def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_create_endpoint_and_event(client):
    ep = client.post(
        "/endpoints", json={"url": "https://example.com/hook", "secret": "long-enough-secret"}
    )
    assert ep.status_code == 201
    ev = client.post(
        "/events",
        json={"endpoint_id": ep.json()["id"], "event_type": "ping", "payload": {"n": 1}},
    )
    assert ev.status_code == 201
    assert client.get("/deliveries").json()[0]["state"] == "pending"


def test_event_for_unknown_endpoint_is_404(client):
    r = client.post("/events", json={"endpoint_id": "ep_999999", "event_type": "x"})
    assert r.status_code == 404


def test_short_secret_is_rejected(client):
    r = client.post("/endpoints", json={"url": "https://example.com/h", "secret": "short"})
    assert r.status_code == 422


def test_unknown_state_filter_is_422(client):
    assert client.get("/deliveries?state=bogus").status_code == 422


def test_replay_unknown_delivery_is_404(client):
    assert client.post("/deliveries/dlv_999999/replay").status_code == 404
