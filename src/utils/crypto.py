"""
Credential encryption helper.

Uses Fernet symmetric encryption. The key is derived from a secret stored in
.env (CREDENTIAL_SECRET). If not set, a stable per-machine key is derived from
the machine's hostname so restarts don't break existing credentials.

IMPORTANT: back up your CREDENTIAL_SECRET — without it encrypted passwords
cannot be recovered.
"""
from __future__ import annotations

import base64
import hashlib
import os
import socket

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    secret = os.getenv("CREDENTIAL_SECRET", "")
    if not secret:
        # Fallback: stable key derived from hostname — good enough for local use
        secret = socket.gethostname() + "_jobsystem_default_key_v1"
    # Derive a 32-byte key from the secret
    key_bytes = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return a base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to a string."""
    return _get_fernet().decrypt(token.encode()).decode()
