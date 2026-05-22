import socket
import threading
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
helpers_dir = os.path.join(current_dir, "..", "helpers")

if helpers_dir not in sys.path:
    sys.path.append(os.path.abspath(helpers_dir))

from handler import handle_command
from clear import CLEAR_SIGNAL

HOST = '0.0.0.0'
PORT = 6667

server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

context = {
    'running': True,
    'username': 'Host',
    'is_host': True
}

server.bind((HOST, PORT))
server.listen()

print(f'[SERVER] Listening on port {PORT}...')

client, address = server.accept()

print(f'[CONNECTED] {address}')

def recieve_messages():
    while context['running']:
        try:
            message = client.recv(1024).decode()
        except OSError:
            break

        if not message:
            break

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

        if context.pop('clear_requested', False):
            try:
                client.send(CLEAR_SIGNAL.encode())
            except OSError:
                context['running'] = False
                break

        if result:
            try:
                client.send(f'{context["username"]}: {result}'.encode())
            except OSError:
                context['running'] = False
                break

    client.close()
    server.close()

recieve_thread = threading.Thread(
    target=recieve_messages,
    daemon=True
)

send_thread = threading.Thread(
    target=send_messages
)

recieve_thread.start()
send_thread.start()