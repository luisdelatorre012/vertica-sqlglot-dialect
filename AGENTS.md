# Repository agent instructions

When a request refers to "the plan", "the next task", or "the next remaining
task", read `docs/AGENT_TASK_PLAN.md` completely before editing anything.

- Resume the single `IN_PROGRESS` task. If none exists, take the lowest-numbered
  `TODO` task whose dependencies are `DONE`.
- Complete exactly one task per invocation. Do not begin, research, or partially
  implement the following task.
- Follow the plan's scope, exclusions, acceptance tests, release gate, status
  update procedure, and commit title.
- Preserve pre-existing worktree changes. They belong to the task identified in
  the plan unless the plan explicitly says otherwise.
- On first use, install the repository hooks with
  `python -m pre_commit install --install-hooks`. Before marking a task complete,
  run `python -m pre_commit run --all-files --show-diff-on-failure` in addition
  to the plan's full release gate.
- Commit normally so both the pre-commit and Conventional Commit message hooks
  execute. Never use `--no-verify`, `SKIP`, or another hook bypass. If a fixer
  changes files, inspect the diff, restage only task files, rerun affected tests
  and all hooks, and then retry the commit.
- Update the selected task to `DONE` (or `BLOCKED`) and update the dashboard in
  the same commit as the implementation. Stop after that local commit. Never
  push; this repository intentionally has no remote.

## Local CPython release matrix

All supported CPython minors are installed and testable through stable
versioned shims in `C:\Users\luisd\.local\bin`:

| Minor | Installed release | Executable |
| --- | --- | --- |
| 3.9 | 3.9.25 | `python3.9.exe` |
| 3.10 | 3.10.20 | `python3.10.exe` |
| 3.11 | 3.11.15 | `python3.11.exe` |
| 3.12 | 3.12.13 | `python3.12.exe` |
| 3.13 | 3.13.15 | `python3.13.exe` |
| 3.14 | 3.14.7 | `python3.14.exe` |
| 3.15 | 3.15.0rc1 | `python3.15.exe` |

- Do not use `py -0p` to decide whether a runtime is installed. These
  `uv`-managed/user-level interpreters are not necessarily registered with the
  Windows Python launcher. Invoke every versioned shim directly and confirm
  `--version` before testing.
- Every planned feature task must run its full test suite on all seven minors,
  not just the default `.venv`. Run 3.15 with
  `-W error::DeprecationWarning`. Treat a missing or non-runnable shim as an
  environment regression to diagnose, not as evidence that the runtime was
  never installed.
- Use isolated per-version environments (for example, `uv run --isolated
  --python <shim> --extra dev python -m pytest`) so dependencies and bytecode do
  not leak between minors. If the default `uv` cache cannot initialize, point
  `UV_CACHE_DIR` at a writable task-specific directory under `$env:TEMP`.
