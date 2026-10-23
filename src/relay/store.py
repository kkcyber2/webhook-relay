"""In-memory store for endpoints, events and deliveries."""
from __future__ import annotations

import itertools
import threading
from typing import Any

from .models import Delivery, DeliveryState, Endpoint, Event


class RelayStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._endpoints: dict[str, Endpoint] = {}
        self._events: dict[str, Event] = {}
        self._deliveries: dict[str, Delivery] = {}
        self._ids = itertools.count(1)

    def _next(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids):06d}"

    def add_endpoint(self, url: str, secret: str) -> Endpoint:
        with self._lock:
            ep = Endpoint(id=self._next("ep"), url=url, secret=secret)
            self._endpoints[ep.id] = ep
            return ep

    def get_endpoint(self, endpoint_id: str) -> Endpoint | None:
        with self._lock:
            return self._endpoints.get(endpoint_id)

    def list_endpoints(self) -> list[Endpoint]:
        with self._lock:
            return list(self._endpoints.values())

    def add_event(self, endpoint_id: str, event_type: str, payload: dict[str, Any]) -> Event:
        with self._lock:
            ev = Event(
                id=self._next("evt"),
                endpoint_id=endpoint_id,
                event_type=event_type,
                payload=payload,
            )
            self._events[ev.id] = ev
            delivery = Delivery(
                id=self._next("dlv"), event_id=ev.id, endpoint_id=endpoint_id
            )
            self._deliveries[delivery.id] = delivery
            return ev

    def get_event(self, event_id: str) -> Event | None:
        with self._lock:
            return self._events.get(event_id)

    def get_delivery(self, delivery_id: str) -> Delivery | None:
        with self._lock:
            return self._deliveries.get(delivery_id)

    def list_deliveries(self, state: DeliveryState | None = None) -> list[Delivery]:
        with self._lock:
            rows = list(self._deliveries.values())
        if state is not None:
            rows = [d for d in rows if d.state == state]
        return rows

    def due_deliveries(self, now: float) -> list[Delivery]:
        with self._lock:
            return [
                d
                for d in self._deliveries.values()
                if d.state in (DeliveryState.PENDING, DeliveryState.RETRYING)
                and (d.next_attempt_at is None or d.next_attempt_at <= now)
            ]

    def clear(self) -> None:
        with self._lock:
            self._endpoints.clear()
            self._events.clear()
            self._deliveries.clear()
            self._ids = itertools.count(1)
