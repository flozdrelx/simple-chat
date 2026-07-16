def allowimgs(args, context, output_func=print):
    if not context.get('is_host'):
        output_func('[ERROR] Only the host can use this command.')
        return
    context['allow_images'] = not context.get('allow_images', False)
    state = 'enabled' if context['allow_images'] else 'disabled'
    output_func(f'[SYSTEM] Image sharing {state}.')
    context['broadcast_system'](f'Image sharing is now {state} by the host.')
