import importlib.util
import re
import unittest

try:
    import _path
except ModuleNotFoundError:
    from tests import _path


def load_hygiene_module():
    path = (
        _path.ROOT_DIR / ".codex" / "skills" / "repo-hygiene" / "scripts" / "hygiene.py"
    )
    spec = importlib.util.spec_from_file_location("repo_hygiene_script", path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load hygiene module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepoHygienePatternTests(unittest.TestCase):
    def test_forbidden_pattern_regex_treats_py_test_as_literal(self):
        hygiene = load_hygiene_module()
        pattern = hygiene.forbidden_pattern_regex()
        legacy_pytest = "py" + "test tests"
        legacy_py_dot_test = "py" + ".test tests"

        self.assertIsNone(re.search(pattern, "numpy.testing.assert_array_equal"))
        self.assertIsNotNone(re.search(pattern, legacy_py_dot_test))
        self.assertIsNotNone(re.search(pattern, legacy_pytest))


if __name__ == "__main__":
    unittest.main()
