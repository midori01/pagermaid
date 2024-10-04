import contextlib

from PIL import Image
from os.path import exists
from httpx import ReadTimeout
from datetime import datetime

from pagermaid.listener import listener
from pagermaid.single_utils import safe_remove
from pagermaid.enums import Client, Message, AsyncClient
from pagermaid.utils import lang, pip_install

pip_install("speedtest-cli", alias="speedtest")

from speedtest import (
    Speedtest,
    ShareResultsConnectFailure,
    ShareResultsSubmitFailure,
    NoMatchedServers,
    SpeedtestBestServerFailure,
    SpeedtestHTTPError,
)

def unit_convert(byte):
    """Converts byte into readable formats."""
    power = 1000
    zero = 0
    units = {0: "", 1: "Kbps", 2: "Mbps", 3: "Gbps", 4: "Tbps"}
    while byte > power:
        byte /= power
        zero += 1
    return f"{round(byte, 2)} {units[zero]}"

async def get_as_info(request: AsyncClient, ip: str):
    """Fetches AS information based on IP address."""
    try:
        response = await request.get(f"http://ip-api.com/json/{ip}?fields=as")
        data = response.json()
        as_info = data.get('as', 'Unknown AS')
        return as_info.split()[0] if as_info != 'Unknown AS' else as_info
    except Exception:
        return 'Unknown AS'

async def run_speedtest(request: AsyncClient, message: Message):
    test = Speedtest()
    server = int(message.arguments) if len(message.parameter) == 1 else None
    if server:
        servers = test.get_closest_servers()
        for i in servers:
            if i["id"] == str(server):
                test.servers = [i]
                break
    test.get_best_server(servers=test.servers)
    test.download()
    test.upload()
    
    with contextlib.suppress(ShareResultsConnectFailure):
        test.results.share()
    
    result = test.results.dict()

    des = (
        f"[服务商] `{result['client']['isp']} {(await get_as_info(request, result['client']['ip']))}`\n"
        f"[测速点] `{result['server']['sponsor']}` - `{result['server']['name']}`\n"
        f"[速度] ↓`{unit_convert(result['download'])}` ↑`{unit_convert(result['upload'])}`\n"
        f"[时延] `{result['ping']} ms`\n"
        f"[时间] `{result['timestamp'].replace('T', ' ').split('.')[0].replace('Z', '')}`"
    )

    if result["share"]:
        data = await request.get(
            result["share"].replace("http:", "https:"), follow_redirects=True
        )
        with open("speedtest.png", mode="wb") as f:
            f.write(data.content)
        with contextlib.suppress(Exception):
            img = Image.open("speedtest.png")
            c = img.crop((17, 11, 727, 389))
            c.save("speedtest.png")
    
    return des, "speedtest.png" if exists("speedtest.png") else None

async def get_all_ids():
    test = Speedtest()
    servers = test.get_closest_servers()
    return (
        (
            "附近的测速点有：\n\n"
            + "\n".join(
                f"`{i['id']}` - `{int(i['d'])}km` - `{i['name']}` - `{i['sponsor']}`"
                for i in servers
            ),
            None,
        )
        if servers
        else ("附近没有测速点", None)
    )

@listener(
    command="spy",
    description=lang("speedtest_des"),
    parameters="(Server ID/测速点列表)",
)
async def speedtest(client: Client, message: Message, request: AsyncClient):
    """Tests internet speed using speedtest."""
    if message.arguments == "测速点列表":
        msg = message
    else:
        msg: Message = await message.edit(lang("speedtest_processing"))
    
    try:
        if message.arguments == "测速点列表":
            des, photo = await get_all_ids()
        else:
            des, photo = await run_speedtest(request, message)
    except SpeedtestHTTPError:
        return await msg.edit(lang("speedtest_ConnectFailure"))
    except (ValueError, TypeError):
        return await msg.edit(lang("arg_error"))
    except (SpeedtestBestServerFailure, NoMatchedServers):
        return await msg.edit(lang("speedtest_ServerFailure"))
    except (ShareResultsSubmitFailure, RuntimeError, ReadTimeout):
        return await msg.edit(lang("speedtest_ConnectFailure"))
    
    if not photo:
        return await msg.edit(des)
    
    try:
        await client.send_photo(
            message.chat.id,
            photo,
            caption=des,
            message_thread_id=message.message_thread_id or message.reply_to_message_id,
        )
    except Exception:
        return await msg.edit(des)
    
    await msg.safe_delete()
    safe_remove(photo)
