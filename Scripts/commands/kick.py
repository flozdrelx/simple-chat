def kick(args, context):
    if not context.get('is_host'):
        print('[ERROR] Only the host can use this command.')
        return

    if not args:
        print('Usage: /kick <userid>')
        return

    try:
        kick_id = int(args[0])
    except ValueError:
        print('[ERROR] Input a valid integer for userid.')
        return

    clients = context.get('clients', [])
    clients_lock = context.get('clients_lock')

    if not clients_lock:
        print('[ERROR] Client management lock is not available.')
        return

    kicked_client = None
    with clients_lock:
        for c in clients:
            if c['id'] == kick_id:
                kicked_client = c
                break

    if not kicked_client:
        print(f'[ERROR] User with ID {kick_id} not found.')
        return

    try:
        kicked_client['socket'].send('[SERVER] You have been kicked by the host.'.encode())
    except OSError:
        pass

    import time
    time.sleep(0.1)

    try:
        kicked_client['socket'].close()
    except OSError:
        pass

    # Safe removal from active list
    with clients_lock:
        if kicked_client in clients:
            clients.remove(kicked_client)

    print(f'[SYSTEM] Kicked user: {kicked_client["username"]} (ID: {kick_id})')