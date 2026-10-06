"""Password hashing with Argon2id (OWASP's first recommendation, winner of the PHC).

Hashing is deliberately expensive, so it runs in a worker thread to keep the event loop
responsive for every other request.
"""

import asyncio
import os
from collections.abc import Callable
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# RFC 9106 "second recommended option": 64 MiB, 3 iterations, 4 lanes.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)

# Each hash allocates 64 MiB. Without a bound, a burst of logins would fan out across the
# whole thread pool (~32 threads ≈ 2 GiB). Extra requests queue here instead.
_HASH_SLOTS = asyncio.Semaphore(max(2, os.cpu_count() or 2))

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash("georgos-timing-equalizer")


async def _run_bounded[T](func: Callable[..., T], *args: str) -> T:
    async with _HASH_SLOTS:
        return await asyncio.to_thread(func, *args)


async def hash_password(password: str) -> str:
    return await _run_bounded(_hasher.hash, password)


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False


def _verify_against_dummy(password: str) -> None:
    # The dummy hash is built lazily inside the worker thread, never on the event loop.
    _verify(_dummy_hash(), password)


async def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-work verification.

    When the account does not exist (``password_hash is None``) a dummy hash is verified
    anyway, so response time does not reveal which e-mails are registered.
    """
    if password_hash is None:
        await _run_bounded(_verify_against_dummy, password)
        return False
    return await _run_bounded(_verify, password_hash, password)


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
