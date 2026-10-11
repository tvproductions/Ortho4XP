"""Bounded Cosmic Ray assessment in an explicit disposable checkout."""

import json
import sqlite3
import tomllib
from operator import itemgetter
from pathlib import Path

from maintenance_common import ROOT, run_command


def mutation_status(population: int, rows: list[tuple[str, str, int]]) -> str:
    """Require complete results and separate survivors from worker/test errors."""
    if incomplete_mutations(population, rows):
        return "FAIL"
    return "WARN" if "SURVIVED" in set(map(itemgetter(1), rows)) else "PASS"


def incomplete_mutations(population: int, rows: list[tuple[str, str, int]]) -> bool:
    """Require every expected job to have one interpretable outcome."""
    return (
        not rows
        or sum(map(itemgetter(2), rows)) != population
        or any(map(invalid_outcome, rows))
    )


def invalid_outcome(row: tuple[str, str, int]) -> bool:
    """Keep worker errors and timed-out/incompetent tests distinct from killed mutants."""
    return row[0] != "NORMAL" or row[1] not in {"KILLED", "SURVIVED"}


def mutation_settings(config: Path, workdir: Path) -> dict:
    """Require a disposable single-file scope and bounded unittest execution."""
    workdir = workdir.resolve()
    if not workdir.is_relative_to(ROOT / "tmp") or workdir == ROOT / "tmp":
        raise ValueError("Mutation workdir must be a task-specific directory under tmp")
    settings = tomllib.loads(config.read_text(encoding="utf-8"))["cosmic-ray"]
    target = (workdir / settings["module-path"]).resolve()
    if not target.is_relative_to(workdir) or not target.is_file():
        raise ValueError(
            "Mutation scope must be one file inside the disposable workdir"
        )
    require_unittest(settings)
    if (workdir / "session.sqlite").exists() or (workdir / "baseline.sqlite").exists():
        raise ValueError("Use an unused workdir/session for each assessment")
    return settings


def require_unittest(settings: dict) -> None:
    """Require the configured public unittest seam and a bounded test timeout."""
    if "-m unittest" not in settings["test-command"]:
        raise ValueError("Require a unittest test command")
    if not 0 < settings["timeout"] <= 60:
        raise ValueError("Require a per-run timeout at most 60 seconds")


def cosmic_command(command: str, config: Path, session: Path) -> None:
    """Run a bounded tool command, refusing any unsuccessful execution."""
    prefix = ["uv", "run", "--project", str(ROOT), "--group", "hygiene", "cosmic-ray"]
    arguments = [str(config.resolve()), str(session)]
    if command == "baseline":
        arguments = [str(config.resolve()), "--session-file", str(session)]
    code, stdout, stderr = run_command(
        [*prefix, command, *arguments], cwd=session.parent
    )
    if code:
        raise ValueError(f"Cosmic Ray {command} failed: {(stdout + stderr)[-500:]}")


def clean_mutation_baseline(config: Path, workdir: Path) -> None:
    """Require one actually successful unmodified unittest run."""
    baseline = workdir / "baseline.sqlite"
    cosmic_command("baseline", config, baseline)
    with sqlite3.connect(baseline) as database:
        rows = database.execute(
            "SELECT worker_outcome, test_outcome FROM work_results"
        ).fetchall()
    if rows != [("NORMAL", "SURVIVED")]:
        raise ValueError(f"Unmodified test baseline was not clean: {rows}")


def mutation_population(config: Path, session: Path) -> int:
    """Initialize an unused session and bound the generated mutation population."""
    cosmic_command("init", config, session)
    with sqlite3.connect(session) as database:
        population = database.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]
    if not 0 < population <= 200:
        raise ValueError(f"Mutation scope has {population} jobs; require 1..200")
    return population


def mutation_receipt(session: Path, population: int) -> tuple[str, str]:
    """Retain complete worker/test outcomes, including surviving and errored jobs."""
    with sqlite3.connect(session) as database:
        rows = database.execute(
            "SELECT worker_outcome, test_outcome, COUNT(*) FROM work_results GROUP BY worker_outcome, test_outcome"
        ).fetchall()
    (session.parent / "outcomes.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    status = mutation_status(population, rows)
    return (
        status,
        f"Worker/test outcomes {rows}; expected={population}; equivalent mutants require review; receipt {session.parent.relative_to(ROOT)}",
    )


def execute_mutations(config: Path, workdir: Path) -> tuple[str, str]:
    """Run the baseline before executing mutations and classify every generated job."""
    mutation_settings(config, workdir)
    clean_mutation_baseline(config, workdir)
    session = workdir / "session.sqlite"
    population = mutation_population(config, session)
    cosmic_command("exec", config, session)
    return mutation_receipt(session, population)


def check_mutation_testing(
    config: Path | None = None, workdir: Path | None = None
) -> tuple[str, str]:
    """Assess only an explicitly requested disposable mutation fixture."""
    try:
        return configured_mutations(config, workdir)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        return "FAIL", f"Cosmic Ray measurement error: {error}"


def configured_mutations(config: Path | None, workdir: Path | None) -> tuple[str, str]:
    """Resolve only an explicitly configured disposable mutation scope."""
    config = config or ROOT / "cosmic-ray.toml"
    if not config.exists() or workdir is None:
        return "FAIL", "Explicit config and disposable workdir are required"
    return execute_mutations(config, workdir.resolve())
