# Repository agent instructions

When a request refers to "the plan", "the next task", or "the next remaining
task", read `docs/AGENT_TASK_PLAN.md` completely before editing anything.
Requests to edit these repository instructions or the task plan itself do not
select or start the next implementation task unless they explicitly ask to
complete that task.

`docs/AGENT_TASK_PLAN.md` is longer than the terminal tool's reliable output
limit. Do not begin with one whole-file `Get-Content -Raw` call and wait for it
to truncate. First obtain the total line count, then read the file in ordered,
non-overlapping chunks of at most 200 lines. Use a separate tool call for each
chunk rather than combining all chunks into one large result. Cover every line
from the first through the reported last line, and treat any truncation warning
as an incomplete read that must be retried with a smaller chunk before editing.
`docs/AGENT_TASK_PLAN_ARCHIVE.md` contains completed historical specifications
and is not part of this mandatory read unless the selected task explicitly
requires that history.

- Resume the single `IN_PROGRESS` task. If none exists, select with milestone
  precedence: while any Milestone 1 (`Q`-series) task is not `DONE`, only `Q`
  tasks are eligible, and Milestone 2 (`P`-series) tasks become eligible only
  after Q05 is `DONE`. Within the active milestone, take the lowest-numbered
  `TODO` task whose dependencies are `DONE`.
- Complete exactly one task per invocation. Do not begin, research, or partially
  implement the following task.
- Follow the plan's scope, exclusions, acceptance tests, release gate, status
  update procedure, and commit title.
- Preserve pre-existing worktree changes. They belong to the task identified in
  the plan unless the plan explicitly says otherwise.
- Before running hooks or isolated tests, use the repository's persistent,
  ignored artifact caches. Environment and bytecode isolation remain mandatory;
  downloaded hook and package artifacts may be reused across tasks:

  ```powershell
  $cacheRoot = Join-Path (Resolve-Path -LiteralPath ".") ".agent-cache"
  $env:PRE_COMMIT_HOME = Join-Path $cacheRoot "pre-commit"
  $env:UV_CACHE_DIR = Join-Path $cacheRoot "uv"
  ```

- Install hooks once per checkout, not once per task. Run
  `python -m pre_commit install --install-hooks` only when `.git/hooks/pre-commit`
  or `.git/hooks/commit-msg` is absent. Hook installation and execution must use
  the same permission boundary: if installation requires scoped approval,
  subsequent hook runs using that cache require the same boundary.
- Use `scripts/release_gate.ps1` for the default suite, seven-runtime matrix,
  build, clean-wheel installation, and smoke test. On a host with restricted
  network access, request one scoped approval before this known dependency-
  resolving command instead of first running a download that is expected to
  fail. Isolation must not be weakened.
- After the release script passes, stage only the selected task files, including
  every newly created file, because `pre_commit run --all-files` does not include
  untracked files. Run the repository-wide
  `python -m pre_commit run --all-files --show-diff-on-failure` exactly once,
  after staging. If a fixer changes files, inspect the diff, restage only task
  files, rerun affected tests and this hook suite, and do not proceed until it
  is clean.
- Commit normally so both the pre-commit and Conventional Commit message hooks
  execute. Never use `--no-verify`, `SKIP`, or another hook bypass. If a fixer
  changes files, inspect the diff, restage only task files, rerun affected tests
  and all hooks, and then retry the commit.
- Update the selected task to `DONE` (or `BLOCKED`) and update the dashboard in
  the same commit as the implementation. After that local commit, run only
  `git status --short` and `git log -1 --oneline` to verify the handoff, then
  stop. Never push; this repository intentionally has no remote.

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
  --python <shim> --extra dev python -m pytest -p no:cacheprovider`) so
  dependencies and bytecode do not leak between minors and pytest does not
  attempt to write a shared repository cache. The shared UV directory is only
  an artifact cache. Dependency resolution can require network access; use the
  release script under one scoped approval on restricted hosts rather than
  silently omitting a check.
