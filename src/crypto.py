"""Symmetric encryption utilities using Fernet."""

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_SALT_SIZE = 16
_KDF_ITERATIONS = 10_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a Fernet-compatible key from a password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_bytes(plaintext: bytes, password: str) -> bytes:
    """Encrypt plaintext; returns salt || ciphertext."""
    salt = os.urandom(_SALT_SIZE)
    key = _derive_key(password, salt)
    ciphertext = Fernet(key).encrypt(plaintext)
    return salt + ciphertext


def decrypt_bytes(data: bytes, password: str) -> bytes:
    """Decrypt data produced by `encrypt_bytes`."""
    salt, ciphertext = data[:_SALT_SIZE], data[_SALT_SIZE:]
    key = _derive_key(password, salt)
    return Fernet(key).decrypt(ciphertext)


def encrypt_file(source: Path, password: str, dest: Path) -> None:
    """Encrypt a file and write the result to *dest*."""
    dest.write_bytes(encrypt_bytes(source.read_bytes(), password))


def decrypt_file(encrypted_path: Path, password: str) -> bytes:
    """Decrypt a file produced by `encrypt_file`."""
    return decrypt_bytes(encrypted_path.read_bytes(), password)
