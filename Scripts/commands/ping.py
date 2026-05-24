import time

def ping(args, context, output_func=print):
    if context['is_host']:
        output_func('[SYSTEM] You are the host. Ping is not applicable.')
        return

    if not context.get('chat_running') or not context.get('client'):
        output_func('[ERROR] You must be connected to a server to use /ping.')
        return

    client = context['client']
    try:
        sent_time = time.time()
        client.send(f'__PING__:{sent_time}'.encode())
    except OSError:
        output_func('[ERROR] Failed to send ping request.')