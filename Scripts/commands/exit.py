def exit(args, context, output_func=print):
    if context['is_host']:
        output_func('[SERVER] shutting down...')
    else:
        output_func('[CLIENT] Disconnecting...')

    context['running'] = False