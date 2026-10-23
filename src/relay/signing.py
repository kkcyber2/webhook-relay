"""HMAC signing and verification for outbound webhooks."""
from __future__ import annotations

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-Relay-Signature"
TIMESTAMP_HEADER = "X-Relay-Timestamp"
DEFAULT_TOLERANCE = 300


def sign(secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, str]:
    """Return (signature_header_value, timestamp_string).

    The signed string is ``<timestamp>.<body>`` so a captured request cannot be
    replayed later without the signature failing.
    """
    ts = str(int(timestamp if timestamp is not None else time.time()))
    mac = hmac.new(secret.encode("utf-8"), f"{ts}.".encode("ascii") + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}", ts


def verify(
    secret: str,
    body: bytes,
    signature: str,
    timestamp: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    now: int | None = None,
) -> bool:
    """Check a signature and that the timestamp is inside the tolerance window."""
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = int(now if now is not None else time.time())
    if abs(current - sent_at) > tolerance:
        return False
    expected, _ = sign(secret, body, sent_at)
    return hmac.compare_digest(expected, signature or "")
