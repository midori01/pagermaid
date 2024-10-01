from pagermaid.common.status import get_bot_uptime
from pagermaid.listener import listener
from pagermaid.utils import execute

@listener(is_plugin=False, command="service", description="Show service details.")
async def sysstatus(message):
    """Show service details."""
    
    args = message.arguments.strip().split()
    service_name = args[0] if args else "pagermaid"
    
    try:
        result = await execute(f"systemctl --no-pager status {service_name} | grep -E 'Active|PID|Tasks|Memory|CPU' | grep -v 'grep'")
        
        if "not be found" in result:
            await message.edit(f"Service '{service_name}' could not be found.")
            return

        if "inactive" in result:
            await message.edit(f"Service '{service_name}' is inactive (dead).")
            return

    except Exception as e:
        await message.edit(f"An error occurred while fetching service details: {str(e)}")
        return

    lines = result.splitlines()
    uptime = await get_bot_uptime()

    for i, line in enumerate(lines):
        line = line.strip()
        
        if 'Active:' in line:
            line = line.replace('Active:', '').replace('ago', '').strip()
            before_since, _, after_since = line.partition('since')
            
            if after_since:
                since_time, _, uptime_info = after_since.partition(';')
                lines[i] = f"{before_since.strip()}\nStarted: {since_time.strip()}\nUptime: {uptime_info.strip()}"
                
                if service_name == "pagermaid":
                    lines[i] += f' ({uptime})'
        else:
            lines[i] = line

    result = "\n".join(lines)
    
    text = f"**{service_name.capitalize()} Service Details**\n```{result.strip()}```"
    await message.edit(text)
