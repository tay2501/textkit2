"""Secure password generation using the stdlib secrets module.

Uses secrets.choice() which draws from os.urandom() — cryptographically
secure and suitable for generating credentials.
"""

from __future__ import annotations

import secrets
import string

DEFAULT_LENGTH: int = 20

# Base alphabet: 62 characters (a-z, A-Z, 0-9)
_ALPHA_NUM: str = string.ascii_letters + string.digits

# Extended alphabet adds all 32 printable ASCII punctuation characters
_ALPHA_NUM_SYMBOLS: str = _ALPHA_NUM + string.punctuation


def generate_password(length: int = DEFAULT_LENGTH, *, symbols: bool = False) -> str:
    """Return a cryptographically secure random password.

    Args:
        length: Number of characters. Must be >= 1.
        symbols: When True, include ASCII punctuation in the character set.

    Raises:
        ValueError: If length < 1.
    """
    if length < 1:
        raise ValueError(f"length must be >= 1, got {length}")
    alphabet = _ALPHA_NUM_SYMBOLS if symbols else _ALPHA_NUM
    return "".join(secrets.choice(alphabet) for _ in range(length))
