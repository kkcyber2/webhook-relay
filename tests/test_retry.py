import random

import pytest

from relay.retry import backoff_seconds, is_retryable


@pytest.mark.parametrize("code", [200, 201, 204, 299])
def test_2xx_is_success(code):
    assert is_retryable(code) is False


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_permanent_4xx_is_not_retried(code):
    assert is_retryable(code) is False


@pytest.mark.parametrize("code", [408, 425, 429])
def test_transient_4xx_is_retried(code):
    assert is_retryable(code) is True


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_5xx_is_retried(code):
    assert is_retryable(code) is True


def test_transport_error_is_retried():
    assert is_retryable(None) is True


def test_backoff_grows_exponentially_without_jitter():
    waits = [backoff_seconds(n, base=1, cap=1000, jitter=False) for n in range(1, 6)]
    assert waits == [1, 2, 4, 8, 16]


def test_backoff_is_capped():
    assert backoff_seconds(20, base=1, cap=60, jitter=False) == 60


def test_jitter_stays_within_the_window():
    rng = random.Random(7)
    for n in range(1, 8):
        value = backoff_seconds(n, base=1, cap=100, jitter=True, rng=rng)
        assert 0 <= value <= min(100, 2 ** (n - 1))


def test_attempt_must_be_positive():
    with pytest.raises(ValueError):
        backoff_seconds(0)
