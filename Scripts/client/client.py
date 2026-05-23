import socket
import threading
import os
import sys
import time

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
    'is_host': False,
    'client': None
}

def receive_messages():
    global connected

    while context['chat_running']:
        try:
            message = client.recv(1024).decode()
        except socket.timeout:
            continue
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

        if message.startswith('__PONG__:'):
            try:
                sent_time = float(message.split(':', 1)[1])
                latency = (time.time() - sent_time) * 1000
                print(f'[PING] Latency: {latency:.2f} ms')
            except (ValueError, IndexError):
                print('[PING] Invalid pong response received.')
            continue

        print(message)

    context['chat_running'] = False
    connected = False

def send_messages():
    while context['chat_running']:
        try:
            message = input('')
        except (EOFError, KeyboardInterrupt):
            context['chat_running'] = False
            break

        if message.strip() in ('/disconnect', 'disconnect'):
            disconnect()
            break

        if message.strip() in ('/exit', 'exit'):
            context['running'] = False
            disconnect()
            break

        result = handle_command(message, context)

        if result:
            try:
                client.send(f'{context["username"]}: {result}'.encode())
            except OSError:
                context['chat_running'] = False
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

    client.settimeout(10)

    try:
        client.connect((host, port))
        client.settimeout(None)
    except OSError as e:
        print(f'[ERROR] {e}')

        return

    connected = True
    context['chat_running'] = True
    context['ip'] = host
    context['port'] = port
    context['client'] = client

    # Clear screen upon successful connection
    os.system('cls' if os.name == 'nt' else 'clear')

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

    context['chat_running'] = False
    context['client'] = None

    if client:
        try:
            client.close()

        except OSError:
            pass

    client = None

    print('[DISCONNECTED]')

def print_main_menu():
    print("Main menu:")
    print("    * Use '/connect <ip:port>' to connect into a server")
    print()

print_main_menu()

while context['running']:
    command = input('>>> ').strip()
    if not command:
        continue

    cmd_parts = command.split()
    cmd_name = cmd_parts[0]

    if cmd_name in ('connect', '/connect'):
        try:
            if len(cmd_parts) < 2:
                raise ValueError
            address = cmd_parts[1]

            host, port = address.split(':')

            connect_to_server(
                host,
                int(port)
            )

            if context['running']:
                os.system('cls' if os.name == 'nt' else 'clear')
                print_main_menu()

        except ValueError:
            print(
                '[ERROR] Use: /connect IP:PORT'
            )
    elif cmd_name in ('exit', '/exit'):
        break
    else:
        print('[ERROR] Unknown command.')