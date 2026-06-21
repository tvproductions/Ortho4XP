import unittest
from unittest import mock

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401

import O4_Provider_Failover as FAILOVER


class ProviderFailoverTests(unittest.TestCase):
    def setUp(self):
        self.vprint_patch = mock.patch.object(FAILOVER.LOG.UI, "vprint")
        self.log_event_patch = mock.patch.object(FAILOVER.LOG.UI, "log_event")
        self.vprint_patch.start()
        self.log_event_patch.start()
        self.addCleanup(self.vprint_patch.stop)
        self.addCleanup(self.log_event_patch.stop)

    def test_success_resets_failure_state_and_blacklist(self):
        clock = FakeClock()
        registry = FAILOVER.ProviderFailoverRegistry(clock=clock)

        registry.record_failure("BI")
        registry.record_failure("BI")
        registry.record_failure("BI")
        self.assertTrue(registry.is_blacklisted("BI"))

        registry.record_success("BI")

        self.assertFalse(registry.is_blacklisted("BI"))
        self.assertEqual(registry.state_for("BI").consecutive_failures, 0)

    def test_third_consecutive_failure_blacklists_for_five_minutes(self):
        clock = FakeClock()
        registry = FAILOVER.ProviderFailoverRegistry(clock=clock)

        first = registry.record_failure("BI")
        second = registry.record_failure("BI")
        third = registry.record_failure("BI")

        self.assertFalse(first.blacklisted)
        self.assertFalse(second.blacklisted)
        self.assertTrue(third.blacklisted)
        self.assertEqual(third.consecutive_failures, 3)
        self.assertEqual(third.blacklisted_until, 300.0)

    def test_expired_blacklist_becomes_eligible_again(self):
        clock = FakeClock()
        registry = FAILOVER.ProviderFailoverRegistry(clock=clock)
        for _ in range(3):
            registry.record_failure("BI")

        self.assertTrue(registry.is_blacklisted("BI"))
        clock.now = 301.0

        self.assertFalse(registry.is_blacklisted("BI"))
        self.assertEqual(registry.state_for("BI").consecutive_failures, 0)

    def test_replacement_selection_skips_failed_and_blacklisted_providers(self):
        clock = FakeClock()
        registry = FAILOVER.ProviderFailoverRegistry(clock=clock)
        for _ in range(3):
            registry.record_failure("Arc")
        providers = {
            "GO2": {"code": "GO2", "in_GUI": True},
            "BI": {"code": "BI", "in_GUI": True},
            "Arc": {"code": "Arc", "in_GUI": True},
            "AAHidden": {"code": "AAHidden", "in_GUI": False},
        }

        replacement = registry.select_replacement("BI", providers)

        self.assertEqual(replacement, "GO2")

    def test_replacement_selection_returns_none_when_no_provider_is_eligible(self):
        registry = FAILOVER.ProviderFailoverRegistry()

        self.assertIsNone(registry.select_replacement("BI", {"BI": {"code": "BI"}}))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


if __name__ == "__main__":
    unittest.main()
