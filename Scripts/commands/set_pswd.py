def set_pswd(args, context, output_func=print):
    if not context.get('is_host'):
        output_func('[ERROR] Only the host can use this command.')
        return

    if not args:
        context['password'] = ''
        output_func('[SYSTEM] Server password has been cleared.')
        return

    password = " ".join(args)
    context['password'] = password
    output_func(f'[SYSTEM] Server password set to: {password}')