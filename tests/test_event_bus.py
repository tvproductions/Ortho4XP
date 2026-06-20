import concurrent.futures
import threading
import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Event_Bus as EVENTS


class EventBusAPITests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_publish_returns_event_with_normalized_name_and_payload(self):
        event = EVENTS.publish("TILE_START", lat=12, lon=-123, mode="all")

        self.assertEqual(event.name, EVENTS.EventName.TILE_START)
        self.assertEqual(event.payload, {"lat": 12, "lon": -123, "mode": "all"})
        self.assertIsNotNone(event.timestamp.tzinfo)

    def test_subscribe_receives_events_in_order(self):
        received = []

        EVENTS.subscribe(EVENTS.EventName.TILE_START, lambda event: received.append(("a", event)))
        EVENTS.subscribe(EVENTS.EventName.TILE_START, lambda event: received.append(("b", event)))

        event = EVENTS.publish(EVENTS.EventName.TILE_START, lat=12)

        self.assertEqual([name for name, _event in received], ["a", "b"])
        self.assertTrue(all(seen is event for _name, seen in received))

    def test_unsubscribe_removes_exact_handler(self):
        received = []

        def first(event):
            received.append(("first", event.name))

        def second(event):
            received.append(("second", event.name))

        unsubscribe = EVENTS.subscribe(EVENTS.EventName.TILE_START, first)
        EVENTS.subscribe(EVENTS.EventName.TILE_START, second)

        unsubscribe()
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [("second", EVENTS.EventName.TILE_START)])

    def test_clear_removes_all_subscribers(self):
        received = []
        EVENTS.subscribe(EVENTS.EventName.TILE_START, received.append)

        EVENTS.event_bus().clear()
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [])

    def test_invalid_event_name_raises_value_error(self):
        with self.assertRaises(ValueError):
            EVENTS.publish("NOT_A_REAL_EVENT")


class EventBusRobustnessTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_handler_exception_is_logged_and_later_handlers_still_run(self):
        received = []

        def failing_handler(_event):
            raise RuntimeError("subscriber failed")

        def healthy_handler(event):
            received.append(event.name)

        EVENTS.subscribe(EVENTS.EventName.TILE_START, failing_handler)
        EVENTS.subscribe(EVENTS.EventName.TILE_START, healthy_handler)

        with mock.patch.object(EVENTS.UI, "log_exception") as log_exception:
            EVENTS.publish(EVENTS.EventName.TILE_START, lat=12)

        self.assertEqual(received, [EVENTS.EventName.TILE_START])
        log_exception.assert_called_once()
        args, kwargs = log_exception.call_args
        self.assertIsInstance(args[0], RuntimeError)
        self.assertEqual(kwargs["context"]["event_name"], "TILE_START")
        self.assertIn("failing_handler", kwargs["context"]["handler"])

    def test_base_exception_is_not_swallowed(self):
        def interrupting_handler(_event):
            raise KeyboardInterrupt()

        EVENTS.subscribe(EVENTS.EventName.TILE_START, interrupting_handler)

        with self.assertRaises(KeyboardInterrupt):
            EVENTS.publish(EVENTS.EventName.TILE_START)

    def test_handler_can_unsubscribe_itself_during_publish(self):
        received = []
        unsubscribe_holder = {}

        def self_removing_handler(event):
            received.append(event.name)
            unsubscribe_holder["unsubscribe"]()

        unsubscribe_holder["unsubscribe"] = EVENTS.subscribe(
            EVENTS.EventName.TILE_START,
            self_removing_handler,
        )

        EVENTS.publish(EVENTS.EventName.TILE_START)
        EVENTS.publish(EVENTS.EventName.TILE_START)

        self.assertEqual(received, [EVENTS.EventName.TILE_START])

    def test_concurrent_publish_delivers_expected_event_count(self):
        lock = threading.Lock()
        received = []

        def handler(event):
            with lock:
                received.append(event.payload["index"])

        EVENTS.subscribe(EVENTS.EventName.TILE_PROGRESS, handler)

        def publish_one(index):
            EVENTS.publish(EVENTS.EventName.TILE_PROGRESS, index=index)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(publish_one, range(100)))

        self.assertEqual(sorted(received), list(range(100)))
