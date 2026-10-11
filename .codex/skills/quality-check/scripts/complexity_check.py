"""Explicit, source-only Lizard C/C/C check; never executes application code."""

import argparse
import ast
import hashlib
import importlib
import json
import platform
import sys
import tokenize
from collections import Counter
from importlib.metadata import version
from pathlib import Path

CEILING = 20
CONTRACT = "lizard-functions-v1"
BLOCKED = {
    ".git",
    ".venv",
    "__pycache__",
    "plugins",
    "archive",
    "archived",
    "out",
    "output",
    "outputs",
}


def source_files(root, paths):
    """Resolve explicit scopes without following links or visiting excluded trees."""
    found = set()
    for relative in paths:
        visit(validate_scope(root, relative), found)
    if not found:
        raise ValueError("Scope contains no Python files")
    return sorted(found)


def validate_scope(root, relative):
    """Require an existing relative scope without symlinked ancestors."""
    scope = Path(relative)
    if scope.is_absolute() or ".." in scope.parts:
        raise ValueError("Scopes must be relative paths inside root")
    if excluded_scope(scope):
        raise ValueError(f"Excluded scope: {relative}")
    path = root / scope
    check_ancestors(path, root, relative)
    if not path.exists():
        raise ValueError(f"Missing scope: {relative}")
    return path


def excluded_scope(scope):
    """Identify explicitly excluded path components."""
    return any(part in BLOCKED for part in scope.parts)


def check_ancestors(path, root, relative):
    """Reject symlink traversal before reading any selected source."""
    for parent in (path, *path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f"Symlink scope: {relative}")


def source_children(path):
    """List visible children outside the contract's excluded directory names."""
    return [
        child
        for child in sorted(path.iterdir())
        if child.name not in BLOCKED and not child.name.startswith(".")
    ]


def visit(path, found):
    """Select Python files while making symlinked source a visible error."""
    if path.is_symlink():
        raise ValueError(f"Symlink in source scope: {path.name}")
    if path.is_dir():
        for child in source_children(path):
            visit(child, found)
    elif path.suffix == ".py":
        found.add(path)


def measure(path, root, analyzer):
    """Validate grammar and discovery, then retain the analyzer's native scores."""
    with tokenize.open(path) as handle:
        source = handle.read()
    compile(source, str(path), "exec")
    tree = ast.parse(source)
    analysis = analyzer.analyze_file.analyze_source_code(str(path), source)
    require_discovery(tree, analysis)
    functions = measured_functions(analysis)
    scores = [item["complexity"] for item in functions]
    return {
        "file": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "functions": functions,
        "mean": sum(scores) / len(scores) if scores else None,
    }


def require_discovery(tree, analysis):
    """Require identical syntax/analyzer populations before using their scores."""
    expected = function_locations(tree)
    actual = Counter(item.start_line for item in analysis.function_list)
    if expected != actual:
        raise ValueError(
            f"Function discovery mismatch: expected {dict(expected)}, got {dict(actual)}"
        )


def function_locations(tree):
    """Count each syntactic function location independently of the analyzer."""
    return Counter(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def measured_functions(analysis):
    """Retain native function locations and cyclomatic scores verbatim."""
    return [
        {
            "name": item.name,
            "line": item.start_line,
            "complexity": item.cyclomatic_complexity,
        }
        for item in analysis.function_list
    ]


def findings(modules):
    """Enforce each part of C/C/C on the identical function population."""
    result = []
    scores = []
    for module in modules:
        for function in module["functions"]:
            score = function["complexity"]
            scores.append(score)
            if score > CEILING:
                result.append({"kind": "function", "file": module["file"], **function})
        if module["mean"] is not None and module["mean"] > CEILING:
            result.append(
                {"kind": "module", "file": module["file"], "complexity": module["mean"]}
            )
    overall = sum(scores) / len(scores) if scores else None
    if overall is not None and overall > CEILING:
        result.append({"kind": "overall", "complexity": overall})
    return result, {
        "functions": len(scores),
        "maximum": max(scores) if scores else None,
        "overall_mean": overall,
    }


def assess(root, paths):
    """Return failures and tool errors distinctly; partial measurements never pass."""
    receipt = {
        "python": platform.python_version(),
        "scope": paths,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "contract": CONTRACT,
        "ceilings": [CEILING] * 3,
        "modules": [],
        "errors": [],
    }
    try:
        lizard = importlib.import_module("lizard")

        receipt["lizard_version"] = version("lizard")
        if receipt["lizard_version"] != "1.24.1":
            raise ValueError(
                "Contract requires reviewed Lizard 1.24.1; revalidate before upgrades"
            )
        files = source_files(root, paths)
    except (ImportError, ValueError, OSError) as error:
        receipt["errors"].append({"message": str(error)})
        files = []
    for path in files:
        retain_measurement(receipt, path, root, lizard)
    receipt["violations"], receipt["aggregate"] = findings(receipt["modules"])
    receipt["status"] = (
        "error"
        if receipt["errors"]
        else "failed"
        if receipt["violations"]
        else "passed"
    )
    return receipt


def retain_measurement(receipt, path, root, analyzer):
    """Retain measurement errors without turning a partial assessment clean."""
    try:
        receipt["modules"].append(measure(path, root, analyzer))
    except Exception as error:  # Analyzer failures must not become clean measurements.
        receipt["errors"].append(
            {"file": str(path.relative_to(root)), "message": str(error)}
        )


def main():
    """Emit a machine-readable receipt and a reliable process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--paths", nargs="+", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = assess(args.root.resolve(), args.paths)
    payload = json.dumps(receipt, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload)
    print(
        json.dumps(
            {key: receipt[key] for key in ("contract", "status", "aggregate", "errors")}
            | {"violations": len(receipt["violations"])}
        )
    )
    return {"passed": 0, "failed": 1, "error": 2}[receipt["status"]]


if __name__ == "__main__":
    sys.exit(main())
