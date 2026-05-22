def set_user(args, context):
    if not args:
        print('Usage: /set_user <username>')
        return

    username = args[0]

    context['username'] = username

    print(f'Username changed to {username}')