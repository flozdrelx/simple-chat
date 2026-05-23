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

client = None
connected = False

context = {
    'running': True,
    'chat_running': False,
    'username': 'Client1',
    'is_host': False
}

def receive_messages():
    while context['chat_running']:
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

    context['chat_running'] = False
    connected = False

def send_messages():
    while context['chat_running']:
        try:
            message = input('')
        except (EOFError, KeyboardInterrupt):
            context['running'] = False
            break

        if message == '/disconnect':
            disconnect()
            break

        result = handle_command(message, context)

        if result:
            try:
                client.send(f'{context["username"]}: {result}'.encode())
            except OSError:
                context['running'] = False
                break

    if client:
        client.close()

def connect_to_server(host, port):
    global client
    global connected

    client = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    try:
        client.connect((host, port))

    except OSError as e:
        print(f'[ERROR] {e}')

        return

    connected = True
    context['chat_running'] = True

    print(f'[CONNECTED] {host}:{port}')

    receive_thread = threading.Thread(
        target=receive_messages,
        daemon=True
    )

    send_thread = threading.Thread(
        target=send_messages
    )

    receive_thread.start()
    send_thread.start()

    send_thread.join()

    connected = False

def disconnect():
    global client
    global connected

    connected = False

    context['running'] = False

    if client:
        try:
            client.close()

        except OSError:
            pass

    client = None

    print('[DISCONNECTED]')

while context['running']:
    command = input('>>> ').strip()

    if command.startswith('connect '):
        try:
            address = command.split()[1]

            host, port = address.split(':')

            connect_to_server(
                host,
                int(port)
            )

        except ValueError:
            print(
                '[ERROR] Use: connect IP:PORT'
            )

    elif command == 'exit':
        break

    else:
        print('[ERROR] Unknown command.')