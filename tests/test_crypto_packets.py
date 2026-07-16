import base64
import importlib
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath('Scripts/shared'))

try:
    import hexium_crypto
except ImportError:
    hexium_crypto = None


@unittest.skipIf(hexium_crypto is None, 'build rust-crypto before integration tests')
class CryptoPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crypto = importlib.import_module('crypto')

    def identities(self):
        a_priv, a_pub = map(bytes, self.crypto._rust.generate_identity())
        b_priv, b_pub = map(bytes, self.crypto._rust.generate_identity())
        return (a_priv, self.crypto.Identity(a_priv, a_pub)), (b_priv, self.crypto.Identity(b_priv, b_pub))

    def test_private_key_is_not_serialized(self):
        (a_private, sender), (b_private, receiver) = self.identities()
        packet = sender.encrypt_for({'b': receiver.public_b64}, b'secret', 'text')
        self.assertNotIn(base64.b64encode(a_private), packet)
        self.assertNotIn(base64.b64encode(b_private), packet)
        self.assertNotIn(b'private', packet)

    def test_envelope_round_trip_and_tamper_rejection(self):
        (_, sender), (_, receiver) = self.identities()
        packet = sender.encrypt_for({'b': receiver.public_b64}, b'hello', 'text')
        self.assertEqual(receiver.decrypt_envelope('b', sender.public_b64, packet), ('text', b'hello'))
        altered = json.loads(packet)
        raw = bytearray(base64.b64decode(altered['ciphertext']))
        raw[0] ^= 1
        altered['ciphertext'] = base64.b64encode(raw).decode()
        with self.assertRaises(self.crypto.CryptoError):
            receiver.decrypt_envelope('b', sender.public_b64, json.dumps(altered).encode())


if __name__ == '__main__':
    unittest.main()