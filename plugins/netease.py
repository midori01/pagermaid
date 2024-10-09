from pyrogram.errors import YouBlockedUser
from pyrogram import filters
from pagermaid import bot
from pagermaid.listener import listener
from pagermaid.enums import Message
from pagermaid.utils import alias_command

async def netease_start() -> None:
    try:
        await bot.send_message("Music163bot", "/start")
    except YouBlockedUser:
        await bot.unblock_user("Music163bot")
        await bot.send_message("Music163bot", "/start")

async def handle_conv(conv, filter_criteria):
    await conv.mark_as_read()
    answer = await conv.get_response(filter_criteria)
    await conv.mark_as_read()
    return answer

async def netease_search(keyword: str, message: Message):
    async with bot.conversation("Music163bot") as conv:
        await conv.send_message(f"/search {keyword}")
        answer = await handle_conv(conv, ~filters.regex("搜索中..."))
        if not answer.reply_markup:
            return await message.edit(answer.text.html)
        await bot.request_callback_answer(
            answer.chat.id,
            answer.id,
            callback_data=answer.reply_markup.inline_keyboard[0][0].callback_data,
        )
        answer = await handle_conv(conv, filters.audio)
        await answer.copy(
            message.chat.id,
            reply_to_message_id=message.reply_to_message_id,
            message_thread_id=message.message_thread_id,
        )
        await message.safe_delete()

async def netease_url(url: str, message: Message):
    async with bot.conversation("Music163bot") as conv:
        await conv.send_message(url)
        answer = await handle_conv(conv, filters.audio)
        await answer.copy(
            message.chat.id,
            reply_to_message_id=message.reply_to_message_id,
            message_thread_id=message.message_thread_id,
        )
        await message.safe_delete()

async def netease_id(music_id: str, message: Message):
    async with bot.conversation("Music163bot") as conv:
        await conv.send_message(f"/music {music_id}")
        answer = await handle_conv(conv, filters.audio)
        await answer.copy(
            message.chat.id,
            reply_to_message_id=message.reply_to_message_id,
            message_thread_id=message.message_thread_id,
        )
        await message.safe_delete()

@listener(
    command="n",
    description="Netease Music",
    parameters="[query]",
)
async def netease_music(message: Message):
    if not message.arguments:
        return await message.edit(Netease_Help_Msg)
    await netease_start()
    if message.arguments.startswith("http"):
        return await netease_url(message.arguments, message)
    if message.arguments.isdigit():
        return await netease_id(message.arguments, message)
    return await netease_search(message.arguments, message)
