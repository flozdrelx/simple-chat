import os

CLEAR_SIGNAL = '__CLEAR_CHAT__'

def clear(args, context, output_func=print):
    if not context['is_host']:
        output_func('Only the host can clear the chat.')
        return

    os.system('cls' if os.name == 'nt' else 'clear')
    context['clear_requested'] = True