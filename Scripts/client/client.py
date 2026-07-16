import socket
import threading
import os
import sys
import time
from urllib.parse import urlparse
import io

try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText
    from tkinter import filedialog
    from PIL import Image, ImageTk
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
from protocol import recv_frame, send_frame, send_text
from images import prepare_image, ImageError, FILE_TYPES
from crypto import load_or_create_identity, CryptoError

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
    'client': None,
    'peers': {}
}
identity = load_or_create_identity()

root = None
chat_text = None
message_entry = None
connect_button = None
disconnect_button = None
status_label = None
address_entry = None
password_entry = None
send_button = None
theme_button = None
image_button = None
image_refs = []
send_lock = threading.Lock()
suggestion_list = None
ttk_style = None
ttk_light_theme = None

CLIENT_COMMANDS = [
    ('/help', 'Show all available commands'),
    ('/exit', 'Close the application'),
    ('/set_user <user>', 'Change your username'),
    ('/host', 'Show safe server sharing information'),
    ('/disconnect', 'Disconnect from the server'),
    ('/ping', 'Check latency to the server'),
    ('/image <path>', 'Send a PNG, JPG, or WEBP image'),
]

def send_client_text(message):
    if not client:
        raise OSError('Not connected')
    with send_lock:
        send_text(client, message)
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
}

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

def send_image(path=None):
    if not client or not context['chat_running']:
        append_text('[ERROR] Not connected to a server.')
        return
    if path is None and GUI_AVAILABLE:
        path = filedialog.askopenfilename(filetypes=FILE_TYPES)
    if not path:
        return
    try:
        clean, image_format = prepare_image(path)
        recipients = dict(context.get('peers', {}))
        if not recipients:
            append_text('[ERROR] No encrypted recipients are connected.')
            return
        encrypted = identity.encrypt_for(recipients, clean, 'image')
        with send_lock:
            send_frame(client, 'encrypted', encrypted, content_type='image', format=image_format)
        append_image(clean, context['username'], tag='right')
    except (ImageError, OSError, ValueError) as exc:
        append_text(f'[ERROR] {exc}')

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
            image_button.config(state='normal')
            status_label.config(text=f'Connected as {context["username"]}')
        else:
            connect_button.config(state='normal')
            address_entry.config(state='normal')
            password_entry.config(state='normal')
            disconnect_button.config(state='disabled')
            message_entry.config(state='disabled')
            image_button.config(state='disabled')
            status_label.config(text='Disconnected')
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
    matches = [command.split()[0] for command, _ in CLIENT_COMMANDS if command.split()[0].startswith(typed)] if typed.startswith('/') else []
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

def receive_messages():
    global connected

    while context['chat_running']:
        try:
            header, payload = recv_frame(client)
        except socket.timeout:
            continue
        except (OSError, ValueError, ConnectionError):
            break

        kind = header.get('kind')
        if kind == 'peer_joined':
            context['peers'][header['peer_id']] = header['public_key']
            continue
        if kind == 'peer_left':
            context['peers'].pop(header.get('peer_id'), None)
            continue
        if kind == 'encrypted':
            try:
                sender_key = context['peers'][header['sender_id']]
                content_type, plain = identity.decrypt_envelope(context['client_uuid'], sender_key, payload)
                if content_type == 'image':
                    append_image(plain, header.get('sender', 'Unknown'))
                elif content_type == 'text':
                    append_text(plain.decode('utf-8'))
            except (CryptoError, KeyError, UnicodeDecodeError):
                append_text('[ERROR] Encrypted payload could not be authenticated.')
            continue
        if header.get('kind') != 'text':
            continue
        try:
            message = payload.decode('utf-8')
        except UnicodeDecodeError:
            continue

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
    
    if message.startswith('/image '):
        send_image(message[7:].strip().strip('"'))
        return
    result = handle_command(message, context, append_text)

    if result:
        if not client:
            append_text('[ERROR] Not connected to a server.')
            return
        
        formatted = f'{context["username"]}: {result}'
        append_text(formatted, tag='right')

        try:
            with send_lock:
                recipients = dict(context.get('peers', {}))
                if not recipients:
                    raise CryptoError('No recipients')
                encrypted = identity.encrypt_for(recipients, formatted.encode(), 'text')
                send_frame(client, 'encrypted', encrypted, content_type='text')
        except (OSError, CryptoError):
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
        send_frame(client, 'control', f'__AUTH__:{password}', public_key=identity.public_b64)
    except OSError as e:
        append_text(f'[ERROR] Failed to send authentication: {e}')
        client.close()
        client = None
        set_connected_ui(False)
        return
    try:
        header, payload = recv_frame(client)
    except (OSError, socket.timeout, ValueError, ConnectionError) as e:
        append_text(f'[ERROR] Failed to complete server handshake: {e}')
        client.close()
        client = None
        set_connected_ui(False)
        return
    
    if header.get('kind') == 'welcome':
        context['username'] = header.get('username', 'Client')
        context['client_uuid'] = header['client_uuid']
        context['peers'] = dict(header.get('peers', {}))
    elif header.get('kind') == 'text':
        initial_message = payload.decode('utf-8', errors='replace')
        append_text(initial_message)
        client.close()
        client = None
        set_connected_ui(False)
        return
    else:
        append_text('[ERROR] Invalid server handshake.')
        client.close()
        client = None
        set_connected_ui(False)
        return
    
    client.settimeout(None)
    connected = True
    context['chat_running'] = True
    context['port'] = port
    context['client'] = client
    context['send_text'] = send_client_text
    clear_screen()
    append_text('[CONNECTED] Connected to server.')
    append_text(f'[SECURITY] Your public-key fingerprint is {identity.fingerprint}')
    append_text(f'[SYSTEM] Your username is {context["username"]}, use "/help" to see available commands.')
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
    global root, chat_text, message_entry, connect_button, disconnect_button, status_label, address_entry, password_entry, send_button, theme_button, image_button, suggestion_list, ttk_style, ttk_light_theme
    
    root = tk.Tk()
    ttk_style = ttk.Style(root)
    ttk_light_theme = ttk_style.theme_use()
    root.title('Chat Client')
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
    connect_button.grid(row=0, column=2, padx=(10, 0))
    theme_button = tk.Button(connect_frame, text='Dark Mode', width=12, command=toggle_theme)
    theme_button.grid(row=1, column=2, padx=(10, 0), pady=(5, 0))
    status_label = tk.Label(root, text='Disconnected', anchor='w')
    status_label.pack(fill='x', padx=10)
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=10, pady=(5, 0))
    chat_frame = tk.Frame(notebook)
    commands_frame = tk.Frame(notebook)
    notebook.add(chat_frame, text='Chat')
    notebook.add(commands_frame, text='Commands')
    chat_text = ScrolledText(chat_frame, state='disabled', wrap='word')
    chat_text.pack(fill='both', expand=True)
    chat_text.tag_configure('left', justify='left', foreground='black')
    chat_text.tag_configure('right', justify='right', foreground='#0B5394')
    commands_text = ScrolledText(commands_frame, state='normal', wrap='word', padx=12, pady=12)
    commands_text.pack(fill='both', expand=True)
    commands_text.insert('end', 'Client commands\n\n')
    for command, description in CLIENT_COMMANDS:
        commands_text.insert('end', f'{command}\n    {description}\n\n')
    commands_text.configure(state='disabled')
    suggestion_list = tk.Listbox(root, height=5, exportselection=False)
    suggestion_list.bind('<Double-Button-1>', autocomplete_command)
    input_frame = tk.Frame(root)
    input_frame.pack(fill='x', padx=10, pady=10)
    message_entry = tk.Entry(input_frame, state='disabled')
    message_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
    message_entry.bind('<Return>', on_send_clicked)
    message_entry.bind('<KeyRelease>', update_command_suggestions)
    message_entry.bind('<Up>', command_key_up)
    message_entry.bind('<Down>', command_key_down)
    message_entry.bind('<Tab>', autocomplete_command)
    message_entry.bind('<Escape>', hide_command_suggestions)
    send_button = tk.Button(input_frame, text='Send', width=10, command=lambda: [process_user_message(message_entry.get()), message_entry.delete(0, 'end')])
    send_button.pack(side='left')
    image_button = tk.Button(input_frame, text='Image', width=10, state='disabled', command=send_image)
    image_button.pack(side='left', padx=(5, 0))
    disconnect_button = tk.Button(root, text='Disconnect', state='disabled', command=disconnect)
    disconnect_button.pack(fill='x', padx=10, pady=(0, 10))
    root.protocol('WM_DELETE_WINDOW', on_close)
    remember_light_options(root)
    apply_theme()
    set_connected_ui(False)
    append_text('Enter an address or tunnel and click Connect.')
    root.mainloop()

def on_send_clicked(event=None):
    if not message_entry:
        return

    hide_command_suggestions()
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
