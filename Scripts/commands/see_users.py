def see_users(args, context):
    if not context.get('is_host'):
        print('[ERROR] Only the host can use this command.')
        return

    clients = context.get('clients', [])
    clients_lock = context.get('clients_lock')

    if not clients_lock:
        print('[ERROR] Client management lock is not available.')
        return

    with clients_lock:
        if not clients:
            print('[SYSTEM] No users are currently connected.')
            return

        print('\n=== Connected Users ===')
        for c in clients:
            print(f"ID: {c['id']} | Username: {c['username']} | Address: {c['address'][0]}:{c['address'][1]}")
        print('=======================\n')