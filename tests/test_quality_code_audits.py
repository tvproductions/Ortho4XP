import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

QUALITY_CHECK_PATH = (
    Path(__file__).resolve().parents[1]
    / ".codex"
    / "skills"
    / "quality-check"
    / "scripts"
    / "quality_check.py"
)


spec = importlib.util.spec_from_file_location("quality_check", QUALITY_CHECK_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load quality check module from {QUALITY_CHECK_PATH}")
quality_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = quality_check
spec.loader.exec_module(quality_check)


class QualityCodeAuditTests(unittest.TestCase):
    def test_module_size_blocks_unwaived_hard_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "large.py"
            module.parent.mkdir()
            module.write_text("x = 1\n" * (quality_check.MODULE_HARD_LINE_LIMIT + 1))

            findings = quality_check.audit_module_size(root, [module], waivers={})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "block")
        self.assertEqual(findings[0].check, "module_size")

    def test_module_size_reports_waived_hard_cap_as_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "legacy.py"
            module.parent.mkdir()
            module.write_text("x = 1\n" * (quality_check.MODULE_HARD_LINE_LIMIT + 1))

            findings = quality_check.audit_module_size(
                root,
                [module],
                waivers={"src/legacy.py": "legacy module awaiting split"},
            )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("under waiver", findings[0].message)

    def test_module_size_blocks_stale_waiver(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "small.py"
            module.parent.mkdir()
            module.write_text("x = 1\n")

            findings = quality_check.audit_module_size(
                root,
                [module],
                waivers={"src/missing.py": "stale"},
            )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "block")
        self.assertIn("no longer scanned", findings[0].message)

    def test_class_size_blocks_unwaived_class(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "classes.py"
            module.parent.mkdir()
            body = "\n".join(
                f"    attr_{idx} = {idx}"
                for idx in range(quality_check.CLASS_LINE_LIMIT + 1)
            )
            module.write_text(f"class Large:\n{body}\n", encoding="utf-8")

            findings = quality_check.audit_class_size(root, [module], waivers={})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "block")
        self.assertEqual(findings[0].line, 1)

    def test_class_size_reports_waived_class_as_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "classes.py"
            module.parent.mkdir()
            body = "\n".join(
                f"    attr_{idx} = {idx}"
                for idx in range(quality_check.CLASS_LINE_LIMIT + 1)
            )
            module.write_text(f"class Large:\n{body}\n", encoding="utf-8")

            findings = quality_check.audit_class_size(
                root,
                [module],
                waivers={"src/classes.py::Large": "legacy aggregate"},
            )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "warn")
        self.assertIn("under waiver", findings[0].message)

    def test_type_ignore_audit_uses_python_comments_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = root / "src" / "typed.py"
            module.parent.mkdir()
            module.write_text(
                'text = "# type: ignore[attr-defined]"\n'
                "value = object()  # type: ignore[attr-defined]\n",
                encoding="utf-8",
            )

            findings = quality_check.audit_type_ignores(root, [module])

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 2)

    def test_test_tier_audit_blocks_forbidden_dirs_and_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            slow = root / "tests" / "slow"
            slow.mkdir(parents=True)
            launcher = root / "Ortho4XP.py"
            launcher.write_text('FLAG = "--slow"\n', encoding="utf-8")

            findings = quality_check.audit_test_tiers(root)

        self.assertEqual(len(findings), 2)
        self.assertTrue(all(finding.severity == "block" for finding in findings))


if __name__ == "__main__":
    unittest.main()
