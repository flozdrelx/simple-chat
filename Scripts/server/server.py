import socket

HOST = '0.0.0.0'
PORT = 6667

server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

server.bind((HOST, PORT))
server.listen()

print(f'[SERVER] Listening on port {PORT}...')

client, address = server.accept()

print(f'[CONNECTED] {address}')