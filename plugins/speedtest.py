import contextlib
import platform
import tarfile

from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from json import loads

from PIL import Image
from os import makedirs
from os.path import exists
from httpx import ReadTimeout

from pagermaid.listener import listener
from pagermaid.single_utils import safe_remove
from pagermaid.enums import Client, Message, AsyncClient
from pagermaid.utils import lang

speedtest_path = "/var/lib/pagermaid/plugins/speedtest"

async def download_cli(request):
    speedtest_version = "1.2.0"
    machine = str(platform.machine())
    if machine == "AMD64":
        machine = "x86_64"
    filename = f"ookla-speedtest-{speedtest_version}-linux-{machine}.tgz"
    speedtest_url = f"https://install.speedtest.net/app/cli/{filename}"
    path = "/var/lib/pagermaid/plugins/"
    if not exists(path):
        makedirs(path)
    data = await request.get(speedtest_url)
    with open(path + filename, mode="wb") as f:
        f.write(data.content)
    try:
        tar = tarfile.open(path + filename, "r:gz")
        file_names = tar.getnames()
        for file_name in file_names:
            tar.extract(file_name, path)
        tar.close()
        safe_remove(path + filename)
        safe_remove(f"{path}speedtest.5")
        safe_remove(f"{path}speedtest.md")
    except Exception:
        return "Error", None
    proc = await create_subprocess_shell(
        f"chmod +x {speedtest_path}",
        shell=True,
        stdout=PIPE,
        stderr=PIPE,
        stdin=PIPE,
    )
    stdout, stderr = await proc.communicate()
    return path if exists(f"{path}speedtest") else None

async def unit_convert(byte):
    power = 1000
    zero = 0
    units = {
        0: '',
        1: 'Kbps',
        2: 'Mbps',
        3: 'Gbps',
        4: 'Tbps'
    }
    byte = byte * 8
    while byte > power:
        byte /= power
        zero += 1
    return f"{round(byte, 2)}{units[zero]}"

async def start_speedtest(command):
    proc = await create_subprocess_shell(command, shell=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
    stdout, stderr = await proc.communicate()
    try:
        stdout = str(stdout.decode().strip())
        stderr = str(stderr.decode().strip())
    except UnicodeDecodeError:
        stdout = str(stdout.decode('gbk').strip())
        stderr = str(stderr.decode('gbk').strip())
    return stdout, stderr, proc.returncode

async def get_as_info(request: AsyncClient, ip: str):
    try:
        response = await request.get(f"http://ip-api.com/json/{ip}?fields=as")
        as_info = response.json().get('as', 'Unknown AS')
        return as_info.split()[0] if as_info != 'Unknown AS' else as_info
    except Exception:
        return 'Unknown AS'

async def run_speedtest(request: AsyncClient, message: Message):
    if not exists(speedtest_path):
        await download_cli(request)

    command = (
        f"sudo {speedtest_path} --accept-license --accept-gdpr -s {message.arguments} -f json"
    ) if str.isdigit(message.arguments) else (
        f"sudo {speedtest_path} --accept-license --accept-gdpr -f json"
    )

    outs, errs, code = await start_speedtest(command)
    if code == 0:
        result = loads(outs)
    elif loads(errs)['message'] == "Configuration - No servers defined (NoServersException)":
        return "Unable to connect to the specified server", None
    else:
        return lang('speedtest_ConnectFailure'), None

    des = (
        f"`    ISP`: `{result['isp']} {await get_as_info(request, result['interface']['externalIp'])}`\n"
        f"` Server`: `{result['server']['id']}` - `{result['server']['name']}` - `{result['server']['location']}`\n"
        f"`  Speed`: ↓`{await unit_convert(result['download']['bandwidth'])}` | ↑`{await unit_convert(result['upload']['bandwidth'])}`\n"
        f"`Latency`: ⇔`{result['ping']['latency']}ms` | ~`{result['ping']['jitter']}ms`\n"
        f"`   Time`: `{result['timestamp'].replace('T', ' ').split('.')[0].replace('Z', '')}`"
    )

    if result["result"]["url"]:
        data = await request.get(result["result"]["url"] + '.png')
        with open("speedtest.png", mode="wb") as f:
            f.write(data.content)
        with contextlib.suppress(Exception):
            img = Image.open("speedtest.png")
            c = img.crop((17, 11, 727, 389))
            c.save("speedtest.png")
    return des, "speedtest.png" if exists("speedtest.png") else None

async def get_all_ids(request):
    if not exists(speedtest_path):
        await download_cli(request)
    outs, errs, code = await start_speedtest(f"sudo {speedtest_path} -f json -L")
    result = loads(outs) if code == 0 else None
    return (
        (
            "Server List:\n"
            + "\n".join(
                f"`{i['id']}` - `{i['name']}` - `{i['location']}`"
                for i in result['servers']
            ),
            None,
        )
        if result
        else ("No Server Available", None)
    )

@listener(command="s",
          need_admin=True,
          description=lang('speedtest_des'),
          parameters="(list/server id)")
async def speedtest(client: Client, message: Message, request: AsyncClient):
    msg = message
    if message.arguments == "list":
        des, photo = await get_all_ids(request)
    elif len(message.arguments) == 0 or str.isdigit(message.arguments):
        msg: Message = await message.edit(lang('speedtest_processing'))
        des, photo = await run_speedtest(request, message)
    else:
        return await msg.edit(lang('arg_error'))
    if not photo:
        return await msg.edit(des)
    try:
        if message.reply_to_message:
            await message.reply_to_message.reply_photo(photo, caption=des)
        else:
            await message.reply_photo(photo, caption=des, quote=False, reply_to_message_id=message.reply_to_top_message_id)
        await message.safe_delete()
    except Exception:
        return await msg.edit(des)
    await msg.safe_delete()
    safe_remove(photo)
