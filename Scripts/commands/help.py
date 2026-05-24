def help(args, context):
    help_msg = '''
Current commands:

    * /help                       -  Shows this message
    * /exit                       -  Leave or close the chat
    * /set_user <user>            -  Set your username
    * /host                       -  Show safe server sharing info
    * /disconnect                 -  Disconnect from server (client only)
    * /ping                       -  Check your ping to the server
'''
    if context.get('is_host'):
        help_msg += '''
Host Administration commands:

    * /clear                      -  Clear the chat (host only)
    * /see_users                  -  List all connected users
    * /kick <userid>              -  Kick a user by ID
    * /set_pswd <password>        -  Set/change server password (empty to clear)
'''

    print(help_msg)