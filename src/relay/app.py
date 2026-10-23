"""HTTP surface for the relay."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from .dispatcher import Dispatcher
from .models import DeliveryState
from .store import RelayStore

store = RelayStore()
dispatcher = Dispatcher(store)

app = FastAPI(
    title="Webhook Relay",
    version="1.0.0",
    description="Reliable webhook delivery with HMAC signing, retries and a dead-letter queue.",
)


class EndpointCreate(BaseModel):
    url: HttpUrl
    secret: str = Field(min_length=8, max_length=256)


class EventCreate(BaseModel):
    endpoint_id: str
    event_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


@app.get("/health", tags=["meta"])
def health() -> dict[str, Any]:
    return {"status": "ok", "stats": dispatcher.stats()}


@app.post("/endpoints", status_code=201, tags=["endpoints"])
def create_endpoint(body: EndpointCreate) -> dict[str, Any]:
    return store.add_endpoint(str(body.url), body.secret).public()


@app.get("/endpoints", tags=["endpoints"])
def list_endpoints() -> list[dict[str, Any]]:
    return [e.public() for e in store.list_endpoints()]


@app.post("/events", status_code=201, tags=["events"])
def create_event(body: EventCreate) -> dict[str, Any]:
    if store.get_endpoint(body.endpoint_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "endpoint not found")
    return store.add_event(body.endpoint_id, body.event_type, body.payload).public()


@app.get("/deliveries", tags=["deliveries"])
def list_deliveries(state: str | None = None) -> list[dict[str, Any]]:
    parsed = None
    if state is not None:
        try:
            parsed = DeliveryState(state)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown state {state!r}") from exc
    return [d.public() for d in store.list_deliveries(parsed)]


@app.post("/deliveries/run", tags=["deliveries"])
def run_due() -> dict[str, Any]:
    results = dispatcher.run_due()
    return {"attempted": len(results), "deliveries": [d.public() for d in results]}


@app.post("/deliveries/{delivery_id}/replay", tags=["deliveries"])
def replay(delivery_id: str) -> dict[str, Any]:
    try:
        return dispatcher.replay(delivery_id).public()
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
