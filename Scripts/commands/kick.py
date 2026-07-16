def kick(args, context, output_func=print):
    if not context.get('is_host'):
        output_func('[ERROR] Only the host can use this command.')
        return

    if not args:
        output_func('Usage: /kick <id|uuid>')
        return

    selector = args[0].strip().lower()

    clients = context.get('clients', [])
    clients_lock = context.get('clients_lock')

    if not clients_lock:
        output_func('[ERROR] Client management lock is not available.')
        return

    matches = []
    with clients_lock:
        for c in clients:
            client_uuid = str(c.get('uuid', '')).lower()
            if selector == str(c['id']) or (client_uuid and client_uuid.startswith(selector)):
                matches.append(c)

    if not matches:
        output_func(f'[ERROR] No user matches {args[0]!r}. Use /see_users to list clients.')
        return
    if len(matches) > 1:
        output_func('[ERROR] UUID prefix is ambiguous. Enter more UUID characters.')
        return
    kicked_client = matches[0]

    try:
        from protocol import send_text
        send_lock = kicked_client.get('send_lock')
        if send_lock:
            with send_lock:
                send_text(kicked_client['socket'], '[SERVER] You have been kicked by the host.')
        else:
            send_text(kicked_client['socket'], '[SERVER] You have been kicked by the host.')
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

    output_func(
        f'[SYSTEM] Kicked user: {kicked_client["username"]} '
        f'(ID: {kicked_client["id"]}, UUID: {kicked_client.get("uuid", "unknown")})'
    )
