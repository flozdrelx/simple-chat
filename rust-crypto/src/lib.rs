use chacha20poly1305::{aead::{Aead, KeyInit, OsRng}, XChaCha20Poly1305, XNonce};
use hkdf::Hkdf;
use pyo3::{exceptions::PyValueError, prelude::*};
use rand_core::RngCore;
use sha2::{Digest, Sha256};
use x25519_dalek::{PublicKey, StaticSecret};
use zeroize::Zeroizing;

const INFO: &[u8] = b"hexium-chat/session/v1";

fn exact32(value: &[u8], label: &str) -> PyResult<[u8; 32]> {
    value.try_into().map_err(|_| PyValueError::new_err(format!("{label} must be 32 bytes")))
}

#[pyfunction]
fn generate_identity() -> (Vec<u8>, Vec<u8>) {
    let secret = StaticSecret::random_from_rng(OsRng);
    let public = PublicKey::from(&secret);
    (secret.to_bytes().to_vec(), public.as_bytes().to_vec())
}

#[pyfunction]
fn public_from_private(private_key: &[u8]) -> PyResult<Vec<u8>> {
    let secret = StaticSecret::from(exact32(private_key, "private key")?);
    Ok(PublicKey::from(&secret).as_bytes().to_vec())
}

#[pyfunction]
fn public_key_fingerprint(public_key: &[u8]) -> String {
    let digest = Sha256::digest(public_key);
    digest[..10].iter().map(|b| format!("{b:02x}")).collect::<Vec<_>>().join(":")
}

#[pyfunction]
fn complete_handshake(private_key: &[u8], peer_public_key: &[u8]) -> PyResult<Vec<u8>> {
    let private = Zeroizing::new(exact32(private_key, "private key")?);
    let secret = StaticSecret::from(*private);
    let peer = PublicKey::from(exact32(peer_public_key, "public key")?);
    let shared = Zeroizing::new(secret.diffie_hellman(&peer).to_bytes());
    let mut key = Zeroizing::new([0u8; 32]);
    Hkdf::<Sha256>::new(None, shared.as_ref()).expand(INFO, key.as_mut())
        .map_err(|_| PyValueError::new_err("key derivation failed"))?;
    Ok(key.to_vec())
}

#[pyfunction]
fn encrypt_bytes(key: &[u8], plaintext: &[u8], aad: &[u8]) -> PyResult<(Vec<u8>, Vec<u8>)> {
    let cipher = XChaCha20Poly1305::new_from_slice(key).map_err(|_| PyValueError::new_err("key must be 32 bytes"))?;
    let mut nonce = [0u8; 24];
    OsRng.fill_bytes(&mut nonce);
    let ciphertext = cipher.encrypt(XNonce::from_slice(&nonce), chacha20poly1305::aead::Payload { msg: plaintext, aad })
        .map_err(|_| PyValueError::new_err("encryption failed"))?;
    Ok((nonce.to_vec(), ciphertext))
}

#[pyfunction]
fn decrypt_bytes(key: &[u8], nonce: &[u8], ciphertext: &[u8], aad: &[u8]) -> PyResult<Vec<u8>> {
    if nonce.len() != 24 { return Err(PyValueError::new_err("nonce must be 24 bytes")); }
    let cipher = XChaCha20Poly1305::new_from_slice(key).map_err(|_| PyValueError::new_err("key must be 32 bytes"))?;
    cipher.decrypt(XNonce::from_slice(nonce), chacha20poly1305::aead::Payload { msg: ciphertext, aad })
        .map_err(|_| PyValueError::new_err("ciphertext authentication failed"))
}

#[pymodule]
fn hexium_crypto(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate_identity, module)?)?;
    module.add_function(wrap_pyfunction!(public_from_private, module)?)?;
    module.add_function(wrap_pyfunction!(public_key_fingerprint, module)?)?;
    module.add_function(wrap_pyfunction!(complete_handshake, module)?)?;
    module.add_function(wrap_pyfunction!(encrypt_bytes, module)?)?;
    module.add_function(wrap_pyfunction!(decrypt_bytes, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn round_trip_tamper_wrong_key_and_nonce_uniqueness() {
        let (a, ap) = generate_identity(); let (b, bp) = generate_identity(); let (c, _) = generate_identity();
        let ab = complete_handshake(&a, &bp).unwrap();
        let ba = complete_handshake(&b, &ap).unwrap();
        let ca = complete_handshake(&c, &ap).unwrap();
        assert_eq!(ab, ba);
        let (n1, ct) = encrypt_bytes(&ab, b"hello", b"text").unwrap();
        let (n2, _) = encrypt_bytes(&ab, b"hello", b"text").unwrap();
        assert_ne!(n1, n2);
        assert_eq!(decrypt_bytes(&ba, &n1, &ct, b"text").unwrap(), b"hello");
        assert!(decrypt_bytes(&ca, &n1, &ct, b"text").is_err());
        let mut altered = ct; altered[0] ^= 1;
        assert!(decrypt_bytes(&ba, &n1, &altered, b"text").is_err());
    }
}