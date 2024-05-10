import os
import platform


def command_execution(command: str) -> str:
    """Execute a command and return the result."""
    print("Operating System: " + platform.system() + ", OS Version: " +
          platform.version() + ", Architecture: " + platform.machine())
    try:
        result = os.system(command)
    except Exception as e:
        return f"[command]{command}[/command][error]{e}[/error]"
    return f"[command]{command}[/command][result]{result}[/result]"


functions_declaration = [{
    "name": "command_execution",
    "description": "Execute a command and return the result. Take in consideration that the command is a bash command. This is the data of the machine where the command is executed: Operating System: " + platform.system() + ", OS Version: " + platform.version() + ", Architecture: " + platform.machine(),
    "parameters": [{
        "command": {"type": "string", "description": "The command to be executed."}
    }]
}]
