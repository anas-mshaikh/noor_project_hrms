from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError


_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def validate_password_strength(password: str) -> None:
    """
    Minimal password policy for bootstrap/admin creation.

    TODO: tighten (entropy checks, breach lists) before production.
    """

    if len(password) < 10:
        raise ValueError("password must be at least 10 characters")
    if password.lower() == password:
        raise ValueError("password must include at least one uppercase letter")
    if password.upper() == password:
        raise ValueError("password must include at least one lowercase letter")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("password must include at least one digit")

