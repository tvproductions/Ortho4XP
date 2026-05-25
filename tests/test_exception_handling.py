import ast
import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


class ExceptionHandlingTests(unittest.TestCase):
    def test_no_bare_except_handlers_remain(self):
        python_files = [_path.ROOT_DIR / "Ortho4XP.py"]
        python_files.extend((_path.ROOT_DIR / "src").rglob("*.py"))

        offenders = []
        for path in python_files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    offenders.append(
                        f"{path.relative_to(_path.ROOT_DIR)}:{node.lineno}"
                    )

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
