"""Parse and splice allowlisted DSFTool text header lines.

This module deliberately avoids terrain, object, polygon, network, pool, and
command definitions because those entries are index-bearing DSF structures.  The
TODO-017 bridge only copies non-destructive header-style lines whose text names
the accepted XP12 feature families: seasons, vegetation, sound, and runway
friction.  Parsing stops at the first DSFTool body block so generated ortho mesh
commands cannot be overwritten by default scenery content.
"""

SUPPORTED_HEADER_TOKENS = (
    "season",
    "vegetation",
    "sound",
    "friction",
)

HEADER_BODY_PREFIXES = ("BEGIN_",)


def extract_supported_header_lines(dsf_text: str) -> tuple[str, ...]:
    """Return allowlisted native XP12 header lines from DSFTool text."""
    supported_lines = []
    seen = set()
    for line in _iter_header_lines(dsf_text):
        if _is_supported_header_line(line):
            _append_unique_line(supported_lines, seen, line)
    return tuple(supported_lines)


def splice_supported_header_lines(
    generated_dsf_text: str, supported_header_lines: tuple[str, ...]
) -> str:
    generated_lines = generated_dsf_text.splitlines()
    existing_lines = {line.strip() for line in generated_lines}
    lines_to_insert = [
        line
        for line in supported_header_lines
        if line.strip() and line.strip() not in existing_lines
    ]
    insertion_index = _header_insertion_index(generated_lines)
    spliced_lines = (
        generated_lines[:insertion_index]
        + lines_to_insert
        + generated_lines[insertion_index:]
    )
    final_newline = "\n" if generated_dsf_text.endswith("\n") or spliced_lines else ""
    return "\n".join(spliced_lines) + final_newline


def _iter_header_lines(dsf_text: str):
    for raw_line in dsf_text.splitlines():
        line = raw_line.strip()
        if line.startswith(HEADER_BODY_PREFIXES):
            break
        if line:
            yield line


def _is_supported_header_line(line: str) -> bool:
    if not line.startswith(("PROPERTY ", "ATTR_")):
        return False
    return _contains_supported_token(line)


def _contains_supported_token(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in SUPPORTED_HEADER_TOKENS)


def _append_unique_line(lines: list[str], seen: set[str], line: str) -> None:
    if line in seen:
        return
    lines.append(line)
    seen.add(line)


def _header_insertion_index(generated_lines: list[str]) -> int:
    insertion_index = 0
    for index, line in enumerate(generated_lines):
        if not line.strip().startswith("PROPERTY "):
            break
        insertion_index = index + 1
    return insertion_index
