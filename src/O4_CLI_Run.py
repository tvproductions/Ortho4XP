from __future__ import annotations

import argparse
from typing import Callable, cast

import O4_Build_Models as MODELS
import O4_CLI_Jobs as JOBS


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "validate-package":
        from O4_Package_Validator import validate_package
        result = validate_package(args.package_dir)
        if result["valid"]:
            print(f"Package validated: {args.package_dir}")
            return 0
        for err in result["errors"]:
            print(f"ERROR: {err}")
        return 1

    try:
        provider_keys, combined_provider_keys, provider_metadata = _provider_inventory()
        plan = JOBS.load_build_plan(
            args.job_file,
            provider_keys=provider_keys,
            combined_provider_keys=combined_provider_keys,
            provider_metadata=provider_metadata,
        )
    except JOBS.JobValidationError as exc:
        _print_validation_failure(exc.errors, json_output=args.json)
        return 2

    if args.command == "validate-job" or args.dry_run:
        _print_validation_success(plan, json_output=args.json)
        return 0

    try:
        result = _run_build(plan)
    except Exception as exc:
        _log_build_exception(exc)
        print(f"Build job failed: {exc}")
        return 1
    _print_build_result(result)
    return 0 if result.ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="Ortho4XP.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-job")
    validate.add_argument("job_file")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(dry_run=True)

    build = subparsers.add_parser("build-job")
    build.add_argument("job_file")
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--json", action="store_true")

    p_validate = subparsers.add_parser(
        "validate-package",
        help="Validate a generated scenery package's metadata and structure",
    )
    p_validate.add_argument(
        "package_dir", type=str,
        help="Path to the generated package directory",
    )

    return parser


def _provider_inventory() -> tuple[set[str], set[str], dict[str, dict]]:
    import O4_Imagery_Utils as IMG

    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    return (
        set(IMG.providers_dict),
        set(IMG.combined_providers_dict),
        IMG.providers_dict,
    )


def _run_build(plan: MODELS.BuildPlan) -> MODELS.BuildBatchResult:
    import Ortho4XP
    import O4_Build_Core as CORE

    if not Ortho4XP.ensure_runtime_dirs():
        return MODELS.BuildBatchResult(False, (), "runtime directory setup failed")
    build_batch = cast(
        Callable[[MODELS.BuildPlan], MODELS.BuildBatchResult],
        getattr(CORE, "build_batch"),
    )
    return build_batch(plan)


def _log_build_exception(exc: Exception) -> None:
    import O4_UI_Utils as UI

    UI.log_exception(exc)


def _print_validation_success(plan: MODELS.BuildPlan, *, json_output: bool) -> None:
    if json_output:
        print(JOBS.validation_success_json(plan))
    else:
        print(JOBS.human_validation_summary(plan))


def _print_validation_failure(
    errors: tuple[JOBS.ValidationError, ...], *, json_output: bool
) -> None:
    if json_output:
        print(JOBS.validation_failure_json(errors))
    else:
        print(JOBS.human_validation_errors(errors))


def _print_build_result(result: MODELS.BuildBatchResult) -> None:
    if result.ok:
        print(f"Build job completed: {len(result.tiles)} tile(s)")
        return
    failed = next((tile for tile in result.tiles if not tile.ok), None)
    if failed:
        print(
            f"Build job failed at {failed.lat:+03d}{failed.lon:+04d} "
            f"step={failed.step}: {failed.message}"
        )
    elif result.message:
        print(f"Build job failed: {result.message}")
    else:
        print("Build job failed")
