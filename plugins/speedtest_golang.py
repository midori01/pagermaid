import contextlib
import platform
import tarfile
import asyncio

from json import loads
from PIL import Image
from os import makedirs
from os.path import exists
from httpx import AsyncClient
from pagermaid.listener import listener
from pagermaid.single_utils import safe_remove
from pagermaid.utils import lang


speedtest_path = "/var/lib/pagermaid/plugins/speedtest"

async def download_cli(request):
    speedtest_version = "1.2.0"
    machine = platform.machine()
    if machine == "AMD64":
        machine = "x86_64"
    filename = f"ookla-speedtest-{speedtest_version}-linux-{machine}.tgz"
    speedtest_url = f"https://install.speedtest.net/app/cli/{filename}"
    path = "/var/lib/pagermaid/plugins/"

    makedirs(path, exist_ok=True)
    
    try:
        data = await request.get(speedtest_url)
        with open(path + filename, mode="wb") as f:
            f.write(data.content)

        with tarfile.open(path + filename, "r:gz") as tar:
            tar.extractall(path)
        
        # Clean up
        safe_remove(path + filename)
        for file in ['speedtest.5', 'speedtest.md']:
            safe_remove(path + file)

    except Exception as e:
        return "Error downloading or extracting the CLI", str(e)

    # Set executable permission
    await run_command(f"chmod +x {speedtest_path}")

async def run_command(command):
    proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    return stdout.decode().strip(), stderr.decode().strip(), proc.returncode

async def unit_convert(byte):
    """ Converts byte into readable formats. """
    power = 1000
    units = ['Kbps', 'Mbps', 'Gbps', 'Tbps']
    byte *= 8  # Convert to bits
    zero = 0
    
    while byte > power and zero < len(units) - 1:
        byte /= power
        zero += 1
        
    return f"{round(byte, 2)} {units[zero]}"

async def get_as_info(request: AsyncClient, ip: str):
    try:
        response = await request.get(f"http://ip-api.com/json/{ip}?fields=as")
        as_info = response.json().get('as', 'Unknown AS')
        return as_info.split()[0] if as_info != 'Unknown AS' else as_info
    except Exception:
        return 'Unknown AS'

async def run_speedtest(request: AsyncClient, message: str):
    if not exists(speedtest_path):
        await download_cli(request)

    command = (
        f"sudo {speedtest_path} --accept-license --accept-gdpr -s {message} -f json"
        if message.isdigit() else 
        f"sudo {speedtest_path} --accept-license --accept-gdpr -f json"
    )

    outs, errs, code = await run_command(command)
    if code == 0:
        result = loads(outs)
    elif "No servers defined" in errs:
        return "Unable to connect to the specified server", None
    else:
        return lang('speedtest_ConnectFailure'), None

    return await format_speedtest_result(result)

async def format_speedtest_result(result):
    des = (
        f"[服务商] `{result['isp']} {await get_as_info(request, result['interface']['externalIp'])}`\n"
        f"[测速点] `{result['server']['id']}` - `{result['server']['name']}` - `{result['server']['location']}`\n"
        f"[速度] ↓`{await unit_convert(result['download']['bandwidth'])}` ↑`{await unit_convert(result['upload']['bandwidth'])}`\n"
        f"[时延] ⇔`{result['ping']['latency']} ms` ~`{result['ping']['jitter']} ms`\n"
        f"[时间] `{result['timestamp'].replace('T', ' ').split('.')[0].replace('Z', '')}`"
    )

    if result["result"]["url"]:
        return await fetch_and_crop_image(result["result"]["url"]), des
    return None, des

async def fetch_and_crop_image(url):
    try:
        data = await request.get(url + '.png')
        with open("speedtest.png", mode="wb") as f:
            f.write(data.content)

        with contextlib.suppress(Exception):
            img = Image.open("speedtest.png")
            c = img.crop((17, 11, 727, 389))
            c.save("speedtest.png")

        return "speedtest.png" if exists("speedtest.png") else None
    except Exception:
        return None

async def get_all_ids(request: AsyncClient):
    if not exists(speedtest_path):
        await download_cli(request)
        
    outs, errs, code = await run_command(f"sudo {speedtest_path} -f json -L")
    if code == 0:
        result = loads(outs)
        return (
            "Server List:\n" + 
            "\n".join(f"`{i['id']}` - `{i['name']}` - `{i['location']}`" for i in result['servers']),
            None
        )
    return "No Server Available", None

@listener(command="sgo", need_admin=True, description=lang('speedtest_des'), parameters="(list/server id)")
async def speedtest(client: Client, message: Message, request: AsyncClient):
    """ Tests internet speed using speedtest. """
    msg = message
    if message.arguments == "list":
        des, photo = await get_all_ids(request)
    elif len(message.arguments) == 0 or message.arguments.isdigit():
        msg: Message = await message.edit(lang('speedtest_processing'))
        des, photo = await run_speedtest(request, message.arguments)
    else:
        return await msg.edit(lang('arg_error'))

    if not photo:
        return await msg.edit(des)

    try:
        await message.reply_to_message.reply_photo(photo, caption=des) if message.reply_to_message else await message.reply_photo(photo, caption=des, quote=False)
        await message.safe_delete()
    except Exception:
        return await msg.edit(des)

    await msg.safe_delete()
    safe_remove(photo)
