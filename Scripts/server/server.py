import socket
import threading
import os
import sys
import time
import select
import uuid
import base64
from collections import deque

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
from protocol import recv_frame, send_frame, send_text
from images import prepare_image, ImageError, FILE_TYPES
from crypto import load_or_create_identity, CryptoError

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    from tkinter import filedialog
    from PIL import Image, ImageTk
    import io
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

config = load_config()

HOST = config['host']
PORT = config['port']
MAX_CLIENTS = config['max_clients']

clients = []
clients_lock = threading.Lock()
next_client_id = 1

root = None
chat_text = None
message_entry = None
status_label = None
send_button = None
shutdown_button = None
theme_button = None
image_button = None
clients_tree = None
image_refs = []
suggestion_list = None
ttk_style = None
ttk_light_theme = None

HOST_COMMANDS = [
    ('/help', 'Show all available commands'),
    ('/exit', 'Shut down the server'),
    ('/set_user <user>', 'Change the host username'),
    ('/host', 'Show safe server sharing information'),
    ('/image <path>', 'Send a PNG, JPG, or WEBP image'),
    ('/clear', 'Clear the chat for everyone'),
    ('/see_users', 'List connected users'),
    ('/kick <id|uuid>', 'Kick a user by numeric ID or UUID prefix'),
    ('/set_pswd <password>', 'Set or clear the room password'),
    ('/allowimgs', 'Enable or disable image sharing'),
    ('/imglimit <count>', 'Set images per minute per user'),
]
dark_mode = False
light_widget_options = {}

DARK_THEME = {
    'bg': '#100b1f',
    'panel': '#181027',
    'field': '#211631',
    'text': '#f4efff',
    'muted': '#c9bce7',
    'accent': '#9d7cff',
    'button': '#2c1f42',
    'button_active': '#3b2a5f',
    'disabled': '#85779f',
    'border': '#4c376d',
    'self_message': '#c7a8ff',
    'danger': '#7f2435',
    'danger_active': '#a13046',
}

context = {
    'running': True,
    'username': 'Host',
    'is_host': True,
    'clients': clients,
    'clients_lock': clients_lock,
    'password': '',
    'share_address': config.get('share_address', '')
    , 'allow_images': config.get('allow_images', False)
    , 'image_rate_limit': config.get('image_rate_limit', 5)
}
host_identity = load_or_create_identity()
host_image_times = deque()

def public_directory(exclude_uuid=None):
    with clients_lock:
        result = {c['uuid']: c['public_key'] for c in clients if c['uuid'] != exclude_uuid}
    # The host is listed like any other room participant, so one connected
    # client can exchange encrypted messages directly with the host.
    result['host'] = host_identity.public_b64
    return result

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

if not GUI_AVAILABLE:
    print(f'[SERVER] Listening on configured port {PORT}...')

    for listener in server_sockets:
        print(f'[SERVER] Bound to {listener.getsockname()[0]}:{listener.getsockname()[1]}')
    
    print(f'[SERVER] Max clients: {MAX_CLIENTS}')
    print('[PRIVACY] Client IP addresses are hidden in this app.')
    print('[SHARE] Use a tunnel address, such as pinggy, when sharing this server.')

def broadcast(message, exclude_socket=None, kind='text', **metadata):
    removed_client = False

    with clients_lock:
        for c in clients[:]:
            if c['socket'] != exclude_socket:
                try:
                    with c['send_lock']:
                        send_frame(c['socket'], kind, message, **metadata)
                except OSError:
                    clients.remove(c)
                    removed_client = True

    if removed_client:
        refresh_connected_count()

context['broadcast_system'] = lambda message: broadcast(f'[SYSTEM] {message}')

def send_system_message(client, message):
    try:
        with clients_lock:
            record = next((c for c in clients if c['socket'] == client), None)
        if record:
            with record['send_lock']:
                send_text(client, f'[SYSTEM] {message}')
        else:
            send_text(client, f'[SYSTEM] {message}')
    except OSError:
        remove_client(client)

def remove_client(client_socket):
    removed_client = False

    with clients_lock:
        for c in clients[:]:
            if c['socket'] == client_socket:
                clients.remove(c)
                removed_client = True
                break

    if removed_client:
        refresh_connected_count()

def refresh_connected_count():
    if not GUI_AVAILABLE or not root:
        return

    with clients_lock:
        user_count = len(clients)
        client_rows = [
            (str(c['id']), c['uuid'], c['username'])
            for c in clients
        ]

    def update():
        if status_label:
            status_label.config(text=f'Host running | {user_count} users connected')
        if clients_tree:
            selected = clients_tree.selection()
            selected_uuid = selected[0] if selected else None
            clients_tree.delete(*clients_tree.get_children())
            for client_id, client_uuid, username in client_rows:
                clients_tree.insert('', 'end', iid=client_uuid, values=(client_id, client_uuid, username))
            if selected_uuid and clients_tree.exists(selected_uuid):
                clients_tree.selection_set(selected_uuid)

    try:
        root.after(0, update)
    except tk.TclError:
        pass

def handle_client(client, client_id):
    global next_client_id

    username = f'Client{client_id} (ID: {client_id})'
    client_label = f'Client ID {client_id}'

    client.settimeout(5.0)
    try:
        header, payload = recv_frame(client)
        auth_msg = payload.decode('utf-8') if header.get('kind') == 'control' else ''
        client_public_key = header.get('public_key', '')
    except (OSError, socket.timeout, ValueError, ConnectionError):
        try:
            send_text(client, '[SERVER] Handshake timeout. Connection closed.')
            client.close()
        except OSError:
            pass
        return

    client.settimeout(None)

    try:
        valid_public_key = base64.b64decode(client_public_key, validate=True)
    except (ValueError, TypeError):
        valid_public_key = b''
    if len(valid_public_key) != 32:
        send_text(client, '[SERVER] Encryption identity is required.')
        client.close()
        return

    provided_password = ""

    if auth_msg.startswith('__AUTH__:'):
        provided_password = auth_msg.split(':', 1)[1]

    expected_password = context.get('password', '')

    if expected_password and provided_password != expected_password:
        try:
            send_text(client, '[SERVER] Incorrect password. Connection closed.')
            client.close()
        except OSError:
            pass
        append_text(f'[REJECTED] {client_label} - incorrect password')
        return

    with clients_lock:
        if len(clients) >= MAX_CLIENTS:
            try:
                send_text(client, '[SERVER] Chat is full. Try again later.')
                client.close()
            except OSError:
                pass

            append_text(f'[REJECTED] {client_label} - server full')
            return

        client_uuid = str(uuid.uuid4())
        client_record = {
            'id': client_id,
            'uuid': client_uuid,
            'socket': client,
            'username': username,
            'send_lock': threading.Lock(),
            'image_times': deque()
            , 'public_key': client_public_key
        }
        clients.append(client_record)

    refresh_connected_count()

    try:
        send_frame(client, 'welcome', b'', username=username, client_uuid=client_uuid,
                   peers=public_directory(client_uuid), host_public_key=host_identity.public_b64)
        broadcast(b'', client, kind='peer_joined', peer_id=client_uuid, public_key=client_public_key)
    except OSError:
        remove_client(client)
        client.close()
        return

    append_text(f'[CONNECTED] {username} | UUID: {client_uuid}')

    last_message_time = 0

    while context['running']:
        try:
            header, payload = recv_frame(client)
        except (OSError, ValueError, ConnectionError):
            break

        kind = header.get('kind')
        if kind == 'encrypted':
            content_type = header.get('content_type')
            if content_type not in ('text', 'image'):
                continue
            with clients_lock:
                record = next((c for c in clients if c['socket'] == client), None)
            if record is None:
                break
            if content_type == 'image':
                if not context['allow_images']:
                    send_system_message(client, 'Image sharing is disabled by the host.')
                    continue
                now = time.time()
                while record['image_times'] and now - record['image_times'][0] >= 60:
                    record['image_times'].popleft()
                if len(record['image_times']) >= context['image_rate_limit']:
                    send_system_message(client, f'Image rate limit reached ({context["image_rate_limit"]}/minute).')
                    continue
                record['image_times'].append(now)
            current_time = time.time()
            if current_time - last_message_time < config['message_cooldown']:
                send_system_message(client, 'Slow down')
                continue
            last_message_time = current_time
            # The host is an ordinary encrypted room participant. Decrypt only
            # the box explicitly addressed to "host"; other recipient boxes
            # remain opaque while the original envelope is relayed unchanged.
            try:
                received_type, plain = host_identity.decrypt_envelope(
                    'host', record['public_key'], payload
                )
                if received_type != content_type:
                    raise ValueError('content type mismatch')
                if content_type == 'text':
                    append_text(plain.decode('utf-8'), tag='left')
                else:
                    append_image(plain, record['username'])
            except (CryptoError, UnicodeDecodeError, ValueError):
                send_system_message(client, 'Encrypted payload could not be authenticated.')
                continue
            # Relay the original envelope unchanged after decrypting the host's
            # explicitly addressed participant copy above.
            broadcast(payload, client, kind='encrypted', sender_id=client_uuid,
                      sender=record['username'], content_type=content_type,
                      format=header.get('format'))
            continue

        if kind == 'image':
            if not context['allow_images']:
                send_system_message(client, 'Image sharing is disabled by the host.')
                continue
            with clients_lock:
                record = next((c for c in clients if c['socket'] == client), None)
            if record is None:
                break
            now = time.time()
            while record['image_times'] and now - record['image_times'][0] >= 60:
                record['image_times'].popleft()
            if len(record['image_times']) >= context['image_rate_limit']:
                send_system_message(client, f'Image rate limit reached ({context["image_rate_limit"]}/minute).')
                continue
            send_system_message(client, 'Legacy image packets are not accepted; encryption is required.')
            continue

        if kind != 'text':
            continue
        try:
            message = payload.decode('utf-8')
        except UnicodeDecodeError:
            continue

        if message.startswith('__PING__:'):
            try:
                pong = message.replace('__PING__:', '__PONG__:', 1)
                send_text(client, pong)
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
                            send_text(client, f'__SET_USERNAME__:{new_username} (ID: {c["id"]})')
                        except OSError:
                            pass

                        append_text(f'[INFO] ID {c["id"]} changed username from {old_username} to {new_username} (ID: {c["id"]})')
                        break
            refresh_connected_count()
            continue

        # Never accept ordinary chat on the control channel. This prevents an
        # old or modified client from silently downgrading the room to plaintext.
        send_system_message(client, 'Plaintext chat packets are not accepted.')

    remove_client(client)

    broadcast(b'', client, kind='peer_left', peer_id=client_uuid)

    client.close()

    append_text(f'[DISCONNECTED] {client_label} | UUID: {client_uuid}')

def kick_selected_client():
    if not clients_tree:
        return
    selected = clients_tree.selection()
    if not selected:
        append_text('[ERROR] Select a client in the Clients tab first.')
        return
    handle_command(f'/kick {selected[0]}', context, append_text)
    refresh_connected_count()

def shutdown_server():
    print('[SERVER] Shutting down...')

    with clients_lock:
        for c in clients[:]:
            try:
                send_text(c['socket'], '[SERVER] Server shutting down.')
                c['socket'].close()
            except OSError:
                pass

        clients.clear()

    refresh_connected_count()

    for listener in server_sockets:
        listener.close()

def append_text(message, tag='left'):
    if not message:
        return

    if GUI_AVAILABLE and root and chat_text:
        def append():
            chat_text.configure(state='normal')
            chat_text.insert('end', message + '\n', tag)
            chat_text.see('end')
            chat_text.configure(state='disabled')

        try:
            root.after(0, append)
        except tk.TclError:
            print(message)
    else:
        print(message)

def append_image(data, sender, tag='left'):
    if not GUI_AVAILABLE or not root or not chat_text:
        print(f'[IMAGE] {sender} sent an image ({len(data) / 1024:.1f} KB)')
        return
    def append():
        try:
            image = Image.open(io.BytesIO(data))
            image_format = (image.format or 'PNG').lower().replace('jpeg', 'jpg')
            image.thumbnail((420, 300), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            image_refs.append(photo)
            chat_text.configure(state='normal')
            line_start = chat_text.index('end-1c')
            block = tk.Frame(chat_text)
            tk.Label(block, text=f'{sender}:', anchor='e' if tag == 'right' else 'w').pack(fill='x')
            tk.Label(block, image=photo).pack()

            def download():
                extension = '.jpg' if image_format == 'jpg' else f'.{image_format}'
                path = filedialog.asksaveasfilename(
                    defaultextension=extension,
                    initialfile=f'image{extension}',
                    filetypes=[(image_format.upper(), f'*{extension}'), ('All files', '*.*')]
                )
                if path:
                    try:
                        with open(path, 'wb') as output:
                            output.write(data)
                        append_text(f'[SYSTEM] Image saved to {path}')
                    except OSError as exc:
                        append_text(f'[ERROR] Could not save image: {exc}')

            tk.Button(block, text='Download', command=download).pack(pady=(4, 0), anchor='e' if tag == 'right' else 'w')
            remember_light_options(block)
            if dark_mode:
                apply_dark_theme(block)
            chat_text.window_create('end', window=block)
            chat_text.insert('end', '\n')
            chat_text.tag_add(tag, line_start, 'end-1c')
            chat_text.see('end')
            chat_text.configure(state='disabled')
        except (OSError, tk.TclError):
            append_text(f'[ERROR] Could not render image from {sender}.')
    root.after(0, append)

def send_host_image(path=None):
    if not context['allow_images']:
        append_text('[ERROR] Enable image sharing with /allowimgs first.')
        return
    if path is None and GUI_AVAILABLE:
        path = filedialog.askopenfilename(filetypes=FILE_TYPES)
    if not path:
        return
    now = time.time()
    while host_image_times and now - host_image_times[0] >= 60:
        host_image_times.popleft()
    if len(host_image_times) >= context['image_rate_limit']:
        append_text(f'[ERROR] Image rate limit reached ({context["image_rate_limit"]}/minute).')
        return
    try:
        clean, image_format = prepare_image(path)
    except (ImageError, OSError) as exc:
        append_text(f'[ERROR] {exc}')
        return
    host_image_times.append(now)
    recipients = public_directory()
    recipients.pop('host', None)
    if not recipients:
        append_text('[ERROR] No encrypted recipients are connected.')
        return
    encrypted = host_identity.encrypt_for(recipients, clean, 'image')
    broadcast(encrypted, kind='encrypted', sender_id='host', sender=context['username'],
              content_type='image', format=image_format)
    append_image(clean, context['username'], tag='right')

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


def process_host_message(message):
    message = message.strip()

    if not message:
        return

    if message.startswith('/image '):
        send_host_image(message[7:].strip().strip('"'))
        return
    result = handle_command(message, context, append_text)
    refresh_connected_count()

    if result:
        formatted = f'{context["username"]}: {result}'
        recipients = public_directory()
        recipients.pop('host', None)
        if recipients:
            broadcast(host_identity.encrypt_for(recipients, formatted.encode(), 'text'),
                      kind='encrypted', sender_id='host', sender=context['username'], content_type='text')
        append_text(formatted, tag='right')
    elif context.pop('clear_requested', False):
        broadcast(CLEAR_SIGNAL)
        clear_screen()

    if not context['running'] and GUI_AVAILABLE and root:
        try:
            root.quit()
        except tk.TclError:
            pass

def on_send_clicked(event=None):
    if not message_entry:
        return

    hide_command_suggestions()
    message = message_entry.get().strip()
    message_entry.delete(0, 'end')
    process_host_message(message)

def set_connected_ui(value):
    if not GUI_AVAILABLE or not root:
        return

    def update():
        if value:
            message_entry.config(state='normal')

            with clients_lock:
                user_count = len(clients)

            status_label.config(text=f'Host running | {user_count} users connected')
        else:
            message_entry.config(state='disabled')
            status_label.config(text='Host console active')

    try:
        root.after(0, update)
    except tk.TclError:
        pass

def remember_light_options(widget):
    options = {}

    for option in (
        'background',
        'foreground',
        'activebackground',
        'activeforeground',
        'insertbackground',
        'selectbackground',
        'selectforeground',
        'disabledforeground',
        'highlightbackground',
        'highlightcolor',
    ):
        try:
            options[option] = widget.cget(option)
        except tk.TclError:
            pass

    light_widget_options[widget] = options

    for child in widget.winfo_children():
        remember_light_options(child)


def configure_widget(widget, **options):
    for option, value in options.items():
        try:
            widget.configure(**{option: value})
        except tk.TclError:
            pass


def restore_light_theme(widget):
    defaults = light_widget_options.get(widget, {})

    if defaults:
        configure_widget(widget, **defaults)
    for child in widget.winfo_children():
        restore_light_theme(child)


def apply_dark_theme(widget):
    widget_class = widget.winfo_class()

    configure_widget(
        widget,
        background=DARK_THEME['bg'],
        foreground=DARK_THEME['text'],
        activebackground=DARK_THEME['button_active'],
        activeforeground=DARK_THEME['text'],
        insertbackground=DARK_THEME['text'],
        selectbackground=DARK_THEME['accent'],
        selectforeground=DARK_THEME['bg'],
        disabledforeground=DARK_THEME['disabled'],
        highlightbackground=DARK_THEME['border'],
        highlightcolor=DARK_THEME['accent'],
    )

    if widget_class in ('Frame', 'Labelframe'):
        configure_widget(widget, background=DARK_THEME['panel'])
    elif widget_class in ('Entry', 'Text', 'Listbox'):
        configure_widget(
            widget,
            background=DARK_THEME['field'],
            foreground=DARK_THEME['text'],
            insertbackground=DARK_THEME['text'],
        )
    elif widget_class == 'Button':
        configure_widget(
            widget,
            background=DARK_THEME['button'],
            foreground=DARK_THEME['text'],
            activebackground=DARK_THEME['button_active'],
            activeforeground=DARK_THEME['text'],
        )
    elif widget_class == 'Label':
        parent_background = DARK_THEME['bg']
        try:
            parent_background = widget.master.cget('background')
        except tk.TclError:
            pass
        configure_widget(widget, background=parent_background, foreground=DARK_THEME['muted'])
    elif widget_class == 'Scrollbar':
        configure_widget(
            widget,
            background=DARK_THEME['button'],
            activebackground=DARK_THEME['button_active'],
            troughcolor=DARK_THEME['field'],
        )
    
    for child in widget.winfo_children():
        apply_dark_theme(child)


def apply_theme():
    if not GUI_AVAILABLE or not root:
        return
    
    if dark_mode:
        apply_ttk_theme(True)
        apply_dark_theme(root)
        chat_text.tag_configure('left', justify='left', foreground=DARK_THEME['text'])
        chat_text.tag_configure('right', justify='right', foreground=DARK_THEME['self_message'])
        theme_button.config(text='Light Mode')
        shutdown_button.config(
            bg=DARK_THEME['danger'],
            fg=DARK_THEME['text'],
            activebackground=DARK_THEME['danger_active'],
            activeforeground=DARK_THEME['text'],
        )
    else:
        apply_ttk_theme(False)
        restore_light_theme(root)
        chat_text.tag_configure('left', justify='left', foreground='black')
        chat_text.tag_configure('right', justify='right', foreground='#0B5394')
        theme_button.config(text='Dark Mode')

def apply_ttk_theme(use_dark_mode):
    if not ttk_style:
        return
    if not use_dark_mode:
        if ttk_light_theme:
            ttk_style.theme_use(ttk_light_theme)
        return
    ttk_style.theme_use('clam')
    ttk_style.configure('TNotebook', background=DARK_THEME['bg'], borderwidth=0)
    ttk_style.configure(
        'TNotebook.Tab',
        background=DARK_THEME['button'],
        foreground=DARK_THEME['text'],
        padding=(14, 7),
        borderwidth=0,
    )
    ttk_style.map(
        'TNotebook.Tab',
        background=[('selected', DARK_THEME['accent']), ('active', DARK_THEME['button_active'])],
        foreground=[('selected', DARK_THEME['bg']), ('active', DARK_THEME['text'])],
    )
    ttk_style.configure(
        'Treeview',
        background=DARK_THEME['field'],
        fieldbackground=DARK_THEME['field'],
        foreground=DARK_THEME['text'],
        bordercolor=DARK_THEME['border'],
        rowheight=24,
    )
    ttk_style.map(
        'Treeview',
        background=[('selected', DARK_THEME['accent'])],
        foreground=[('selected', DARK_THEME['bg'])],
    )
    ttk_style.configure(
        'Treeview.Heading',
        background=DARK_THEME['button'],
        foreground=DARK_THEME['text'],
        bordercolor=DARK_THEME['border'],
        relief='flat',
    )
    ttk_style.map(
        'Treeview.Heading',
        background=[('active', DARK_THEME['button_active'])],
        foreground=[('active', DARK_THEME['text'])],
    )

def toggle_theme():
    global dark_mode
    dark_mode = not dark_mode
    apply_theme()

def update_command_suggestions(event=None):
    if not suggestion_list or not message_entry:
        return
    if event and event.keysym in ('Up', 'Down', 'Tab', 'Return', 'Escape'):
        return
    typed = message_entry.get()
    matches = [command.split()[0] for command, _ in HOST_COMMANDS if command.split()[0].startswith(typed)] if typed.startswith('/') else []
    suggestion_list.delete(0, 'end')
    for command in matches:
        suggestion_list.insert('end', command)
    if matches:
        suggestion_list.selection_set(0)
        suggestion_list.activate(0)
        suggestion_list.pack(fill='x', padx=10, before=message_entry.master)
    else:
        suggestion_list.pack_forget()

def move_command_selection(direction):
    if not suggestion_list or not suggestion_list.winfo_ismapped() or not suggestion_list.size():
        return
    current = suggestion_list.curselection()
    index = current[0] if current else 0
    index = (index + direction) % suggestion_list.size()
    suggestion_list.selection_clear(0, 'end')
    suggestion_list.selection_set(index)
    suggestion_list.activate(index)
    suggestion_list.see(index)

def autocomplete_command(event=None):
    if not suggestion_list or not suggestion_list.winfo_ismapped():
        return None
    selected = suggestion_list.curselection()
    if not selected:
        return 'break'
    command = suggestion_list.get(selected[0])
    message_entry.delete(0, 'end')
    message_entry.insert(0, command + ' ')
    message_entry.icursor('end')
    suggestion_list.pack_forget()
    return 'break'

def command_key_up(event=None):
    move_command_selection(-1)
    return 'break' if suggestion_list and suggestion_list.winfo_ismapped() else None

def command_key_down(event=None):
    move_command_selection(1)
    return 'break' if suggestion_list and suggestion_list.winfo_ismapped() else None

def hide_command_suggestions(event=None):
    if suggestion_list:
        suggestion_list.pack_forget()
    return 'break'

def accept_clients():
    global next_client_id

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

def build_server_gui():
    global root, chat_text, message_entry, status_label, send_button, shutdown_button, theme_button, image_button, clients_tree, suggestion_list, ttk_style, ttk_light_theme

    root = tk.Tk()
    ttk_style = ttk.Style(root)
    ttk_light_theme = ttk_style.theme_use()
    root.title('Chat Host')
    root.geometry('620x520')

    top_frame = tk.Frame(root)
    top_frame.pack(fill='x', padx=10, pady=(10, 0))

    status_label = tk.Label(top_frame, text='Host console active', anchor='w')
    status_label.pack(side='left', fill='x', expand=True)

    theme_button = tk.Button(top_frame, text='Dark Mode', width=12, command=toggle_theme)
    theme_button.pack(side='right', padx=(10, 0))

    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=10, pady=10)
    chat_frame = tk.Frame(notebook)
    commands_frame = tk.Frame(notebook)
    clients_frame = tk.Frame(notebook)
    notebook.add(chat_frame, text='Chat')
    notebook.add(clients_frame, text='Clients')
    notebook.add(commands_frame, text='Commands')
    chat_text = ScrolledText(chat_frame, state='disabled', wrap='word')
    chat_text.pack(fill='both', expand=True)
    chat_text.tag_configure('left', justify='left', foreground='black')
    chat_text.tag_configure('right', justify='right', foreground='#0B5394')

    clients_tree = ttk.Treeview(
        clients_frame,
        columns=('id', 'uuid', 'username'),
        show='headings',
        selectmode='browse',
    )
    clients_tree.heading('id', text='ID')
    clients_tree.heading('uuid', text='UUID')
    clients_tree.heading('username', text='Username')
    clients_tree.column('id', width=50, stretch=False, anchor='center')
    clients_tree.column('uuid', width=245, stretch=True)
    clients_tree.column('username', width=190, stretch=True)
    clients_tree.pack(fill='both', expand=True, padx=8, pady=(8, 4))
    client_actions = tk.Frame(clients_frame)
    client_actions.pack(fill='x', padx=8, pady=(4, 8))
    tk.Button(client_actions, text='Refresh', command=refresh_connected_count).pack(side='left')
    tk.Button(client_actions, text='Kick Selected', command=kick_selected_client).pack(side='right')

    commands_text = ScrolledText(commands_frame, state='normal', wrap='word', padx=12, pady=12)
    commands_text.pack(fill='both', expand=True)
    commands_text.insert('end', 'Host commands\n\n')
    for command, description in HOST_COMMANDS:
        commands_text.insert('end', f'{command}\n    {description}\n\n')
    commands_text.configure(state='disabled')

    suggestion_list = tk.Listbox(root, height=6, exportselection=False)
    suggestion_list.bind('<Double-Button-1>', autocomplete_command)
    input_frame = tk.Frame(root)
    input_frame.pack(fill='x', padx=10, pady=(0, 10))

    message_entry = tk.Entry(input_frame, state='disabled')
    message_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
    message_entry.bind('<Return>', on_send_clicked)
    message_entry.bind('<KeyRelease>', update_command_suggestions)
    message_entry.bind('<Up>', command_key_up)
    message_entry.bind('<Down>', command_key_down)
    message_entry.bind('<Tab>', autocomplete_command)
    message_entry.bind('<Escape>', hide_command_suggestions)

    send_button = tk.Button(input_frame, text='Send', width=12, command=on_send_clicked)
    send_button.pack(side='left')
    image_button = tk.Button(input_frame, text='Image', width=10, command=send_host_image)
    image_button.pack(side='left', padx=(5, 0))

    shutdown_button = tk.Button(root, text='Shutdown Server', fg='white', bg='#d9534f', command=on_close)
    shutdown_button.pack(fill='x', padx=10, pady=(0, 10))

    root.protocol('WM_DELETE_WINDOW', on_close)
    remember_light_options(root)
    apply_theme()
    set_connected_ui(True)
    append_text(f'[SERVER] Listening on {HOST}:{PORT}')
    append_text('Host GUI active. Type a message and press Send. Use "/help" to see available commands.')
    root.mainloop()

def on_close():
    context['running'] = False
    shutdown_server()

    if root:
        root.destroy()

def send_messages():
    while context['running']:
        try:
            message = input('')

        except (EOFError, KeyboardInterrupt):
            context['running'] = False
            break

        if message.startswith('/image '):
            send_host_image(message[7:].strip().strip('"'))
            continue

        result = handle_command(message, context)

        if result:
            formatted = f'{context["username"]}: {result}'

            recipients = public_directory()
            recipients.pop('host', None)
            if recipients:
                broadcast(host_identity.encrypt_for(recipients, formatted.encode(), 'text'),
                          kind='encrypted', sender_id='host', sender=context['username'], content_type='text')
        elif context.pop('clear_requested', False):
            broadcast(CLEAR_SIGNAL)

    shutdown_server()

if GUI_AVAILABLE:
    accept_thread = threading.Thread(target=accept_clients, daemon=True)
    accept_thread.start()
    build_server_gui()
else:
    host_thread = threading.Thread(
        target=send_messages
    )
    host_thread.start()
    accept_clients()
