def set_user(args, context):
    if not args:
        print('Usage: /set_user <username>')
        return

    username = args[0]

    context['username'] = username

    client = context.get('client')
    if client:
        try:
            client.send(f'__CHANGE_USERNAME__:{username}'.encode())
        except OSError:
            pass

    print(f'Username changed to {username}')