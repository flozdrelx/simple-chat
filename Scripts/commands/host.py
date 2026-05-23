def host(args, context):
    ip = context.get('ip')
    port = context.get('port')
    if ip and port:
        if context.get('is_host'):
            print(f'[SHARE] Server address: {ip}:{port}')
        else:
            print(f'[INFO] Connected to server: {ip}:{port}')
    else:
        print('[ERROR] Connection details not available.')
