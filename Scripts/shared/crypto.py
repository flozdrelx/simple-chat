"""Client-side E2EE orchestration. Network envelopes contain public data only."""
import base64
import json
import os
from pathlib import Path

try:
    import hexium_crypto as _rust
except ImportError as exc:
    raise RuntimeError(
        'Rust crypto module is unavailable. Run: python -m pip install ./rust-crypto'
    ) from exc


class CryptoError(ValueError):
    pass


def _b64(data):
    return base64.b64encode(bytes(data)).decode('ascii')


def _unb64(data):
    return base64.b64decode(data, validate=True)


def load_or_create_identity(path=None):
    path = Path(path or Path.home() / '.hexium-chat' / 'identity.key')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        private = _unb64(path.read_text(encoding='ascii').strip())
        public = bytes(_rust.public_from_private(private))
    else:
        private, public = map(bytes, _rust.generate_identity())
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, 'O_BINARY'): flags |= os.O_BINARY
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'w', encoding='ascii') as stream:
            stream.write(_b64(private))
    return Identity(private, public)


class Identity:
    def __init__(self, private_key, public_key):
        self._private = bytes(private_key)
        self.public_key = bytes(public_key)

    @property
    def public_b64(self):
        return _b64(self.public_key)

    @property
    def fingerprint(self):
        return _rust.public_key_fingerprint(self.public_key)

    def _key(self, peer_public_b64):
        return bytes(_rust.complete_handshake(self._private, _unb64(peer_public_b64)))

    def encrypt_for(self, recipients, plaintext, content_type):
        aad = ('hexium-v1:' + content_type).encode()
        content_key = os.urandom(32)
        body_nonce, body_ciphertext = _rust.encrypt_bytes(content_key, plaintext, aad)
        boxes = {}
        for peer_id, public_key in recipients.items():
            nonce, ciphertext = _rust.encrypt_bytes(self._key(public_key), content_key, aad + b':key')
            boxes[peer_id] = {'nonce': _b64(nonce), 'ciphertext': _b64(ciphertext)}
        return json.dumps({'v': 1, 'type': content_type, 'nonce': _b64(body_nonce),
                           'ciphertext': _b64(body_ciphertext), 'boxes': boxes},
                          separators=(',', ':')).encode()

    def decrypt_envelope(self, own_id, sender_public, payload):
        try:
            envelope = json.loads(payload)
            box = envelope['boxes'][own_id]
            content_type = envelope['type']
            aad = ('hexium-v1:' + content_type).encode()
            content_key = _rust.decrypt_bytes(self._key(sender_public), _unb64(box['nonce']),
                                              _unb64(box['ciphertext']), aad + b':key')
            plain = _rust.decrypt_bytes(content_key, _unb64(envelope['nonce']),
                                        _unb64(envelope['ciphertext']), aad)
            return content_type, bytes(plain)
        except Exception as exc:
            raise CryptoError('Encrypted payload could not be authenticated.') from exc
