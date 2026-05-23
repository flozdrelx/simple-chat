def set_pswd(args, context):
    if not context.get('is_host'):
        print('[ERROR] Only the host can use this command.')
        return

    if not args:
        context['password'] = ''
        print('[SYSTEM] Server password has been cleared.')
        return

    password = " ".join(args)
    context['password'] = password
    print(f'[SYSTEM] Server password set to: {password}')