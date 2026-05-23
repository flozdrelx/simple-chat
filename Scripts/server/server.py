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
from config import load_config

config = load_config()

HOST = config['host']
PORT = config['port']
MAX_CLIENTS = config['max_clients']

clients = []
clients_lock = threading.Lock()
next_client_id = 1

server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

context = {
    'running': True,
    'username': 'Host',
    'is_host': True
}

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

server.bind((HOST, PORT))
server.listen(MAX_CLIENTS)

print(f'[SERVER] Listening on {HOST}:{PORT}...')
print(f'[SERVER] Max clients: {MAX_CLIENTS}')

def broadcast(message, sender=None):
    with clients_lock:
        for client in clients[:]:
            if client != sender:
                try:
                    client.send(message.encode())
                except OSError:
                    clients.remove(client)

def send_system_message(client, message):
    try:
        client.send(f'[SYSTEM] {message}'.encode())
    except OSError:
        remove_client(client)

def remove_client(client):
    with clients_lock:
        if client in clients:
            clients.remove(client)

def handle_client(client, address, username):
    print(f'[CONNECTED] {address} as {username}')

    last_message_time = 0

    while context['running']:
        try:
            message = client.recv(1024).decode()
        except OSError:
            break
        
        if not message:
            break

        current_time = time.time()

        if current_time - last_message_time < config['message_cooldown']:
            send_system_message(client, 'Slow down')
            continue

        last_message_time = current_time

        print(message)

        broadcast(message, client)

    remove_client(client)

    client.close()

    print(f'[DISCONNECTED] {address}')

def shutdown_server():
    print('[SERVER] Shutting down...')

    with clients_lock:
        for client in clients[:]:
            try:
                client.send(
                    '[SERVER] Server shutting down.'.encode()
                )

                client.close()
            except OSError:
                pass

        clients.clear()

    server.close()

def send_messages():
    while context['running']:
        try:
            message = input('')

        except (EOFError, KeyboardInterrupt):
            context['running'] = False
            break

        result = handle_command(message, context)

        if result:
            formatted = f'{context["username"]}: {result}'

            broadcast(formatted)
        elif context.pop('clear_requested', False):
            broadcast(CLEAR_SIGNAL)

    shutdown_server()

host_thread = threading.Thread(
    target=send_messages
)

host_thread.start()

server.settimeout(1)

while context['running']:
    try:
        client, address = server.accept()

        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                client.send('[SERVER] Chat is full. Try again later.'.encode())
                client.close()
                print(f'[REJECTED] {address} - server full')
                continue

            username = f'Client{next_client_id}'
            next_client_id += 1
            clients.append(client)

        client.send(f'__SET_USERNAME__:{username}'.encode())

        thread = threading.Thread(
            target=handle_client,
            args=(client, address, username),
            daemon=True
        )

        thread.start()
    except socket.timeout:
        continue
    except OSError:
        break