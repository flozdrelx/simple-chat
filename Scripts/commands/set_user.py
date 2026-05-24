def set_user(args, context, output_func=print):
    if not args:
        output_func('Usage: /set_user <username>')
        return

    username = args[0]

    context['username'] = username

    client = context.get('client')
    if client:
        try:
            client.send(f'__CHANGE_USERNAME__:{username}'.encode())
        except OSError:
            pass

    output_func(f'Username changed to {username}')