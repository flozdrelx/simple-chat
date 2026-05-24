def host(args, context, output_func=print):
    address = context.get('share_address')
    port = context.get('port')
    if context.get('is_host'):
        if address:
            output_func(f'[SHARE] Server address: {address}')
        elif port:
            output_func('[SHARE] Start a tunnel, then share the tunnel address shown by that service.')
        else:
            output_func('[ERROR] Connection details not available.')
    else:
        output_func('[INFO] Connected to server.')