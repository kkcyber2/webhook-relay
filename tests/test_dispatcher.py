import pytest

from relay.dispatcher import Dispatcher
from relay.models import DeliveryState
from relay.store import RelayStore


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(sender, **kw):
    store = RelayStore()
    clock = Clock()
    ep = store.add_endpoint("https://example.com/hook", "secret-secret")
    ev = store.add_event(ep.id, "order.created", {"id": 1})
    delivery = store.list_deliveries()[0]
    dispatcher = Dispatcher(store, sender=sender, clock=clock, **kw)
    return store, dispatcher, delivery, clock, ev


def test_successful_delivery_marks_delivered():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (200, None))
    dispatcher.attempt(delivery)
    assert delivery.state is DeliveryState.DELIVERED
    assert delivery.attempt_count == 1


def test_permanent_failure_goes_straight_to_dead_letter():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (404, None))
    dispatcher.attempt(delivery)
    assert delivery.state is DeliveryState.DEAD
    assert delivery.attempt_count == 1


def test_5xx_schedules_a_retry():
    store, dispatcher, delivery, clock, _ = make(lambda u, b, h: (503, None))
    dispatcher.attempt(delivery)
    assert delivery.state is DeliveryState.RETRYING
    assert delivery.next_attempt_at > clock.now


def test_retry_is_not_due_until_the_backoff_elapses():
    store, dispatcher, delivery, clock, _ = make(lambda u, b, h: (500, None))
    dispatcher.attempt(delivery)
    assert dispatcher.run_due() == []
    clock.now += 10_000
    assert len(dispatcher.run_due()) == 1


def test_gives_up_after_max_attempts():
    store, dispatcher, delivery, clock, _ = make(lambda u, b, h: (500, None), max_attempts=3)
    for _ in range(3):
        dispatcher.attempt(delivery)
        clock.now += 10_000
    assert delivery.state is DeliveryState.DEAD
    assert delivery.attempt_count == 3


def test_transport_error_is_recorded_and_retried():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (None, "ConnectError: refused"))
    dispatcher.attempt(delivery)
    assert delivery.state is DeliveryState.RETRYING
    assert delivery.attempts[0].error == "ConnectError: refused"


def test_request_carries_a_valid_signature():
    from relay.signing import SIGNATURE_HEADER, TIMESTAMP_HEADER, verify

    captured = {}

    def sender(url, body, headers):
        captured.update(url=url, body=body, headers=headers)
        return 200, None

    store, dispatcher, delivery, _, _ = make(sender)
    dispatcher.attempt(delivery)
    assert captured["url"] == "https://example.com/hook"
    assert verify(
        "secret-secret",
        captured["body"],
        captured["headers"][SIGNATURE_HEADER],
        captured["headers"][TIMESTAMP_HEADER],
    )


def test_replay_revives_a_dead_delivery():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (404, None))
    dispatcher.attempt(delivery)
    assert delivery.state is DeliveryState.DEAD
    dispatcher.replay(delivery.id)
    assert delivery.state is DeliveryState.PENDING


def test_replay_refuses_a_live_delivery():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (200, None))
    dispatcher.attempt(delivery)
    with pytest.raises(ValueError):
        dispatcher.replay(delivery.id)


def test_stats_counts_each_state():
    store, dispatcher, delivery, _, _ = make(lambda u, b, h: (200, None))
    dispatcher.attempt(delivery)
    assert dispatcher.stats()["delivered"] == 1
