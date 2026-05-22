def exit(args, context):
    if context['is_host']:
        print('[SERVER] shutting down...')
    else:
        print('[CLIENT] Disconnecting...')

    context['running'] = False