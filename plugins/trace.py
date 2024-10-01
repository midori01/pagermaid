from pagermaid.enums import Message
from pagermaid.listener import listener
from pagermaid.utils import execute
import re

@listener(
    is_plugin=False,
    command="trace",
    need_admin=True,
    description="Perform a network trace using besttrace.",
    parameters="Provide the target to trace."
)
async def trace(message: Message):
    """Use besttrace to perform network tracing."""
    def extract_ip(text):
        ip_pattern = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
        match = ip_pattern.search(text)
        return match.group(0) if match else None

    target = message.arguments

    if not target and message.reply_to_message:
        target = extract_ip(message.reply_to_message.text or "")
    
    if not target:
        await message.edit("Error: No target specified or no IP found in the replied message.")
        return
    
    command = f"besttrace -g cn -q 1 {target}"
    
    try:
        result = await execute(command)
    except Exception as e:
        await message.edit(f"Error executing command: {str(e)}")
        return
    
    if result:
        result_lines = result.splitlines()
        if len(result_lines) > 1:
            result = "\n".join(result_lines[1:])
        
        title = f"**Traceroute to {target}**"
        final_result = f"{title}\n```\n{result}\n```"
        await message.edit(final_result)
    else:
        await message.edit("No result returned from the trace.")