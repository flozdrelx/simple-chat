import socket
import threading
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
helpers_dir = os.path.join(current_dir, "..", "helpers")
shared_dir = os.path.join(current_dir, "..", "shared")

if helpers_dir not in sys.path:
    sys.path.append(os.path.abspath(helpers_dir))

if shared_dir not in sys.path:
    sys.path.append(os.path.abspath(shared_dir))

from handler import handle_command
from clear import CLEAR_SIGNAL
from config import get_client_host, load_config

USERNAME_SIGNAL = '__SET_USERNAME__:'

config = load_config()

HOST = get_client_host(config)
PORT = config['port']

client = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

context = {
    'running': True,
    'username': 'Client1',
    'is_host': False
}

client.connect((HOST, PORT))

print('[CLIENT] Connected successfully!')

def recieve_messages():
    while context['running']:
        try:
            message = client.recv(1024).decode()
        except OSError:
            break

        if not message:
            break

        if message == CLEAR_SIGNAL:
            os.system('cls' if os.name == 'nt' else 'clear')
            continue

        if message.startswith(USERNAME_SIGNAL):
            context['username'] = message[len(USERNAME_SIGNAL):]
            print(f'[SYSTEM] Your username is {context["username"]}')
            continue

        print(message)

    context['running'] = False

def send_messages():
    while context['running']:
        try:
            message = input('')
        except (EOFError, KeyboardInterrupt):
            context['running'] = False
            break

        result = handle_command(message, context)

        if result:
            try:
                client.send(f'{context["username"]}: {result}'.encode())
            except OSError:
                context['running'] = False
                break

    client.close()

recieve_thread = threading.Thread(
    target=recieve_messages,
    daemon=True
)

send_thread = threading.Thread(
    target=send_messages
)

recieve_thread.start()
send_thread.start()