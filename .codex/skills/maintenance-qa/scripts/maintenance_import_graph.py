"""Check real flat O4 imports with Import Linter's standard forbidden contract."""

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def imported_names(node: ast.AST) -> list[str]:
    """Include every static branch and refuse unsupported flat relative imports."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return from_import_names(node)
    return []


def from_import_names(node: ast.ImportFrom) -> list[str]:
    """Require an absolute module identity without executing application code."""
    if node.level or node.module is None:
        raise ValueError(f"Relative import in flat module at line {node.lineno}")
    return [node.module]


def import_edges(source: str, filename: str) -> list[tuple[str, int, str]]:
    """Retain original static import names, including conditional and indirect edges."""
    lines = source.splitlines()
    edges = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        edges.extend(node_edges(node, lines))
    return edges


def node_edges(node: ast.AST, lines: list[str]) -> list[tuple[str, int, str]]:
    """Bind line evidence only to actual import statements."""
    if not isinstance(node, (ast.Import, ast.ImportFrom)):
        return []
    return [
        (name.split(".")[0], node.lineno, lines[node.lineno - 1])
        for name in imported_names(node)
    ]


def add_source_edges(graph, name: str, path: Path) -> None:
    """Add one source's original imports and their line evidence to the graph."""
    for imported, line, contents in import_edges(
        path.read_text(encoding="utf-8"), str(path)
    ):
        graph.add_module(imported)
        graph.add_import(
            importer=name, imported=imported, line_number=line, line_contents=contents
        )


class FlatGraphBuilder:
    """Preserve original O4 module identities without inventing a package layout."""

    def build(self, root_package_names):
        ImportGraph = importlib.import_module("grimp").ImportGraph
        sources = {path.stem: path for path in (ROOT / "src").glob("O4_*.py")}
        if set(root_package_names) != set(sources):
            raise ValueError("Import Linter roots must match all active O4 modules")
        graph = ImportGraph()
        for name in sources:
            graph.add_module(name)
        for name, path in sources.items():
            add_source_edges(graph, name, path)
        return graph


def check_contract(graph, options, contract_options) -> bool:
    """Use the standard indirect forbidden-import semantics on the actual graph."""
    ForbiddenContract = importlib.import_module(
        "importlinter.contracts.forbidden"
    ).ForbiddenContract
    if contract_options["type"] != "forbidden":
        raise ValueError("Flat adapter supports reviewed forbidden contracts only")
    contract = ForbiddenContract(
        contract_options["name"], options.session_options, contract_options
    )
    check = contract.check(graph, verbose=False)
    print(
        f"{contract.name}: {'PASS' if check.kept else 'FAIL'} ({len(graph.modules)} graph nodes)"
    )
    if not check.kept:
        contract.render_broken_contract(check)
    return not check.kept


def main() -> int:
    """Read reviewed configuration and assess every contract independently."""
    configure = importlib.import_module("importlinter.configuration").configure
    reader = importlib.import_module(
        "importlinter.application.use_cases"
    ).read_user_options
    configure()
    options = reader(
        config_filename=str(ROOT / ".codex/skills/maintenance-qa/importlinter.ini")
    )
    graph = FlatGraphBuilder().build(options.session_options["root_packages"])
    if not options.contracts_options:
        raise ValueError("At least one import contract is required")
    failed = False
    for contract in options.contracts_options:
        failed |= check_contract(graph, options, contract)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
