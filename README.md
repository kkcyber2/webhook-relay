# Webhook Relay

Reliable outbound webhook delivery: HMAC-signed payloads, exponential backoff with
jitter, a dead-letter queue, and a replay endpoint for anything that gave up.

Sending a webhook is easy. Sending one *reliably* is not — the receiver is down, the
receiver is slow, the receiver returns 200 but means "try later", and the same event
must not be delivered twice. This service handles those cases explicitly.

## Design notes

* **Signatures are over the raw body.** `X-Relay-Signature: sha256=<hex>` is an HMAC of
  the exact bytes sent, so a receiver can verify before parsing. The timestamp is part
  of the signed string, which is what makes replay detectable.
* **Retries are classified, not blind.** 2xx succeeds, 4xx (except 408/429) is
  permanent and goes straight to the dead-letter queue, 5xx and network errors retry.
* **Backoff is exponential with full jitter.** Without jitter, a fleet of relays
  retries in lockstep and re-creates the outage it is recovering from.
* **Every attempt is recorded.** The delivery log is the audit trail.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
uvicorn relay.app:app --reload
```

## Try it

```bash
# register an endpoint
curl -s localhost:8000/endpoints -H 'content-type: application/json' \
  -d '{"url":"https://example.com/hook","secret":"s3cret"}'

# enqueue an event
curl -s localhost:8000/events -H 'content-type: application/json' \
  -d '{"endpoint_id":"ep_000001","event_type":"order.created","payload":{"id":42}}'

# inspect the delivery log
curl -s localhost:8000/deliveries
```

## Verifying a signature (receiver side)

```python
import hashlib, hmac

def verify(secret: str, timestamp: str, body: bytes, header: str) -> bool:
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", header)
```

## Tests

```bash
pytest -q
```

## License

MIT — see `LICENSE`.
