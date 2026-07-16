import json
import struct


MAX_FRAME_SIZE = 8 * 1024 * 1024


def _recv_exact(sock, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError('Connection closed while receiving data')
        chunks.append(chunk)
        remaining -= len(chunk)
    return b''.join(chunks)


def send_frame(sock, kind, payload=b'', **metadata):
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    header = json.dumps({'kind': kind, **metadata}, separators=(',', ':')).encode('utf-8')
    body = struct.pack('!I', len(header)) + header + payload
    if len(body) > MAX_FRAME_SIZE:
        raise ValueError('Frame is too large')
    sock.sendall(struct.pack('!I', len(body)) + body)


def recv_frame(sock):
    size = struct.unpack('!I', _recv_exact(sock, 4))[0]
    if size < 4 or size > MAX_FRAME_SIZE:
        raise ValueError('Invalid frame size')
    body = _recv_exact(sock, size)
    header_size = struct.unpack('!I', body[:4])[0]
    if header_size > len(body) - 4:
        raise ValueError('Invalid frame header')
    header = json.loads(body[4:4 + header_size].decode('utf-8'))
    return header, body[4 + header_size:]


def send_text(sock, message):
    send_frame(sock, 'text', message)
