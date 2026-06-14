import os
import tempfile
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class TestSceneryCLIDispatch(unittest.TestCase):
    def test_scenery_add_requires_lat_lon(self):
        from O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["add"])

    def test_scenery_remove_requires_lat_lon(self):
        from O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["remove"])

    def test_scenery_list_accepts_no_args(self):
        from O4_CLI_Run import dispatch_scenery
        result = dispatch_scenery(["list"])
        self.assertIsNone(result)

    def test_scenery_reorder_accepts_no_args(self):
        from O4_CLI_Run import dispatch_scenery
        result = dispatch_scenery(["reorder"])
        self.assertIsNone(result)

    def test_scenery_validate_accepts_no_args(self):
        from O4_CLI_Run import dispatch_scenery
        result = dispatch_scenery(["validate"])
        self.assertIsNone(result)

    def test_scenery_invalid_command_exits(self):
        from O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["unknown"])

    def test_dispatch_scenery_with_help(self):
        """Verify basic CLI wiring doesn't crash."""
        from O4_CLI_Run import dispatch_scenery
        with self.assertRaises(SystemExit):
            dispatch_scenery(["--help"])


class TestUpgradePackageWithScenery(unittest.TestCase):
    """Test upgrade-package --update-scenery flag parsing."""

    def test_upgrade_package_parser_accepts_update_scenery(self):
        from O4_CLI_Run import _parser
        p = _parser()
        args = p.parse_args(["upgrade-package", "/some/path", "--update-scenery"])
        self.assertTrue(args.update_scenery)

    def test_upgrade_package_parser_dry_run_with_update_scenery(self):
        from O4_CLI_Run import _parser
        p = _parser()
        args = p.parse_args(["upgrade-package", "/some/path", "--dry-run", "--update-scenery"])
        self.assertTrue(args.dry_run)
        self.assertTrue(args.update_scenery)

    def test_upgrade_package_parser_short_flag(self):
        from O4_CLI_Run import _parser
        p = _parser()
        args = p.parse_args(["upgrade-package", "/some/path", "-u"])
        self.assertTrue(args.update_scenery)
