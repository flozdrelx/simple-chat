def help(args, context):
    help_msg = '''
Current commands:

    * /help             -  Shows this message
    * /exit             -  Leave or close the chat
    * /clear            -  Clear the chat (host only)
    * /set_user <user>  -  Set your username
    * /host             -  Show server connection address
    * /disconnect       -  Disconnect from server (client only)
    * /ping             -  Check your ping to the server
'''

    print(help_msg)