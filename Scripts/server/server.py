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
    'is_host': True,
    'clients': clients,
    'clients_lock': clients_lock,
    'password': ''
}

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

def get_ip_address():
    if HOST != '0.0.0.0':
        return HOST
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        try:
            IP = socket.gethostbyname(socket.gethostname())
        except Exception:
            IP = '127.0.0.1'
    finally:
        s.close()
    return IP

server.bind((HOST, PORT))
server.listen(MAX_CLIENTS)

ip = get_ip_address()
context['ip'] = ip
context['port'] = PORT
print(f'[SERVER] Listening on {HOST}:{PORT}...')
print(f'[SERVER] Max clients: {MAX_CLIENTS}')
print(f'[SHARE] Server address: {ip}:{PORT}')

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

def handle_client(client, address, client_id):
    global next_client_id

    username = f'Client{client_id} (ID: {client_id})'

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
        print(f'[REJECTED] {address} - incorrect password')
        return

    with clients_lock:
        if len(clients) >= MAX_CLIENTS:
            try:
                client.send('[SERVER] Chat is full. Try again later.'.encode())
                client.close()
            except OSError:
                pass
            print(f'[REJECTED] {address} - server full')
            return

        client_record = {
            'id': client_id,
            'socket': client,
            'address': address,
            'username': username
        }
        clients.append(client_record)

    try:
        client.send(f'__SET_USERNAME__:{username}'.encode())
    except OSError:
        remove_client(client)
        client.close()
        return

    print(f'[CONNECTED] {address} as {username}')

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
                        print(f'[INFO] {address} (ID: {c["id"]}) changed username from {old_username} to {new_username} (ID: {c["id"]})')
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

    print(f'[DISCONNECTED] {address}')

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

        client_id = next_client_id
        next_client_id += 1

        thread = threading.Thread(
            target=handle_client,
            args=(client, address, client_id),
            daemon=True
        )

        thread.start()
    except socket.timeout:
        continue
    except OSError:
        break