"""Domain types for endpoints, events and delivery attempts."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeliveryState(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRYING = "retrying"
    DEAD = "dead"


@dataclass
class Endpoint:
    id: str
    url: str
    secret: str
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "url": self.url, "active": self.active, "created_at": self.created_at}


@dataclass
class Event:
    id: str
    endpoint_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "endpoint_id": self.endpoint_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "created_at": self.created_at,
        }


@dataclass
class Attempt:
    number: int
    status_code: int | None
    error: str | None
    duration_ms: float
    at: float = field(default_factory=time.time)

    def public(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "status_code": self.status_code,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "at": self.at,
        }


@dataclass
class Delivery:
    id: str
    event_id: str
    endpoint_id: str
    state: DeliveryState = DeliveryState.PENDING
    attempts: list[Attempt] = field(default_factory=list)
    next_attempt_at: float | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "endpoint_id": self.endpoint_id,
            "state": self.state.value,
            "attempt_count": self.attempt_count,
            "attempts": [a.public() for a in self.attempts],
            "next_attempt_at": self.next_attempt_at,
            "created_at": self.created_at,
        }
