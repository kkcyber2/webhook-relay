"""The delivery engine: attempt, classify, schedule or dead-letter."""
from __future__ import annotations

import time
from typing import Any, Callable

from .models import Attempt, Delivery, DeliveryState
from .retry import backoff_seconds, is_retryable
from .signing import SIGNATURE_HEADER, TIMESTAMP_HEADER, sign
from .store import RelayStore

# A sender takes (url, body, headers) and returns (status_code, error).
Sender = Callable[[str, bytes, dict[str, str]], "tuple[int | None, str | None]"]


def default_sender(url: str, body: bytes, headers: dict[str, str]) -> tuple[int | None, str | None]:
    """POST the body with httpx. Transport failures come back as (None, message)."""
    import httpx

    try:
        response = httpx.post(url, content=body, headers=headers, timeout=10.0)
        return response.status_code, None
    except httpx.HTTPError as exc:
        return None, f"{type(exc).__name__}: {exc}"


class Dispatcher:
    def __init__(
        self,
        store: RelayStore,
        *,
        sender: Sender | None = None,
        max_attempts: int = 5,
        base_backoff: float = 1.0,
        cap_backoff: float = 300.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.sender = sender or default_sender
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        self.cap_backoff = cap_backoff
        self.clock = clock

    def build_request(self, delivery: Delivery) -> tuple[str, bytes, dict[str, str]]:
        import json

        event = self.store.get_event(delivery.event_id)
        endpoint = self.store.get_endpoint(delivery.endpoint_id)
        if event is None or endpoint is None:
            raise LookupError("delivery references a missing event or endpoint")
        body = json.dumps(
            {"id": event.id, "type": event.event_type, "data": event.payload},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        signature, timestamp = sign(endpoint.secret, body)
        headers = {
            "content-type": "application/json",
            "user-agent": "webhook-relay/1.0",
            SIGNATURE_HEADER: signature,
            TIMESTAMP_HEADER: timestamp,
            "X-Relay-Event": event.event_type,
            "X-Relay-Delivery": delivery.id,
        }
        return endpoint.url, body, headers

    def attempt(self, delivery: Delivery) -> Delivery:
        """Perform one delivery attempt and update the delivery's state."""
        url, body, headers = self.build_request(delivery)
        started = time.perf_counter()
        status_code, error = self.sender(url, body, headers)
        duration_ms = (time.perf_counter() - started) * 1000.0
        delivery.attempts.append(
            Attempt(
                number=delivery.attempt_count + 1,
                status_code=status_code,
                error=error,
                duration_ms=duration_ms,
            )
        )
        if status_code is not None and 200 <= status_code < 300:
            delivery.state = DeliveryState.DELIVERED
            delivery.next_attempt_at = None
            return delivery
        if not is_retryable(status_code) or delivery.attempt_count >= self.max_attempts:
            delivery.state = DeliveryState.DEAD
            delivery.next_attempt_at = None
            return delivery
        delivery.state = DeliveryState.RETRYING
        delay = backoff_seconds(
            delivery.attempt_count, base=self.base_backoff, cap=self.cap_backoff
        )
        delivery.next_attempt_at = self.clock() + delay
        return delivery

    def run_due(self) -> list[Delivery]:
        """Attempt every delivery that is due right now."""
        results = []
        for delivery in self.store.due_deliveries(self.clock()):
            results.append(self.attempt(delivery))
        return results

    def replay(self, delivery_id: str) -> Delivery:
        """Reset a dead delivery so it can be attempted again."""
        delivery = self.store.get_delivery(delivery_id)
        if delivery is None:
            raise LookupError("delivery not found")
        if delivery.state != DeliveryState.DEAD:
            raise ValueError("only dead deliveries can be replayed")
        delivery.state = DeliveryState.PENDING
        delivery.next_attempt_at = None
        return delivery

    def stats(self) -> dict[str, Any]:
        counts: dict[str, int] = {s.value: 0 for s in DeliveryState}
        for delivery in self.store.list_deliveries():
            counts[delivery.state.value] += 1
        return counts
