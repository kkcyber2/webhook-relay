"""Retry policy: which responses are worth retrying, and how long to wait."""
from __future__ import annotations

import random

# 4xx that are genuinely transient and worth another try.
RETRYABLE_4XX = frozenset({408, 425, 429})


def is_retryable(status_code: int | None) -> bool:
    """Decide whether a delivery attempt should be retried.

    ``None`` means a transport error (DNS, connection refused, timeout) — always
    retryable. 2xx is success. 4xx is permanent unless it is one of the transient
    codes. 5xx is retryable.
    """
    if status_code is None:
        return True
    if 200 <= status_code < 300:
        return False
    if 400 <= status_code < 500:
        return status_code in RETRYABLE_4XX
    return True


def backoff_seconds(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 300.0,
    jitter: bool = True,
    rng: random.Random | None = None,
) -> float:
    """Exponential backoff with full jitter, clamped to `cap`.

    `attempt` is 1-based: the wait before the second try is `base * 2`.
    """
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    raw = min(cap, base * (2 ** (attempt - 1)))
    if not jitter:
        return raw
    source = rng or random
    return source.uniform(0.0, raw)
