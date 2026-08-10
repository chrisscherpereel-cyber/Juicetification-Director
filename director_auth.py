"""
director_auth.py — password hashing and login helpers.

Uses PBKDF2-HMAC-SHA256 from the standard library, so there are no extra
dependencies to install or pin. Hashes are stored as a self-describing string:

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

Comparison is constant-time via hmac.compare_digest.
"""

from __future__ import annotations

import os
import base64
import hashlib
import hmac

ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty.")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "{}${}${}${}".format(
        _ALGO,
        ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iters)
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def password_problem(password: str, confirm: str | None = None) -> str | None:
    """Return an error string if the password is unacceptable, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if confirm is not None and password != confirm:
        return "The two passwords do not match."
    return None
