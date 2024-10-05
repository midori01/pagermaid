import contextlib
import platform
import tarfile

from asyncio import create_subprocess_shell
from asyncio.subprocess import PIPE
from json import loads

from PIL import Image
from pathlib import Path
from httpx import ReadTimeout

from pagermaid.listener import listener
from pagermaid.single_utils import safe_remove
from pagermaid.enums import Client, Message, AsyncClient
from pagermaid.utils import lang

speedtest_path = "/var/lib/pagermaid/plugins/speedtest"

async def download_cli(request):
    speedtest_version = "1.2.0"
    machine = "x86_64" if platform.machine().lower() == "amd64" else platform.machine().lower()
    filename = f"ookla-speedtest-{speedtest_version}-linux-{machine}.tgz"
    path = Path("/var/lib/pagermaid/plugins/")
    path.mkdir(parents=True, exist_ok=True)

    data = await request.get(f"https://install.speedtest.net/app/cli/{filename}")
    file_path = path / filename
    file_path.write_bytes(data.content)

    try:
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(path)
        safe_remove(file_path)
        for extra_file in ["speedtest.5", "speedtest.md"]:
            safe_remove(path / extra_file)
    except Exception:
        return "Error", None

    proc = await create_subprocess_shell(f"chmod +x {speedtest_path}", stdout=PIPE, stderr=PIPE, stdin=PIPE)
    await proc.communicate()
    return path if (path / "speedtest").exists() else None

async def decode_output(output):
    return output.decode(errors='ignore').strip()

async def start_speedtest(command):
    proc = await create_subprocess_shell(command, shell=True, stdout=PIPE, stderr=PIPE, stdin=PIPE)
    stdout, stderr = await proc.communicate()
    return await decode_output(stdout), await decode_output(stderr), proc.returncode

async def unit_convert(byte):
    units = ['bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps']
    byte *= 8
    power = 1000
    zero = 0
    while byte >= power and zero < len(units) - 1:
        byte /= power
        zero += 1
    return f"{round(byte, 2)} {units[zero]}"

async def get_as_info(request: AsyncClient, ip: str):
    try:
        response = await request.get(f"http://ip-api.com/json/{ip}?fields=as", timeout=10)
        as_info = response.json().get('as', 'Unknown AS')
        return as_info.split()[0] if as_info != 'Unknown AS' else as_info
    except ReadTimeout:
        return 'Timeout'
    except Exception:
        return 'Unknown AS'

async def run_speedtest(request: AsyncClient, message: Message):
    if not Path(speedtest_path).exists():
        await download_cli(request)
    command = (
        f"sudo {speedtest_path} --accept-license --accept-gdpr -s {message.arguments} -f json"
    ) if message.arguments.isnumeric() else (
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
        f"[服务商] `{result['isp']} {await get_as_info(request, result['interface']['externalIp'])}`\n"
        f"[测速点] `{result['server']['id']}` - `{result['server']['name']}` - `{result['server']['location']}`\n"
        f"[速度] ↓`{await unit_convert(result['download']['bandwidth'])}` ↑`{await unit_convert(result['upload']['bandwidth'])}`\n"
        f"[时延] ⇔`{result['ping']['latency']} ms` ~`{result['ping']['jitter']} ms`\n"
        f"[时间] `{result['timestamp'].replace('T', ' ').split('.')[0].replace('Z', '')}`"
    )
    if result["result"]["url"]:
        data = await request.get(result["result"]["url"] + '.png')
        path = "speedtest.png"
        with open(path, mode="wb") as f:
            f.write(data.content)
        try:
            img = Image.open(path)
            img.crop((17, 11, 727, 389)).save(path)
        except Exception:
            pass
    return des, path if Path(path).exists() else None

async def get_all_ids(request):
    if not Path(speedtest_path).exists():
        await download_cli(request)
    outs, _, code = await start_speedtest(f"sudo {speedtest_path} -f json -L")
    if code != 0:
        return "No Server Available", None
    result = loads(outs)
    return (
        "Server List:\n" + "\n".join(
            f"`{i['id']}` - `{i['name']}` - `{i['location']}`"
            for i in result['servers']
        ),
        None
    )

@listener(command="sgo", need_admin=True, description=lang('speedtest_des'), parameters="(list/server id)")
async def speedtest(client: Client, message: Message, request: AsyncClient):
    msg = await message.edit(lang('speedtest_processing'))
    try:
        if message.arguments == "list":
            des, photo = await get_all_ids(request)
        elif not message.arguments or message.arguments.isnumeric():
            des, photo = await run_speedtest(request, message)
        else:
            return await msg.edit(lang('arg_error'))

        if not photo:
            return await msg.edit(des)

        await (message.reply_to_message.reply_photo if message.reply_to_message else message.reply_photo)(
            photo, caption=des, quote=False, reply_to_message_id=message.reply_to_top_message_id
        )
    except Exception:
        await msg.edit(des)
    finally:
        await msg.safe_delete()
        if photo:
            safe_remove(photo)
