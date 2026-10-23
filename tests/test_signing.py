from relay.signing import sign, verify


def test_signature_round_trips():
    body = b'{"a":1}'
    sig, ts = sign("topsecret", body, timestamp=1_000_000)
    assert verify("topsecret", body, sig, ts, now=1_000_000)


def test_wrong_secret_fails():
    body = b"payload"
    sig, ts = sign("right", body, timestamp=1_000_000)
    assert not verify("wrong", body, sig, ts, now=1_000_000)


def test_tampered_body_fails():
    sig, ts = sign("s", b"original", timestamp=1_000_000)
    assert not verify("s", b"modified", sig, ts, now=1_000_000)


def test_stale_timestamp_fails():
    body = b"x"
    sig, ts = sign("s", body, timestamp=1_000_000)
    assert not verify("s", body, sig, ts, now=1_000_000 + 10_000)


def test_timestamp_is_part_of_the_signature():
    body = b"x"
    sig, _ = sign("s", body, timestamp=1_000_000)
    assert not verify("s", body, sig, "1000001", now=1_000_001)


def test_malformed_timestamp_is_rejected():
    assert not verify("s", b"x", "sha256=abc", "not-a-number")
