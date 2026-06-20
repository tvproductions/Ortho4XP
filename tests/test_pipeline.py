import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Event_Bus as EVENTS
import O4_Pipeline as PIPELINE


def _event_summary(events):
    return [
        (
            event.payload.get("pipeline"),
            event.payload.get("step"),
            event.payload.get("status"),
            event.payload.get("message"),
        )
        for event in events
    ]


def _progress_recorder(progress):
    def record(state, completed, total):
        progress.append((state.name, completed, total))

    return record


def _step_statuses(result):
    return [state.status for state in result.steps]


def _step_durations(result):
    return [state.duration_seconds for state in result.steps]


class PipelineExecutionTests(unittest.TestCase):
    def setUp(self):
        EVENTS.event_bus().clear()
        self.events = []
        EVENTS.subscribe(EVENTS.EventName.PIPELINE_STEP, self.events.append)

    def tearDown(self):
        EVENTS.event_bus().clear()

    def test_pipeline_runs_named_steps_and_tracks_timing(self):
        calls = []
        progress = []
        pipeline = PIPELINE.Pipeline(
            "demo",
            event_payload={"mode": "test"},
            on_step_complete=_progress_recorder(progress),
        )
        pipeline.add_step("first", lambda: calls.append("first"))
        pipeline.add_step("second", lambda: calls.append("second"))

        result = pipeline.run()

        self.assertTrue(result.ok)
        self.assertIsNone(result.failed_step)
        self.assertEqual(calls, ["first", "second"])
        self.assertEqual([state.name for state in result.steps], ["first", "second"])
        self.assertEqual(
            _step_statuses(result),
            [PIPELINE.StepStatus.COMPLETE, PIPELINE.StepStatus.COMPLETE],
        )
        self.assertNotIn(None, _step_durations(result))
        self.assertEqual(progress, [("first", 1, 2), ("second", 2, 2)])
        self.assertEqual(
            _event_summary(self.events),
            [
                ("demo", "first", "running", None),
                ("demo", "first", "complete", None),
                ("demo", "second", "running", None),
                ("demo", "second", "complete", None),
            ],
        )
        self.assertTrue(all(event.payload["mode"] == "test" for event in self.events))

    def test_pipeline_stops_after_step_failure(self):
        calls = []
        pipeline = PIPELINE.Pipeline("demo")
        pipeline.add_step("first", lambda: calls.append("first"))
        pipeline.add_step(
            "second",
            lambda: PIPELINE.StepOutcome(False, "second failed"),
        )
        pipeline.add_step("third", lambda: calls.append("third"))

        result = pipeline.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_step, "second")
        self.assertEqual(result.message, "second failed")
        self.assertEqual(calls, ["first"])
        self.assertEqual(
            _step_statuses(result),
            [
                PIPELINE.StepStatus.COMPLETE,
                PIPELINE.StepStatus.ERROR,
                PIPELINE.StepStatus.PENDING,
            ],
        )
        self.assertEqual(
            _event_summary(self.events),
            [
                ("demo", "first", "running", None),
                ("demo", "first", "complete", None),
                ("demo", "second", "running", None),
                ("demo", "second", "error", "second failed"),
            ],
        )

    def test_pipeline_converts_exceptions_to_failed_step_result(self):
        def fail():
            raise RuntimeError("boom")

        pipeline = PIPELINE.Pipeline("demo")
        pipeline.add_step("explode", fail)
        pipeline.add_step("after", lambda: None)

        result = pipeline.run()

        self.assertFalse(result.ok)
        self.assertEqual(result.failed_step, "explode")
        self.assertEqual(result.message, "boom")
        self.assertEqual(
            _step_statuses(result),
            [PIPELINE.StepStatus.ERROR, PIPELINE.StepStatus.PENDING],
        )


if __name__ == "__main__":
    unittest.main()
