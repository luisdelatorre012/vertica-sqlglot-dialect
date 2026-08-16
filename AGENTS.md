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
