import socket

HOST = '127.0.0.1'
PORT = 6667

client = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

client.connect((HOST, PORT))

print('[CLIENT] Connected successfully!')