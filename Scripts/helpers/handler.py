import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
commands_dir = os.path.join(current_dir, "..", "commands")

if commands_dir not in sys.path:
    sys.path.append(os.path.abspath(commands_dir))

from exit import exit
from help import help
from set_user import set_user
from clear import clear

COMMANDS = {
    '/clear': clear,
    '/exit': exit,
    '/help': help,
    '/set_user': set_user
}

def handle_command(message, context):
    if not message.startswith('/'):
        return message

    parts = message.split()

    command = parts[0]
    args = parts[1:]

    if command in COMMANDS:
        COMMANDS[command](args, context)

        return None

    return message