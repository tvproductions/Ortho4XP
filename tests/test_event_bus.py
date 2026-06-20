import unittest

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
