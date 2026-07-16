def imglimit(args, context, output_func=print):
    if not context.get('is_host'):
        output_func('[ERROR] Only the host can use this command.')
        return
    if len(args) != 1:
        output_func('[ERROR] Usage: /imglimit <images-per-minute>')
        return
    try:
        limit = int(args[0])
        if not 1 <= limit <= 60:
            raise ValueError
    except ValueError:
        output_func('[ERROR] Image limit must be from 1 to 60.')
        return
    context['image_rate_limit'] = limit
    output_func(f'[SYSTEM] Image rate limit set to {limit} per minute per user.')
