import socket
import threading
import os
import sys
import time
from urllib.parse import urlparse

try:
    import tkinter as tk
    from tkinter.scrolledtext import ScrolledText
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

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

root = None
chat_text = None
message_entry = None
connect_button = None
disconnect_button = None
status_label = None
address_entry = None
password_entry = None


def parse_server_address(address):
    parsed = urlparse(address if '://' in address else f'//{address}')
    if not parsed.hostname or parsed.port is None:
        raise ValueError
    return parsed.hostname, parsed.port


def open_tcp_connection(host, port, timeout=10):
    last_error = None
    try:
        address_infos = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM
        )
    except OSError as e:
        raise OSError(f'Could not resolve {host}:{port}: {e}') from e

    for family, socktype, proto, _, sockaddr in address_infos:
        try:
            sock = socket.socket(family, socktype, proto)
            sock.settimeout(timeout)
            sock.connect(sockaddr)
            return sock
        except OSError as e:
            last_error = e
            try:
                sock.close()
            except OSError:
                pass
    raise OSError(f'Could not connect to {host}:{port}: {last_error}')


def append_text(message):
    if not message:
        return
    if GUI_AVAILABLE and root and chat_text:
        def append():
            chat_text.configure(state='normal')
            chat_text.insert('end', message + '\n')
            chat_text.see('end')
            chat_text.configure(state='disabled')
        try:
            root.after(0, append)
        except tk.TclError:
            print(message)
    else:
        print(message)


def clear_screen():
    if GUI_AVAILABLE and root and chat_text:
        def clear_text():
            chat_text.configure(state='normal')
            chat_text.delete('1.0', 'end')
            chat_text.configure(state='disabled')
        try:
            root.after(0, clear_text)
        except tk.TclError:
            os.system('cls' if os.name == 'nt' else 'clear')
    else:
        os.system('cls' if os.name == 'nt' else 'clear')


def set_connected_ui(value):
    if not GUI_AVAILABLE or not root:
        return
    def update():
        if value:
            connect_button.config(state='disabled')
            address_entry.config(state='disabled')
            password_entry.config(state='disabled')
            disconnect_button.config(state='normal')
            message_entry.config(state='normal')
            status_label.config(text=f'Connected as {context["username"]}')
        else:
            connect_button.config(state='normal')
            address_entry.config(state='normal')
            password_entry.config(state='normal')
            disconnect_button.config(state='disabled')
            message_entry.config(state='disabled')
            status_label.config(text='Disconnected')
    try:
        root.after(0, update)
    except tk.TclError:
        pass


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
            clear_screen()
            continue
        if message.startswith(USERNAME_SIGNAL):
            context['username'] = message[len(USERNAME_SIGNAL):]
            append_text(f'[SYSTEM] Your username is {context["username"]}')
            continue
        if message.startswith('__PONG__:'):
            try:
                sent_time = float(message.split(':', 1)[1])
                latency = (time.time() - sent_time) * 1000
                append_text(f'[PING] Latency: {latency:.2f} ms')
            except (ValueError, IndexError):
                append_text('[PING] Invalid pong response received.')
            continue
        append_text(message)
    context['chat_running'] = False
    connected = False
    set_connected_ui(False)
    append_text('[DISCONNECTED]')


def process_user_message(message):
    message = message.strip()
    if not message:
        return
    if message in ('/disconnect', 'disconnect'):
        disconnect()
        return
    if message in ('/exit', 'exit'):
        context['running'] = False
        disconnect()
        if GUI_AVAILABLE and root:
            try:
                root.quit()
            except tk.TclError:
                pass
        return
    result = handle_command(message, context, append_text)
    if result:
        if not client:
            append_text('[ERROR] Not connected to a server.')
            return
        try:
            client.send(f'{context["username"]}: {result}'.encode())
        except OSError:
            append_text('[ERROR] Failed to send message.')
            context['chat_running'] = False
            connected = False
            set_connected_ui(False)


def send_messages():
    while context['chat_running']:
        try:
            message = input('')
        except (EOFError, KeyboardInterrupt):
            context['chat_running'] = False
            break
        process_user_message(message)
    if client:
        client.close()


def connect_to_server(host, port, password=""):
    global client
    global connected
    try:
        client = open_tcp_connection(host, port, timeout=10)
    except OSError as e:
        append_text(f'[ERROR] {e}')
        set_connected_ui(False)
        return
    try:
        client.send(f'__AUTH__:{password}'.encode())
    except OSError as e:
        append_text(f'[ERROR] Failed to send authentication: {e}')
        client.close()
        client = None
        set_connected_ui(False)
        return
    try:
        initial_message = client.recv(1024).decode()
    except (OSError, socket.timeout) as e:
        append_text(f'[ERROR] Failed to complete server handshake: {e}')
        client.close()
        client = None
        set_connected_ui(False)
        return
    if not initial_message:
        append_text('[ERROR] Server closed the connection.')
        client.close()
        client = None
        set_connected_ui(False)
        return
    if initial_message.startswith(USERNAME_SIGNAL):
        context['username'] = initial_message[len(USERNAME_SIGNAL):]
    else:
        append_text(initial_message)
        client.close()
        client = None
        set_connected_ui(False)
        return
    client.settimeout(None)
    connected = True
    context['chat_running'] = True
    context['port'] = port
    context['client'] = client
    clear_screen()
    append_text('[CONNECTED] Connected to server.')
    append_text(f'[SYSTEM] Your username is {context["username"]}')
    receive_thread = threading.Thread(
        target=receive_messages,
        daemon=True
    )
    receive_thread.start()
    set_connected_ui(True)
    if not GUI_AVAILABLE:
        send_thread = threading.Thread(target=send_messages)
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
    set_connected_ui(False)
    append_text('[DISCONNECTED]')


def build_gui():
    global root, chat_text, message_entry, connect_button, disconnect_button, status_label, address_entry, password_entry
    root = tk.Tk()
    root.title('Simple Chat Client')
    root.geometry('600x520')
    connect_frame = tk.LabelFrame(root, text='Connect to Server', padx=10, pady=10)
    connect_frame.pack(fill='x', padx=10, pady=10)
    tk.Label(connect_frame, text='Address:').grid(row=0, column=0, sticky='w')
    address_entry = tk.Entry(connect_frame, width=42)
    address_entry.insert(0, f'{HOST}:{PORT}')
    address_entry.grid(row=0, column=1, sticky='we', padx=5)
    tk.Label(connect_frame, text='Password:').grid(row=1, column=0, sticky='w', pady=(5, 0))
    password_entry = tk.Entry(connect_frame, width=42, show='*')
    password_entry.grid(row=1, column=1, sticky='we', padx=5, pady=(5, 0))
    connect_button = tk.Button(connect_frame, text='Connect', width=12, command=gui_connect)
    connect_button.grid(row=0, column=2, rowspan=2, padx=(10, 0))
    status_label = tk.Label(root, text='Disconnected', anchor='w')
    status_label.pack(fill='x', padx=10)
    chat_frame = tk.Frame(root)
    chat_frame.pack(fill='both', expand=True, padx=10, pady=(5, 0))
    chat_text = ScrolledText(chat_frame, state='disabled', wrap='word')
    chat_text.pack(fill='both', expand=True)
    input_frame = tk.Frame(root)
    input_frame.pack(fill='x', padx=10, pady=10)
    message_entry = tk.Entry(input_frame, state='disabled')
    message_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
    message_entry.bind('<Return>', on_send_clicked)
    send_button = tk.Button(input_frame, text='Send', width=10, command=lambda: [process_user_message(message_entry.get()), message_entry.delete(0, 'end')])
    send_button.pack(side='left')
    disconnect_button = tk.Button(root, text='Disconnect', state='disabled', command=disconnect)
    disconnect_button.pack(fill='x', padx=10, pady=(0, 10))
    root.protocol('WM_DELETE_WINDOW', on_close)
    set_connected_ui(False)
    append_text('Enter an address or tunnel and click Connect.')
    root.mainloop()


def on_send_clicked(event=None):
    if not message_entry:
        return
    message = message_entry.get()
    message_entry.delete(0, 'end')
    process_user_message(message)


def gui_connect():
    if not address_entry:
        return
    address = address_entry.get().strip()
    password = password_entry.get().strip()
    if not address:
        append_text('[ERROR] Address is required.')
        return
    try:
        host, port = parse_server_address(address)
    except ValueError:
        append_text('[ERROR] Use ADDRESS:PORT format.')
        return
    connect_button.config(state='disabled')
    append_text(f'[SYSTEM] Connecting to {host}:{port} ...')
    threading.Thread(target=connect_to_server, args=(host, port, password), daemon=True).start()


def on_close():
    context['running'] = False
    disconnect()
    if root:
        root.destroy()


def print_main_menu():
    print('Main menu:')
    print("    * Use '/connect <address:port|tunnel.domain:port> [password]' to connect into a server")
    print()

if GUI_AVAILABLE:
    build_gui()
else:
    print_main_menu()
    while context['running']:
        try:
            command = input('>>> ').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not command:
            continue
        cmd_parts = command.split()
        cmd_name = cmd_parts[0]
        if cmd_name in ('connect', '/connect'):
            try:
                if len(cmd_parts) < 2:
                    raise ValueError
                address = cmd_parts[1]
                password = " ".join(cmd_parts[2:]) if len(cmd_parts) > 2 else ""
                host, port = parse_server_address(address)
                connect_to_server(host, port, password)
            except ValueError:
                print(
                    '[ERROR] Use: /connect ADDRESS:PORT [PASSWORD] or /connect TUNNEL.DOMAIN:PORT [PASSWORD]'
                )
        elif cmd_name in ('exit', '/exit'):
            break
        else:
            print('[ERROR] Unknown command.')