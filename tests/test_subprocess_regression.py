import unittest

try:
    import _path  # noqa: F401
except ModuleNotFoundError:
    from tests import _path  # noqa: F401


FORBIDDEN_SUBPROCESS = (
    "subprocess.call(",
    "subprocess.Popen(",
    "subprocess.run(",
)

SHARED_SUBPROCESS_MODULES = {
    "O4_Subprocess_Runtime.py",
    "O4_Subprocess_Utils.py",
}

TODO_010_TOOLS = (
    "Triangle4XP",
    "triangle",
    "moulinette",
    "nvcompress",
    "DDSTool",
    "gdal_translate",
    "gdalwarp",
    "7z",
    "DSFTool",
)


def active_source_files():
    for path in _path.SRC_DIR.rglob("*.py"):
        relative_parts = path.relative_to(_path.SRC_DIR).parts
        if (
            "Unused" not in relative_parts
            and path.name not in SHARED_SUBPROCESS_MODULES
        ):
            yield path


def raw_subprocess_findings():
    for path in active_source_files():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_SUBPROCESS:
            if token in text:
                yield f"{path}: raw {token}"


def raw_os_system_tool_findings():
    for path in active_source_files():
        for line in raw_os_system_tool_lines(path):
            yield f"{path}: raw os.system tool call: {line.strip()}"


def raw_os_system_tool_lines(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if is_todo_010_os_system_line(line)]


def is_todo_010_os_system_line(line):
    return "os.system(" in line and any(tool in line for tool in TODO_010_TOOLS)


class ExternalToolRegressionTests(unittest.TestCase):
    def test_active_tool_calls_do_not_use_raw_subprocess_apis(self):
        findings = list(raw_subprocess_findings())
        findings.extend(raw_os_system_tool_findings())

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
