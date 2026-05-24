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
from host import host
from ping import ping
from see_users import see_users
from kick import kick
from set_pswd import set_pswd

COMMANDS = {
    '/clear': clear,
    '/exit': exit,
    '/help': help,
    '/set_user': set_user,
    '/host': host,
    '/ping': ping,
    '/see_users': see_users,
    '/kick': kick,
    '/set_pswd': set_pswd
}

def handle_command(message, context, output_func=print):
    if not message.startswith('/'):
        return message

    parts = message.split()

    command = parts[0]
    args = parts[1:]

    if command in COMMANDS:
        COMMANDS[command](args, context, output_func)
        return None

    return message