import socket
import threading
import os
import sys
import time
import select

current_dir = os.path.dirname(os.path.abspath(__file__))
helpers_dir = os.path.join(current_dir, "..", "helpers")
shared_dir = os.path.join(current_dir, "..", "shared")
commands_dir = os.path.join(current_dir, "..", "commands")

if helpers_dir not in sys.path:
    sys.path.append(os.path.abspath(helpers_dir))

if shared_dir not in sys.path:
    sys.path.append(os.path.abspath(shared_dir))

if commands_dir not in sys.path:
    sys.path.append(os.path.abspath(commands_dir))

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

context = {
    'running': True,
    'username': 'Host',
    'is_host': True,
    'clients': clients,
    'clients_lock': clients_lock,
    'password': '',
    'share_address': config.get('share_address', '')
}

def listen_address_candidates(host):
    if host in ('', '0.0.0.0'):
        return [
            (socket.AF_INET6, '::'),
            (socket.AF_INET, '0.0.0.0')
        ]

    if host == 'localhost':
        return [
            (socket.AF_INET6, '::1'),
            (socket.AF_INET, '127.0.0.1')
        ]

    if host == '::':
        return [(socket.AF_INET6, host)]

    return [(socket.AF_INET, host)]

def create_listener(family, host, port, max_clients):
    listener = socket.socket(
        family,
        socket.SOCK_STREAM
    )

    listener.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    if family == socket.AF_INET6 and hasattr(socket, 'IPV6_V6ONLY'):
        listener.setsockopt(
            socket.IPPROTO_IPV6,
            socket.IPV6_V6ONLY,
            1
        )

    listener.bind((host, port))
    listener.listen(max_clients)
    return listener

def create_server_sockets(host, port, max_clients):
    listeners = []
    last_error = None

    for family, address in listen_address_candidates(host):
        try:
            listeners.append(create_listener(family, address, port, max_clients))
        except OSError as e:
            last_error = e

    if not listeners:
        raise OSError(f'Could not listen on {host}:{port}: {last_error}')

    return listeners

server_sockets = create_server_sockets(HOST, PORT, MAX_CLIENTS)

context['port'] = PORT
print(f'[SERVER] Listening on configured port {PORT}...')
for listener in server_sockets:
    print(f'[SERVER] Bound to {listener.getsockname()[0]}:{listener.getsockname()[1]}')
print(f'[SERVER] Max clients: {MAX_CLIENTS}')
print('[PRIVACY] Client IP addresses are hidden in this app.')
print('[SHARE] Use a tunnel address, such as pinggy, when sharing this server.')

def broadcast(message, sender=None):
    with clients_lock:
        for c in clients[:]:
            if c['socket'] != sender:
                try:
                    c['socket'].send(message.encode())
                except OSError:
                    clients.remove(c)

def send_system_message(client, message):
    try:
        client.send(f'[SYSTEM] {message}'.encode())
    except OSError:
        remove_client(client)

def remove_client(client_socket):
    with clients_lock:
        for c in clients[:]:
            if c['socket'] == client_socket:
                clients.remove(c)
                break

def handle_client(client, client_id):
    global next_client_id

    username = f'Client{client_id} (ID: {client_id})'
    client_label = f'Client ID {client_id}'

    client.settimeout(5.0)
    try:
        auth_msg = client.recv(1024).decode()
    except (OSError, socket.timeout):
        try:
            client.send('[SERVER] Handshake timeout. Connection closed.'.encode())
            client.close()
        except OSError:
            pass
        return

    client.settimeout(None)

    provided_password = ""
    if auth_msg.startswith('__AUTH__:'):
        provided_password = auth_msg.split(':', 1)[1]

    expected_password = context.get('password', '')
    if expected_password and provided_password != expected_password:
        try:
            client.send('[SERVER] Incorrect password. Connection closed.'.encode())
            client.close()
        except OSError:
            pass
        print(f'[REJECTED] {client_label} - incorrect password')
        return

    with clients_lock:
        if len(clients) >= MAX_CLIENTS:
            try:
                client.send('[SERVER] Chat is full. Try again later.'.encode())
                client.close()
            except OSError:
                pass
            print(f'[REJECTED] {client_label} - server full')
            return

        client_record = {
            'id': client_id,
            'socket': client,
            'username': username
        }
        clients.append(client_record)

    try:
        client.send(f'__SET_USERNAME__:{username}'.encode())
    except OSError:
        remove_client(client)
        client.close()
        return

    print(f'[CONNECTED] {username}')

    last_message_time = 0

    while context['running']:
        try:
            message = client.recv(1024).decode()
        except OSError:
            break
        
        if not message:
            break

        if message.startswith('__PING__:'):
            try:
                pong = message.replace('__PING__:', '__PONG__:', 1)
                client.send(pong.encode())
            except OSError:
                pass
            continue

        if message.startswith('__CHANGE_USERNAME__:'):
            new_username = message.split(':', 1)[1]
            with clients_lock:
                for c in clients:
                    if c['socket'] == client:
                        old_username = c['username']
                        c['username'] = f'{new_username} (ID: {c["id"]})'
                        try:
                            client.send(f'__SET_USERNAME__:{new_username} (ID: {c["id"]})'.encode())
                        except OSError:
                            pass
                        print(f'[INFO] ID {c["id"]} changed username from {old_username} to {new_username} (ID: {c["id"]})')
                        break
            continue

        current_time = time.time()

        if current_time - last_message_time < config['message_cooldown']:
            send_system_message(client, 'Slow down')
            continue

        last_message_time = current_time

        print(message)

        broadcast(message, client)

    remove_client(client)

    client.close()

    print(f'[DISCONNECTED] {username}')

def shutdown_server():
    print('[SERVER] Shutting down...')

    with clients_lock:
        for c in clients[:]:
            try:
                c['socket'].send(
                    '[SERVER] Server shutting down.'.encode()
                )
                c['socket'].close()
            except OSError:
                pass

        clients.clear()

    for listener in server_sockets:
        listener.close()

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

while context['running']:
    try:
        ready_listeners, _, _ = select.select(server_sockets, [], [], 1)

        if not ready_listeners:
            continue

        client, _ = ready_listeners[0].accept()

        client_id = next_client_id
        next_client_id += 1

        thread = threading.Thread(
            target=handle_client,
            args=(client, client_id),
            daemon=True
        )

        thread.start()
    except (OSError, ValueError):
        break
