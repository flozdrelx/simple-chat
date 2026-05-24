def see_users(args, context, output_func=print):
    if not context.get('is_host'):
        output_func('[ERROR] Only the host can use this command.')
        return

    clients = context.get('clients', [])
    clients_lock = context.get('clients_lock')

    if not clients_lock:
        output_func('[ERROR] Client management lock is not available.')
        return

    with clients_lock:
        if not clients:
            output_func('[SYSTEM] No users are currently connected.')
            return

        output_func('\n=== Connected Users ===')
        for c in clients:
            output_func(f"ID: {c['id']} | Username: {c['username']}")
        output_func('=======================\n')