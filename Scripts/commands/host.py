def host(args, context):
    address = context.get('share_address')
    port = context.get('port')
    if context.get('is_host'):
        if address:
            print(f'[SHARE] Server address: {address}')
        elif port:
            print('[SHARE] Start a tunnel, then share the tunnel address shown by that service.')
        else:
            print('[ERROR] Connection details not available.')
    else:
        print('[INFO] Connected to server.')