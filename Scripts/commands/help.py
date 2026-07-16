def help(args, context, output_func=print):
    help_msg = '''
Current commands:

    * /help                       -  Shows this message
    * /exit                       -  Leave or close the chat
    * /set_user <user>            -  Set your username
    * /host                       -  Show safe server sharing info
    * /disconnect                 -  Disconnect from server (client only)
    * /ping                       -  Check your ping to the server
    * /image <path>               -  Send a PNG, JPG, or WEBP image
'''
    if context.get('is_host'):
        help_msg += '''
Host Administration commands:

    * /clear                      -  Clear the chat (host only)
    * /see_users                  -  List connected users with IDs and UUIDs
    * /kick <id|uuid>             -  Kick by ID or a unique UUID prefix
    * /set_pswd <password>        -  Set/change server password (empty to clear)
    * /allowimgs                  -  Enable/disable image sharing
    * /imglimit <count>           -  Set images/minute/user (1-60)
'''

    output_func(help_msg)
