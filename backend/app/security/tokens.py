"""Opaque bearer secrets (session and invitation tokens) and CSRF tokens.

Only the SHA-256 digest of a bearer secret is stored. A database leak therefore exposes
no usable credential, and because the secret has 256 bits of entropy a fast hash is
sufficient (slow hashing only matters for low-entropy, human-chosen passwords).
"""

import hashlib
import hmac
import secrets
import uuid

_TOKEN_BYTES = 32


def generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def digest_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def csrf_token_for(session_id: uuid.UUID, secret_key: str) -> str:
    """Synchronizer token bound to one session, derived instead of stored."""
    return hmac.new(secret_key.encode(), session_id.bytes, hashlib.sha256).hexdigest()


def csrf_token_matches(candidate: str | None, session_id: uuid.UUID, secret_key: str) -> bool:
    if not candidate:
        return False
    return hmac.compare_digest(candidate, csrf_token_for(session_id, secret_key))


def fingerprint(value: str, secret_key: str) -> str:
    """Stable pseudonymous key (rate limiting, audit) so no raw e-mail or IP is stored.

    Keyed with HMAC: a plain hash of an IPv4 address could be reversed by brute force.
    """
    return hmac.new(secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]
