# TODO-037 Pipeline Orchestrator Design

Date: 2026-06-20
Backlog: TODO-037

## Purpose & Scope

Add a small named-step pipeline orchestrator that centralizes build-step
execution, timing, status tracking, event publication, and stop-on-failure
behavior. The first integration target is the existing all-in-one and batch
build step loops in `src/O4_Build_Core.py`.

Scope covers:

- A reusable `src/O4_Pipeline.py` module.
- Step states: `pending`, `running`, `complete`, and `error`.
- Per-step elapsed timing in seconds.
- `PIPELINE_STEP` events with `pipeline`, `step`, `status`, and timing/error
  payloads.
- Existing build result contracts preserved for callers.

## Architecture

`O4_Pipeline.Pipeline` owns an ordered list of named steps. Each step is a
callable returning `None`, `True`, `False`, or `StepOutcome`. `None` and `True`
mean success; `False` means a generic failure; `StepOutcome(False, message)`
means a controlled failure with a caller-provided message.

`Pipeline.run()` executes steps sequentially. Before a step action runs, the
step state becomes `running` and a `PIPELINE_STEP` event is published. On
success, the state becomes `complete`, elapsed time is recorded, a completion
event is published, and the optional `on_step_complete` hook runs. On failure
or exception, the state becomes `error`, an error event is published, remaining
steps stay `pending`, and execution stops.

`O4_Build_Core` wraps current build functions as pipeline actions. It keeps
`TILE_START`, `TILE_PROGRESS`, `TILE_COMPLETE`, and `TILE_ERROR` ownership in
the build core while delegating step status and timing to the pipeline.

## Event Contract

`PIPELINE_STEP` events include:

- `pipeline`: `all` or `batch` for current build integrations.
- `step`: the build step name.
- `status`: `running`, `complete`, or `error`.
- `duration_seconds`: present on `complete` and `error` events.
- `message`: present on `error` events.
- Existing build payload context such as `lat`, `lon`, and `mode`.

The orchestrator does not publish `TILE_*` events directly.

## Testing

Use `unittest` only.

- `tests/test_pipeline.py` covers generic named-step execution, timing, event
  publication, stop-on-failure behavior, and exception conversion.
- `tests/test_build_events.py` covers build-core event integration and verifies
  the event stream now uses orchestrator statuses.
- Existing build-core regression tests cover order, retry, batch, context, and
  interruption behavior.

## Non-Goals

- No GUI workflow changes.
- No CLI output changes.
- No smart cache behavior; TODO-038 owns cache hits.
- No broad build-step decomposition beyond replacing the current step loops.
