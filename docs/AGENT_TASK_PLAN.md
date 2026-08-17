# Sequential agent implementation plan

This is the executable backlog for continuing the coverage-driven Vertica
dialect. It is intentionally written for a capable **Sol Medium** agent working
one bounded slice at a time.

The architectural target remains OpenText Analytics Database 26.2, SQLGlot
30.13.x, and Python 3.9 through 3.15. `docs/COVERAGE.md` defines the public
coverage contract; this file defines implementation order.

The backlog is organized into two major milestones:

- **Milestone 1 — analysis parsing surface.** The project's first deliverable
  is parsing, analyzing, and regenerating the statement classes an analysis
  workload actually contains: `SELECT` queries (joins, subqueries, set
  operations), common table expressions, and temporary-table creation and
  cleanup. No database-management capability is required for this milestone.
  Its tasks carry `Q` numbers.
- **Milestone 2 — administration and remaining DDL.** Everything else —
  flex tables, stored procedures and SQL functions, partition maintenance,
  library/UDx alterations, and cluster/Eon/TLS/cryptographic administration —
  is deferred until Milestone 1 is certified; detailed specifications live in
  [AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md). Its tasks
  keep their original `P` numbers; do not renumber them, because completion
  records and coverage notes reference those IDs.

## Copy-paste prompt

The repository-level `AGENTS.md` makes this prompt sufficient:

> Complete the next remaining task in the plan and update progress to mark this
> task as complete. Do not complete multiple tasks.

## Current state

- Completed through **P15 — Ordinary constraint conformance**. P01–P15 are the
  completed foundation; their specifications and completion records are
  archived in [AGENT_TASK_PLAN_ARCHIVE.md](AGENT_TASK_PLAN_ARCHIVE.md).
- On 2026-08-16 the backlog was split into the two milestones above. Parser
  probes against the installed development environment verified that the
  Milestone 1 surface is already largely delivered by the completed
  foundation: plain/multiple/recursive CTEs with materialization hints,
  joins, subqueries, `MINUS`/`EXCEPT` set operations, `LIMIT … OVER`,
  definition-form temporary tables with `ON COMMIT`/`NO PROJECTION`,
  unscoped temporary CTAS, `INSERT … SELECT` (including target-following
  `WITH`), and single-target `DROP TABLE [IF EXISTS] … [CASCADE]` all parse
  and round-trip. The same probes confirmed three gaps inside the Milestone 1
  scope, now tasks Q01–Q03: scoped temporary CTAS raises a deliberate
  `ParseError`, the documented `SELECT … INTO [scope] TEMP[ORARY] [TABLE] …
  [ON COMMIT …]` clause does not parse (the 26.2 doc page's own example
  fails), and multi-target `DROP TABLE` lists do not parse.
- Next eligible tasks are selected milestone-first: every Q task must be
  `DONE` before any P task is eligible.
- Completed **Q02 — SELECT INTO TABLE clause conformance**. Q03 is the
  lowest-numbered remaining task.
- On 2026-08-16 the embedded foreign-property `KeyError` gap recorded by
  Q01 was scheduled as new task Q05, and the acceptance gate was renumbered
  Q05 → Q06 before any gate work began; no completion record references the
  old gate number.
- There is intentionally no Git remote. Make local commits only; never push.

## Installed local Python runtimes

The Windows development host has every supported CPython minor installed and
testable through versioned shims in `C:\Users\luisd\.local\bin`:

| Minor | Installed release | Executable       |
| ----- | ----------------- | ---------------- |
| 3.9   | 3.9.25            | `python3.9.exe`  |
| 3.10  | 3.10.20           | `python3.10.exe` |
| 3.11  | 3.11.15           | `python3.11.exe` |
| 3.12  | 3.12.13           | `python3.12.exe` |
| 3.13  | 3.13.15           | `python3.13.exe` |
| 3.14  | 3.14.7            | `python3.14.exe` |
| 3.15  | 3.15.0rc1         | `python3.15.exe` |

These interpreters are managed outside the Windows Python launcher registry,
so `py -0p` is not an authoritative inventory and can show only the older
system 3.12 installation. Agents must invoke each versioned shim directly.
Historical completion records below describe what was actually run at the time
and must not be used to infer current runtime availability. Do not rewrite
those records to match the current host; the table above and fresh `--version`
checks are authoritative for new tasks.

## Reading installed SQLGlot source

Auditing "current SQLGlot parse/generate behavior" (required before every
task) means reading the installed `sqlglot` package's actual source, not
recalling an older version from memory. SQLGlot 30.13 restructured its
internals into subpackages, so a guessed flat-file path can fail even though
the file genuinely exists somewhere under the package — for example,
`sqlglot/expressions.py` does not exist in 30.13; `sqlglot.expressions` is a
package, and canonical expression classes are grouped by topic into
submodules such as `sqlglot.expressions.constraints` (constraint-kind nodes)
and `sqlglot.expressions.core` (`Expression`, `ColumnConstraintKind`, and
other base machinery). The base `Parser`/`Generator` classes remain flat
files at `sqlglot.parser`/`sqlglot.generator`, but each dialect's own parser
and generator mixin lives in a separate per-dialect submodule instead:
`sqlglot.parsers.<dialect>` / `sqlglot.generators.<dialect>` (for example
`sqlglot.parsers.postgres.PostgresParser`, `sqlglot.generators.sqlite`).
This is distinct from `sqlglot.dialects.<dialect>`, which holds only the
`Dialect` subclass, tokenizer, and `EXPRESSION_METADATA`.
`VerticaParser`/`VerticaGenerator` subclass the `sqlglot.parsers.postgres`/
`sqlglot.generators.postgres` mixins (see the imports at the top of
`src/sqlglot_vertica/parser.py` and `generator.py`), not
`sqlglot.dialects.postgres.Postgres` directly.

Rather than guessing a path, resolve the real submodule file with Python
first, then read that resolved path normally with the ordinary file tools:

```powershell
.venv/Scripts/python.exe -c "import sqlglot.expressions.constraints as m; print(m.__file__)"
```

This also matters when checking whether a foreign dialect's generator has
its own handling for a canonical node class (relevant to the foreign-dispatch
hazard noted under AST policy in `ARCHITECTURE.md`): check both
`sqlglot.generators.<dialect>` for a same-named render method and any
dialect-level statement preprocessing that can run before per-node dispatch
(for example SQLite's `_transform_create` in `sqlglot/generators/sqlite.py`,
which structurally rewrites parts of a `CREATE TABLE` tree by `isinstance`
before generation).

## Repository map and code anchors

`src/sqlglot_vertica/parser.py` (~8,200 lines) and
`src/sqlglot_vertica/generator.py` (~5,300 lines) are too large for
whole-file reads. Locate the work site by searching for the symbol names
below, then read only the enclosing method and the dispatch table that
registers it. Anchors verified 2026-08-16; if one is missing, search for the
family name instead of assuming it was removed.

- `parser.py` — `VerticaParser(PostgresParser)`; statement families parse in
  `_parse_<family>` methods. High-traffic entry points: the CREATE TABLE
  dispatch (`_parse_create_table`, `_parse_create_table_ctas`), the guarded
  DROP front door `_parse_drop` (lookahead rejections, then per-kind
  `_parse_drop_<kind>` helpers such as `_parse_drop_view` and
  `_parse_drop_schema`), and the SELECT post-validation override
  `_parse_select_query`. Guaranteed-raise validation wrappers are named
  `_raise_<family>_error`; grep `def _raise_` for the current set.
- `generator.py` — `VerticaGenerator`: one `<node>_sql` method per node plus
  strict validation helpers mirroring the parser families.
- `expressions.py` — every custom `vexp.*` node and its `arg_types`.
- `dialect.py` / `tokens.py` — dialect wiring and tokenizer deltas.
- `dml.py` / `user_limits.py` — INSERT/UPDATE/DELETE/MERGE validation and
  USER limit domains, split out of the parser.
- `tests/helpers.py` — `assert_roundtrip(sql, expected)` asserts
  non-`Command` parse, compact and pretty round-trips, reparse equality, and
  `dump()`/`load()` stability in one call; use it for positive cases.
- Tests: one `tests/test_<area>.py` module per family. Before writing a new
  module, copy the structure of the nearest sibling (`test_create_table.py`
  for table work, `test_schema_view.py` for lifecycle and multi-target DROP
  families).

## Status dashboard

Allowed states are `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`. At most one
task may be `IN_PROGRESS` across all tables.

### Completed foundation (pre-milestone)

| ID  | Status | Task                                          | Required dependency | Commit title                                            |
| --- | ------ | --------------------------------------------- | ------------------- | ------------------------------------------------------- |
| P01 | DONE   | PROFILE lifecycle                             | `6ca2a0d`           | `feat: model profile lifecycle`                         |
| P02 | DONE   | Executable `PROFILE` statement                | P01                 | `feat: model profiled statement execution`              |
| P03 | DONE   | USER profile and resource-pool assignments    | P01                 | `feat: add user workload assignments`                   |
| P04 | DONE   | USER time and capacity limits                 | P03                 | `feat: model non-secret user limits`                    |
| P05 | DONE   | USER search path and default roles            | P03                 | `feat: model user path and default roles`               |
| P06 | DONE   | Safe USER configuration/reset actions         | P04, P05            | `feat: model safe user configuration actions`           |
| P07 | DONE   | AUTHENTICATION create/drop core               | P06                 | `feat: model authentication creation and drop`          |
| P08 | DONE   | AUTHENTICATION structural ALTER actions       | P07                 | `feat: model authentication alter actions`              |
| P09 | DONE   | AUTHENTICATION SET security boundary          | P08                 | `feat: add safe authentication parameters`              |
| P10 | DONE   | COMMENT ON family                             | P02                 | `feat: make Vertica comment statements semantic`        |
| P11 | DONE   | VIEW lifecycle                                | P10                 | `feat: complete semantic view lifecycle`                |
| P12 | DONE   | SCHEMA lifecycle                              | P11                 | `feat: complete semantic schema lifecycle`              |
| P13 | DONE   | Administrative privilege targets              | P09                 | `feat: complete administrative privilege targets`       |
| P14 | DONE   | Access-policy lifecycle                       | P13                 | `feat: model access policy lifecycle`                   |
| P15 | DONE   | Ordinary constraint conformance               | P12                 | `feat: enforce Vertica constraint grammar`              |

### Milestone 1 — analysis parsing surface

Every Q task must be `DONE` before any Milestone 2 task becomes eligible.

| ID  | Status | Task                                          | Required dependency | Commit title                                            |
| --- | ------ | --------------------------------------------- | ------------------- | ------------------------------------------------------- |
| Q01 | DONE   | Scoped temporary CTAS acceptance              | —                   | `feat: accept scoped temporary ctas`                    |
| Q02 | DONE   | SELECT INTO TABLE clause conformance          | —                   | `feat: model select into table targets`                 |
| Q03 | TODO   | DROP TABLE grammar completion                 | —                   | `feat: complete drop table grammar`                     |
| Q04 | TODO   | Official query-corpus hardening               | —                   | `test: add official query corpus`                       |
| Q05 | TODO   | Foreign embedded-property atomicity           | —                   | `fix: close embedded property foreign atomicity gap`    |
| Q06 | TODO   | Milestone 1 acceptance gate                   | Q01–Q05             | `test: certify milestone one analysis surface`          |

### Milestone 2 — administration and remaining DDL (deferred)

Deferred until Q06 is `DONE`. Task numbering, dependencies, and
specifications are intentionally unchanged from the prior plan revision.

| ID  | Status | Task                                          | Required dependency | Commit title                                            |
| --- | ------ | --------------------------------------------- | ------------------- | ------------------------------------------------------- |
| P16 | TODO   | Native flexible-table definition form         | P15                 | `feat: model native flexible table definitions`         |
| P17 | TODO   | Flexible-table CTAS                           | P16                 | `feat: model flexible table ctas`                       |
| P18 | TODO   | Flex map transform core                       | P16                 | `feat: model flex map transforms`                       |
| P19 | TODO   | ALTER LIBRARY                                 | P10                 | `feat: model library alterations`                       |
| P20 | TODO   | Common factory-backed UDx metadata ALTER      | P19                 | `feat: model factory udx alterations`                   |
| P21 | TODO   | Partition-maintenance completion              | P12                 | `feat: complete partition maintenance actions`          |
| P22 | TODO   | Routine-body parsing foundation               | P20                 | `feat: add routine body parsing foundation`             |
| P23 | TODO   | Stored-procedure CREATE shell                 | P22                 | `feat: model stored procedure creation shells`          |
| P24 | TODO   | Stored/external procedure DROP discrimination | P23                 | `feat: distinguish stored and external procedure drops` |
| P25 | TODO   | Fault-group lifecycle                         | P14                 | `feat: model fault group lifecycle`                     |
| P26 | TODO   | Node administration                           | P25                 | `feat: model node alterations`                          |
| P27 | TODO   | Standard namespace lifecycle                  | P16                 | `feat: model namespace lifecycle`                       |
| P28 | TODO   | Eon subnet lifecycle                          | P27                 | `feat: model subnet lifecycle`                          |
| P29 | TODO   | Eon subcluster alterations                    | P28                 | `feat: model subcluster alterations`                    |
| P30 | TODO   | Storage-location administration               | P29                 | `feat: model storage location administration`           |
| P31 | TODO   | Archive lifecycle                             | P30                 | `feat: model archive lifecycle`                         |
| P32 | TODO   | TLS-configuration lifecycle                   | P13                 | `feat: model tls configuration lifecycle`               |
| P33 | TODO   | Non-secret cryptographic-object core          | P32                 | `feat: add non-secret cryptographic object core`        |
| P34 | TODO   | SQL-expression function lifecycle             | P22, P24            | `feat: model sql function lifecycle`                    |
| P35 | TODO   | Coverage audit and queue refresh              | P01–P34             | `docs: refresh remaining sql coverage backlog`          |

## Task-selection and status protocol

1. Read this entire file, the selected task's detailed specification
   (Milestone 1 tasks are below; Milestone 2 tasks are in
   [AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md)),
   `docs/ARCHITECTURE.md`, and the relevant rows in `docs/COVERAGE.md` and
   `docs/ROADMAP.md`.
2. If a task is `IN_PROGRESS`, resume it. Otherwise select the next eligible
   task with milestone precedence: while any Milestone 1 (`Q`-series) task is
   not `DONE`, only `Q` tasks are eligible; Milestone 2 (`P`-series) tasks
   become eligible only after Q06 is `DONE`. Within the active milestone,
   select the lowest-numbered `TODO` task whose dependencies are all `DONE`,
   change it to `IN_PROGRESS` in both the dashboard and its detail heading,
   and do no other task.
3. Inspect `git status` and `git diff` before editing. Never discard or overwrite
   unrelated changes. If unexpected changes overlap the selected task, mark it
   `BLOCKED` with an exact explanation and stop.
4. Re-open every linked OpenText 26.2 primary source before implementation.
   Record any material documentation contradiction in the task completion note;
   do not resolve it by guessing server behavior. When primary-source sections
   conflict, prefer the formal syntax and parameter tables over examples unless
   a 26.2 server fixture proves otherwise, and record that choice. When a task
   asks to pin a broad value grammar, document representative accepted,
   rejected, boundary, and canonical-output examples before implementation.
5. Implement only the stated scope. Explicit exclusions must either retain their
   already-documented behavior or fail closed when they are recognized members
   of the newly semantic family.
6. Run the common release gate and all task-specific tests. Fix failures within
   scope; do not begin the next task. If the gate is blocked by a defect in
   shared release infrastructure that would block every task (as Q01 found
   with the release driver's task-ID pattern), fix that infrastructure within
   the task and record it. If testing exposes a cross-cutting product defect
   beyond the task's scope, record it in the completion record and the
   relevant policy or architecture notes, and propose it as its own bounded
   task rather than expanding the current one.
7. Update the coverage matrix, roadmap, sources, architecture, and changelog as
   applicable. Change this task to `DONE`, update the dashboard, and add a short
   completion record with test counts and any deliberate boundary.
8. Stage only the selected task and its plan/status updates, including all newly
   created files, before the single versioned pre-commit run. This ensures
   `pre_commit run --all-files` covers files that were previously untracked. If
   a fixer changes files, inspect the diff, restage only task files, rerun
   affected tests and the hook suite, and do not proceed until it is clean.
9. Commit locally with the exact listed title so the installed code-quality and
   commit-message hooks execute. Never use `--no-verify`, `SKIP`, or another
   hook bypass. After the commit, run only `git status --short` and
   `git log -1 --oneline` to verify a clean handoff and the expected commit,
   then stop.
10. If completion is genuinely impossible, set `BLOCKED`, document the exact
   repeated blocker and evidence, commit the status/docs if useful, and stop.
   Never skip ahead automatically.

## Execution-efficiency notes

- Iterate against the focused test module only
  (`.venv/Scripts/python.exe -m pytest tests/test_<area>.py -q`). Do not run
  the full default suite, the seven-runtime matrix, or `pre_commit` while
  iterating: the release driver runs each required check exactly once at the
  end, and a full gate attempt costs several minutes.
- Open each primary-source page once per task and extract everything needed
  while it is open — the formal syntax block, the parameter tables, and
  every worked example. Repeated partial fetches of the same page are the
  largest avoidable cost after redundant test runs.
- Navigate the two large source files by symbol search (see the repository
  map above), never by sequential whole-file reads.

## Architecture and parser policy

These rules apply to every implementation task:

- Prefer canonical SQLGlot nodes when they preserve Vertica semantics exactly.
  Otherwise use the closest canonical subclass with typed children. Avoid raw
  strings and generic `exp.Command` for a family marked Semantic.
- Every custom node needs explicit Vertica generation, `arg_types`, serialization
  stability, correct parent/`arg_key`/`index` links, and an intentional optimizer
  and type-annotation policy.
- Custom roots and detached custom leaves must fail atomically in foreign
  dialects under `unsupported_level=RAISE` unless the task documents a safe
  lowering. Never allow foreign generation to silently drop a clause.
- The standard bare-instantiation foreign-atomicity sweep (`vexp.SomeClass().sql(dialect=...)`)
  does not prove a custom `exp.Property` subclass fails atomically once it is
  actually embedded in a real `exp.Properties` list: `Generator.locate_properties`
  indexes `self.PROPERTIES_LOCATION` with a plain dict lookup before any
  per-node dispatch runs, so a foreign dialect with no entry for the class
  raises raw `KeyError`, not `UnsupportedError`. This is a confirmed,
  cross-cutting, pre-existing gap across every custom Vertica table property
  (see `ARCHITECTURE.md`'s AST-policy section for the mechanism and evidence);
  do not treat the generic sweep as proof for a `Property` subclass, and do
  not assume `KeyError` from a new feature's foreign-generation test is a
  regression it introduced without first checking whether the same property
  already crashes the same way in its pre-existing context. Closing this gap
  is scheduled as task Q05.
- Recognized malformed Vertica syntax must raise `ParseError`; it must not fall
  back to `exp.Command`, truncate a tail, or emit a warning and partial AST at
  any `ErrorLevel`.
- Plain `self.raise_error(...)` does not by itself satisfy the rule above: at
  `ErrorLevel.RAISE` it only appends to `self.errors` (nothing raises until
  something later calls `check_errors()`), and at `WARN`/`IGNORE` it neither
  raises nor aggregates usefully, so unguarded downstream code can silently
  continue with a `None`/default value, and code that assumes the statement
  already failed (for example an `assert x is not None` placed right after)
  can crash with `AssertionError` instead of `ParseError`. New validation must
  go through a dedicated `_raise_<family>_error` wrapper: call `raise_error`,
  then `check_errors()` when `error_level == RAISE`, then an unconditional
  `raise ParseError(message)` when `error_level` is `IGNORE` or `WARN` (see
  `_raise_schema_error`, `_raise_view_error`, `_raise_constraint_error`, and
  siblings for the exact pattern). Add one such wrapper per new statement
  family rather than reusing an unrelated family's wrapper. This has not been
  retrofitted onto every pre-existing call site, so an existing bare
  `self.raise_error(...)` elsewhere in the file is not proof the pattern is
  safe to copy for new work; grep for `def _raise_.*_error` for the current
  set of guaranteed-raise wrappers before adding a new one.
- Keep contextual words contextual. Do not add tokenizer keywords unless primary
  grammar and collision tests prove it necessary. Require exact unquoted ASCII
  provenance for object/action keywords where Unicode case folding could change
  meaning.
- Validate programmatic ASTs before rendering. Malformed containers, falsey
  extras, child types, flags, kinds, and values must yield `UnsupportedError`,
  never raw `TypeError`, `KeyError`, `AttributeError`, or partial SQL.
- Do not use `int()` on unbounded source digits. Validate sign, range, and large
  values lexically so behavior is stable on Python 3.9–3.15.
- Preserve the established identifier contract: parser/generator token parity,
  safe quoting, UTF-8 length rules where Vertica documents them, surrogate
  handling, and collision tests.
- Catalog-dependent existence, privilege, topology, type, and state checks stay
  server-side and must be documented rather than guessed.
- Secret-bearing values require a pre-AST security design. Synthetic sentinel
  tests must prove absence from ASTs, dumps, exceptions, warnings, logs, and
  stderr across every supported literal token form and `ErrorLevel`. Never add
  real credentials to fixtures.
- Do not change the SQLGlot dependency line, project version, Python range, or
  public compatibility policy unless a task explicitly authorizes it.

## Release environment and permissions

Release environments and bytecode remain isolated, but downloaded artifacts
are intentionally shared across tasks. Use the ignored repository-local cache:

```powershell
$cacheRoot = Join-Path (Resolve-Path -LiteralPath ".") ".agent-cache"
$env:PRE_COMMIT_HOME = Join-Path $cacheRoot "pre-commit"
$env:UV_CACHE_DIR = Join-Path $cacheRoot "uv"
```

Install pre-commit and commit-message hooks once per checkout, and only when
either `.git/hooks/pre-commit` or `.git/hooks/commit-msg` is absent. Do not
reinstall hooks for each task. Hook installation and execution must use the
same permission boundary; a cache created by an approved outside-sandbox
installation must not subsequently be invoked from a boundary that cannot read
it. The repository-local cache avoids that mismatch on the current host.

Dependency-resolving release commands are predictably network-capable. On a
restricted host, request one scoped approval for the checked-in release driver
before running it; do not first perform a download that is already expected to
fail. This approval changes access, not test isolation or required coverage.

## Common release gate

Every feature task must complete all applicable checks:

1. Focused positive and negative tests for the new family and neighboring
   dispatch families.
2. AST-class/field assertions; compact and pretty parse → generate → reparse
   equality; comments and multi-statement boundaries.
3. `dump()`/`Expression.load()`, `copy()`, `transform()`, exact parent metadata,
   optimizer stability, and type annotation where relevant.
4. Source negatives at `IMMEDIATE`, `RAISE`, `WARN`, and `IGNORE`, proving no
   `Command` fallback, truncation, internal exception, or sensitive logging.
5. Strict programmatic-AST mutation matrix and direct/nested foreign generation
   against at least PostgreSQL, DuckDB, MySQL, and SQLite.
6. Identifier provenance, quoted payload, Unicode/confusable, reserved-token,
   127/128/129-byte, invalid UTF-8, huge-number, prefix-modifier, and neighboring
   statement collision cases where applicable.
7. Full default-runtime suite with branch coverage at or above 90%, plus Ruff
   lint and formatting, strict mypy, and `git diff --check`. The release driver
   in step 8 runs all of these checks; do not repeat them separately unless
   diagnosing a failure. A guaranteed-raise `_raise_<family>_error` wrapper's
   final `if error_level in {IGNORE, WARN}: raise ParseError(...)` line will
   show as a partially covered branch (`N->exit`) in the coverage report even
   with a full `ErrorLevel` sweep tested: reaching that `if` at all already
   proves `error_level` is `IGNORE` or `WARN` (`IMMEDIATE` raises earlier
   inside `raise_error` itself; `RAISE` always raises from the preceding
   `check_errors()` call), so the "condition is false" exit is unreachable
   dead code, not a real gap. Every existing wrapper shows this same pattern;
   do not add tests chasing it.

8. Full tests on every installed supported runtime, CPython 3.9 through 3.15,
   plus the sdist/wheel build and clean installed-wheel smoke. Use the checked-in
   release driver, supplying one distinctive statement and expected root class:

   ```powershell
   ./scripts/release_gate.ps1 -TaskId pNN `
       -SmokeSql "TASK-DISTINCTIVE SQL" `
       -ExpectedClass "ExpectedExpressionClass"
   ```

   Sanity-check `-SmokeSql`/`-ExpectedClass` locally first with a plain
   `parse_one(sql, read="vertica")` / `.sql(dialect="vertica")` round-trip and
   an `isinstance` check against the expected class. A full run costs several
   minutes (the default suite, all 7 isolated runtimes, and a clean sdist/wheel
   build and install), so a typo or a clause-order mistake in the smoke SQL
   itself is an expensive way to fail the last step.

   The script uses persistent ignored PRE_COMMIT/UV artifact caches, but creates
   isolated per-version environments and a unique clean wheel environment. It
   invokes every documented versioned shim directly, treats Python 3.15
   deprecations as errors, builds without isolation, force-installs the exact
   wheel with `uv pip install`, runs `pip check`, performs the `python -I`
   entry-point smoke, and guards cleanup paths. A missing shim remains an
   environment regression to diagnose with `uv python install <minor>
   --upgrade`; never skip it.
9. On hosts with restricted network access, request one scoped approval before
   the release driver because dependency resolution is predictably network-
   capable. Do not deliberately run a known-failing sandbox download first.
   After all implementation and documentation files are staged, run
   `pre_commit run --all-files --show-diff-on-failure` exactly once using the
   same permission boundary as hook installation. Commit hooks still run
   normally and must never be bypassed.

## Detailed tasks — completed foundation

Completed task specifications and completion records for P01–P15 are archived
in [AGENT_TASK_PLAN_ARCHIVE.md](AGENT_TASK_PLAN_ARCHIVE.md). They are
historical context and are not part of the mandatory active-plan read. The
active backlog starts at the Milestone 1 section that follows.

## Detailed tasks — Milestone 1: analysis parsing surface

These six bounded tasks close the verified gaps between the completed
foundation and the milestone goal — parsing, analyzing, and regenerating
`SELECT`/CTE/temporary-table workloads — and retire the one recorded
cross-cutting policy violation inside that surface (Q05). No
database-management capability is in scope in this milestone.

### Q01 — scoped temporary CTAS acceptance — `DONE`

**Outcome.** Accept `CREATE { GLOBAL | LOCAL } TEMP[ORARY] TABLE … AS query`
with the same typed contract as unscoped temporary CTAS, recording the
documented grammar conflict.

**Required work.** Remove the deliberate scope rejection in the
temporary-CTAS dispatch (`_parse_create_table_ctas` raises "GLOBAL or LOCAL
scope is not supported for temporary CTAS", pinned in `test_create_table.py`)
and give scoped temporary CTAS exactly the unscoped contract: optional
column-name list, `ON COMMIT { DELETE | PRESERVE } ROWS` before `AS`, hints,
and the currently supported post-query clauses, with scope and
`TEMP`/`TEMPORARY` spelling handled consistently with the definition form.
Accept parenthesized query bodies (`AS (SELECT …)`) if any gap exists, since
ecosystem tooling emits them. Record the source conflict: the 26.2 CREATE
TEMPORARY TABLE page splits its formal syntax into a column-definition block
(with scope) and an AS-query block (without scope), with no example either
way, while working Vertica deployments and ecosystem tooling (for example the
dbt-vertica adapter's `CREATE LOCAL TEMPORARY TABLE … ON COMMIT PRESERVE ROWS
AS (SELECT …)` materializations) exercise scoped temporary CTAS routinely.
This task explicitly authorizes preferring that operational evidence over the
formal block split under protocol rule 4's server-fixture escape hatch;
capture a concrete server fixture in the completion record if one is
available. Keep every other existing temporary-table restriction (for
example the definition-form `LOCAL … DISK_QUOTA` rejection) unchanged unless
the re-opened source contradicts it. Test both scopes, both spellings, both
`ON COMMIT` values, column lists, hints, parenthesized queries, unscoped
regression parity, LIKE/definition-form dispatch neighbors, serialization,
and foreign-generation policy consistent with the existing CTAS contract.

**Explicit exclusions.** Flex temporary tables (Milestone 2), `SELECT … INTO`
(Q02), catalog/session scope effects, and projection creation.

**Primary sources.** [CREATE TEMPORARY TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-temporary-table/)
and [Creating temporary tables](https://docs.vertica.com/26.2.x/en/admin/working-with-native-tables/creating-temporary-tables/).

**Completion record.** Removed the deliberate `if scope: raise` block from
`_parse_create_table_ctas` in `src/sqlglot_vertica/parser.py`. `scope` is
already reflected in `properties` by the caller (`_parse_create_table`) as a
canonical `GlobalProperty`/detached `LocalProperty` before the CTAS dispatch
ever runs, so no other branch needed to change for column lists,
`ON COMMIT`, hints, `ENCODED BY`, `AT EPOCH`/`AT TIME`, or parenthesized query
bodies (`AS (SELECT …)`, already handled losslessly by the inherited
`_parse_ddl_select`/`_parse_select(nested=True)` path) — all were already
scope-blind and unaffected once the rejection was removed. Re-opening both
26.2 primary sources confirmed the task's framing of the grammar conflict
exactly: the CREATE TEMPORARY TABLE page's formal syntax splits a
column-definition block (with `scope`) from an AS-query block (without
`scope`), with no worked example either way on that page or the admin
"Creating temporary tables" guide. That same page's `DISK_QUOTA` parameter
description — "Disk quota is valid for global temporary tables but not local
ones" — is written once, covering both syntax forms, rather than per-block;
this is direct textual evidence that the LOCAL/`DISK_QUOTA` restriction is
meant to apply to any local temporary table, not only the column-definition
form. Per that evidence and the task's server-fixture escape hatch, the
LOCAL/`DISK_QUOTA` rejection already enforced by the definition form was
extended, verbatim, to the CTAS `DISK_QUOTA` clause; no 26.2 server was
available to capture a live fixture, so this rests on the shared
parameter-table wording plus the task-authorized ecosystem evidence
(dbt-vertica's `CREATE LOCAL TEMPORARY TABLE … ON COMMIT PRESERVE ROWS AS
(SELECT …)` materializations) rather than a captured server response. Every
other post-query clause is unchanged and scope-blind, matching "exactly the
unscoped contract"; `INCLUDE`/`EXCLUDE PRIVILEGES` remains unavailable to
temporary CTAS regardless of scope, consistent with the pre-existing (not
Q01-introduced) `if temporary: on_commit … else: privileges` exclusivity
already in the CTAS dispatch. Testing the required foreign-generation matrix
surfaced a pre-existing, cross-cutting defect predating this task and
documented in `ARCHITECTURE.md`'s AST-policy section and the policy rules
above: any custom Vertica table `Property` embedded in a real `CREATE TABLE`
`Properties` list — not only the newly-scoped `LocalProperty` — raises raw
`KeyError` rather than `UnsupportedError` in PostgreSQL, DuckDB, MySQL, and
SQLite, because `Generator.locate_properties` indexes `PROPERTIES_LOCATION`
directly and no foreign dialect registers Vertica-only property classes; this
reproduces identically, independent of scope and of this task, for unscoped
CTAS's own `InheritedPrivilegesProperty` (`CREATE TABLE t INCLUDE PRIVILEGES
AS SELECT 1 AS id` against `postgres`). Foreign generation still never
silently drops the clause — failure remains atomic — but the exception type
is not the intended one; fixing it is a cross-cutting change spanning every
custom table property across the whole physical-design surface, so it is
recorded rather than fixed in this bounded task. `GLOBAL` scope's foreign
behavior is unaffected and matches the pre-existing definition-form/CTAS
pattern exactly: PostgreSQL and MySQL accept canonical `GlobalProperty`,
DuckDB and SQLite cleanly raise `UnsupportedError`. Separately,
`scripts/release_gate.ps1`'s `-TaskId` parameter validated only `^p\d{2}$`,
left over from before the 2026-08-16 milestone split introduced `Q`-prefixed
task IDs; this would have blocked every Milestone 1 task's release gate, not
just this one, so the pattern was widened to `^[pq]\d{2}$` as necessary
infrastructure for this task's own mandatory release-gate step. Column-
definition/LIKE dispatch neighbors, unscoped regression parity, and both
scopes/spellings/`ON COMMIT` values/column lists/hints/parenthesized bodies
are covered. The focused `test_create_table.py` suite passed 86 tests. The
default CPython 3.12.6 gate passed 4887 tests at 93.24% branch coverage;
isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and
3.15.0rc1 suites each passed 4887 tests, with 3.15 treating deprecations as
errors. Ruff, formatting, strict mypy, sdist/wheel build, clean force-install,
`pip check`, and installed-wheel entry-point/scoped-temporary-CTAS round-trip
smoke passed.

### Q02 — SELECT INTO TABLE clause conformance — `DONE`

**Outcome.** Make the documented `INTO TABLE` clause of `SELECT` parse and
generate valid Vertica for permanent and temporary targets.

**Required work.** Implement `INTO [TABLE]
[[{namespace.|database.}]schema.]table` and `INTO [GLOBAL|LOCAL]
TEMP[ORARY] [TABLE] [[database.]schema.]table [ON COMMIT {DELETE|PRESERVE}
ROWS]` per the 26.2 INTO TABLE clause page. The page's own example —
`SELECT * INTO LOCAL TEMP TABLE newTempTableLocal ON COMMIT PRESERVE ROWS
FROM customer_dimension` — currently raises `ParseError`, and the unscoped
forms that do parse ride the inherited PostgreSQL SELECT INTO path and drop
the optional `TABLE` keyword as an accident rather than a contract. Type the
target so scope, spelling, and `ON COMMIT` are preserved exactly; make
`TABLE`-keyword canonicalization a deliberate, tested decision; keep the
query traversable and the target reachable for lineage. Reject foreign forms
(variable targets, PostgreSQL `STRICT`) and malformed tails atomically at
every error level through a guaranteed-raise `_raise_<family>_error` wrapper.
Test permanent/temporary targets, every scope/spelling combination,
`ON COMMIT` placement, qualification shapes including namespace-qualified
permanent targets, dispatch neighbors (`INSERT INTO`, CTAS), serialization,
optimizer traversal, and foreign-generation policy.

**Explicit exclusions.** Target existence/collision, projection creation,
privileges, and load/export alternatives — server concerns.

**Primary source.** [INTO TABLE clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/into-table-clause/).

**Implementation pointers (non-normative, verified 2026-08-16).** The
inherited path is the base `sqlglot.parser.Parser._parse_into`, called from
`_parse_select`; `sqlglot.parsers.postgres` does not override it, and
`VerticaParser` has no `_parse_into` override yet. Canonical `exp.Into`
(`sqlglot.expressions.query`) carries only
`this`/`temporary`/`unlogged`/`bulk_collect`/`expressions` — no scope, no
`TEMP` spelling, no `ON COMMIT`, and no `TABLE`-keyword slot — so today
`INTO TABLE t` regenerates as `INTO t` and `INTO TEMP TABLE t` as
`INTO TEMPORARY t`. The base generator method is `Generator.into_sql`. Add
this family's own guaranteed-raise wrapper per the parser policy.

**Completion record.** Implemented both documented forms with a typed
two-node contract: `vexp.IntoTableClause` (an `exp.Into` subclass holding
the qualified target plus `temporary`/`spelling`/`scope`/`on_commit`) parsed
by a new `_parse_into` override, and `vexp.SelectInto` (an `exp.Select`
subclass, `TimeseriesSelect` precedent) that every SELECT carrying the
clause is promoted to at the end of `_parse_query_modifiers`. The custom
root is not optional styling: auditing base `Generator.select_sql` showed
that any generator with `SUPPORTS_SELECT_INTO = False` — DuckDB, MySQL, and
SQLite among the release-gate dialects — pops `Select.args["into"]` and
structurally rewrites the whole statement into `CREATE [TEMPORARY] TABLE …
AS …`, reading the popped node's args directly before per-node dispatch ever
runs, so a typed clause child alone can never fail atomically; the custom
root fails first (`ValueError`, `DropViews`-parity, at every
`unsupported_level`, direct and nested). The page's own
`SELECT * INTO LOCAL TEMP TABLE newTempTableLocal ON COMMIT PRESERVE ROWS
FROM customer_dimension` example now parses and round-trips byte-identically.
Scope, `TEMP`/`TEMPORARY` spelling, and `ON COMMIT` are preserved exactly as
written (absence stays absence); the optional `TABLE` keyword is the
deliberate canonicalization: it always regenerates, matching every worked
example on the 26.2 page, and is therefore not stored in the AST. Re-opening
the primary source found no material contradiction; recorded observation:
the formal syntax gives the permanent form `{namespace.|database.}schema.`
qualification but the temporary form only `[database.]schema.` — the two are
syntactically indistinguishable three-part names, so both forms accept up to
three identifier parts and the namespace/database distinction stays
server-side. Recognized malformed and foreign members fail closed through a
new `_raise_select_into_error` wrapper at all four error levels: scope
without `TEMP[ORARY]` (`INTO GLOBAL TABLE`), permanent `ON COMMIT`,
truncated/incorrect `ON COMMIT` tails, PL/pgSQL `INTO STRICT var`, Postgres
`INTO UNLOGGED [TABLE] t` (previously accepted by inheritance as
`unlogged=True` — a deliberate boundary change), comma-separated
variable-list targets, CTAS-style column lists, and over-qualified
(four-part) names. `STRICT`/`UNLOGGED`/`GLOBAL`/`LOCAL` stay contextual:
each is rejected only in its recognizable foreign/malformed shape
(lookahead-based) and still parses as an ordinary target name (`INTO local
FROM x`), with unquoted-ASCII provenance so quoted `"PRESERVE"`/`"GLOBAL"`
payloads never act as keywords. Canonical `exp.Into` from foreign-parsed
trees still renders (unscoped forms are valid Vertica), but a new Vertica
`into_sql` override rejects `unlogged`/`bulk_collect`/`expressions` with
`UnsupportedError` instead of emitting invalid `INTO UNLOGGED t`. A
`TimeseriesSelect` that also carries INTO keeps `TimeseriesSelect` as its
root (one atomic root suffices; the typed clause child still regenerates) —
covered by a dedicated test. Optimizer contract verified: `qualify`,
`optimize`, and `lineage` preserve the root class, resolve source columns,
and never treat the INTO target as a source relation. Two reusable
discoveries recorded for future tasks: SQLGlot 30.13's generator dispatch
(`_build_dispatch`) maps `<key>_sql` method names through canonical
`exp.EXPR_CLASSES` only, so a custom node's generator method is silently
unreachable until the class is registered in `TRANSFORMS` (both new nodes
are wired there), and the bare-instantiation foreign sweep in
`test_ast_safety.py` picks the two new classes up automatically. The focused
`test_select_into.py` module passed 181 tests; neighboring dispatch families
(query extensions, core statements, DML, CREATE TABLE, AST safety, hints,
keywords, schema/view) passed 880. The default CPython 3.12.6 gate passed
5070 tests at 93.30% branch coverage with Ruff, formatting, and strict mypy
clean; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7,
and 3.15.0rc1 suites each passed 5070 tests, with 3.15 treating deprecations
as errors. sdist/wheel build, clean force-install, `pip check`, and the
installed-wheel `python -I` entry-point smoke (scoped temporary INTO
round-trip returning `SelectInto`) passed.

### Q03 — DROP TABLE grammar completion — `TODO`

**Outcome.** Complete Vertica `DROP TABLE`: ordered multi-target lists with
`IF EXISTS` and `CASCADE`.

**Required work.** Re-open the 26.2 DROP TABLE page and support `DROP TABLE
[IF EXISTS] [[database.]schema.]table[,…] [CASCADE]`. Single-target
statements currently parse through canonical generic `exp.Drop`, including
`IF EXISTS`, qualification, and `CASCADE`; multi-target lists raise
`ParseError`. Follow the established ordered multi-target precedent
(`DropViews`/`DropSchemas`): retain canonical nodes where lossless and add an
atomic ordered root only for demonstrated loss. Once DROP TABLE becomes a
deliberate family, enforce exact modifier placement and reject modifiers the
re-opened page does not document. Test list order, `IF EXISTS` scope over
lists, `CASCADE` placement, temporary/permanent name shapes, dispatch
neighbors (`DROP VIEW`, `DROP SCHEMA`, `DROP PROJECTION`), serialization, and
atomic foreign failure for any custom node.

**Explicit exclusions.** Catalog existence, dependency effects, and
temporary-table auto-drop semantics.

**Primary source.** [DROP TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-table/).

**Implementation pointers (non-normative, verified 2026-08-16).** TABLE has
no per-kind branch in `_parse_drop`; single targets fall through to the base
parser's canonical `exp.Drop`. The ordered multi-target precedent is
`_parse_drop_view`/`_parse_drop_schema` building `vexp.DropViews`/
`vexp.DropSchemas`, and the lookahead-rejection block at the top of
`_parse_drop` is the established guard pattern for a family's negatives.
Nearest sibling tests: the DROP coverage in `test_schema_view.py`.

**Completion record.** Pending.

### Q04 — official query-corpus hardening — `TODO`

**Outcome.** Back the Generic `SELECT`/CTE coverage rows with the
long-planned official-example corpus and fix any mismatch it exposes.

**Required work.** Walk the 26.2 SELECT statement family pages — SELECT,
FROM/joins, WHERE, GROUP BY (including ROLLUP/CUBE/GROUPING SETS), HAVING,
ORDER BY, LIMIT/OFFSET (including the `LIMIT ALL` losslessness question
recorded in the coverage matrix), UNION/INTERSECT/EXCEPT/MINUS, subqueries,
and the WITH clause pages (recursive plus materialization hints) — and add
each documented example, adapted only where determinism requires, as
parse → AST-shape → compact/pretty round-trip regressions. Expand the
reserved-word collision corpus flagged in the lexical coverage row for query
positions. Promote or demote coverage statuses only with AST evidence, and
record named residuals rather than guessing.

**Explicit exclusions.** TIMESERIES/MATCH/INTERPOLATE (already Partial with
server-side residuals), structured hints (already covered), the INTO TABLE
clause page (Q02's contract), flex map functions (Milestone 2, P18), and
any new statement family.

**Primary sources.** [SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/)
and its clause subpages, including the WITH clause documentation.

**Implementation pointers (non-normative).** Use
`tests/helpers.py::assert_roundtrip` for the positive corpus; it already
asserts compact/pretty round-trips and `dump()`/`load()` stability. The
`docs/COVERAGE.md` rows this task re-evidences are the `SELECT`/CTE query
row ("additional official-example corpus planned"), the ordinary
`LIMIT`/`OFFSET`/`FETCH` row (`LIMIT ALL` losslessness), and the identifier
row's reserved-word collision note.

**Completion record.** Pending.

### Q05 — foreign embedded-property atomicity — `TODO`

**Outcome.** Close the cross-cutting gap recorded by Q01: a custom Vertica
table `Property` embedded in a real `exp.Properties` list must fail in
foreign dialects with an intended, tested contract instead of raw
`KeyError`, before the milestone gate certifies the temporary-table surface
that exposes it.

**Required work.** Audit every `exp.Property` subclass in
`src/sqlglot_vertica/expressions.py` (15 as of 2026-08-16) against the four
release-gate foreign dialects (PostgreSQL, DuckDB, MySQL, SQLite). Foreign
generators copy `PROPERTIES_LOCATION` per class at class-creation time and
SQLGlot lazy-loads dialect modules, so prove the chosen registration
mechanism reaches every foreign generator under both import orders
(Vertica-first and foreign-first). Deliver exactly one of two contracts and
record the choice:

- **All-level parity (preferred).** The established custom-node contract —
  raised failure at `RAISE`, `WARN`, and `IGNORE`, nothing dropped, exactly
  as `vexp.DropViews` already fails against foreign dialects — if
  achievable without changing shared upstream machinery's behavior for
  non-Vertica trees.
- **Upstream property semantics (fallback).** Register
  `exp.Properties.Location.UNSUPPORTED` in every foreign generator:
  `UnsupportedError` at `RAISE`, warn-and-drop at `WARN`, silent drop at
  `IGNORE`. If chosen, amend the custom-node policy bullet above to scope
  its never-drop sentence and record the deviation as a deliberate
  boundary.

Registering a real location such as `POST_SCHEMA` is prohibited: the
foreign generic property renderer then emits corrupt `None=` SQL at
`WARN`/`IGNORE`. Update the pinned `KeyError` regressions (the
`locate_properties` block in `tests/test_create_table.py` and any sibling
pins) to the new contract. Add an introspective sweep that enumerates the
`vexp` `Property` subclasses — so a future property cannot silently
reintroduce the gap — plus embedded-context tests (definition form, CTAS,
temporary tables) across all four dialects at every `unsupported_level`.
Vertica-dialect generation must be byte-identical before and after. Update
the AST-policy bullet in this file, `ARCHITECTURE.md`'s AST-policy section,
and any coverage note that documents the `KeyError` behavior.

**Stop condition.** If neither contract is deliverable plugin-side without
patching upstream behavior for non-Vertica trees, mark this task `BLOCKED`
with the audit evidence and keep the pinned `KeyError` tests; do not ship
the corrupt-output registration or a partial dialect subset.

**Explicit exclusions.** Canonical properties (for example
`GlobalProperty`) keep their existing foreign behavior; no foreign
rendering or safe lowering of Vertica properties; no SQLGlot dependency or
vendoring changes; custom non-property nodes already satisfy the contract
and must not change.

**Primary sources.** The installed SQLGlot 30.13 sources —
`sqlglot.generator.Generator.locate_properties` and the per-dialect
`PROPERTIES_LOCATION` copies — read per this plan's source-reading section,
plus `ARCHITECTURE.md`'s AST-policy section. No OpenText page governs this
task.

**Implementation pointers (non-normative, verified 2026-08-16).**
Reproduction: generating `CREATE TABLE t INCLUDE PRIVILEGES AS SELECT 1 AS
id` (parsed as Vertica) against `postgres` raises `KeyError` at every
`unsupported_level`. The parity target: `DROP VIEW a, b`, whose
`vexp.DropViews` root raises `ValueError("Unsupported expression type
DropViews")` against foreign dialects at every level. The plugin's own
registration precedent is the
`PROPERTIES_LOCATION: t.ClassVar = {**PostgresGenerator.PROPERTIES_LOCATION,
…}` spread near the top of `generator.py`.

**Completion record.** Pending.

### Q06 — Milestone 1 acceptance gate — `TODO`

**Outcome.** Prove the analysis surface end to end on realistic
multi-statement workloads, update the contract documents, and certify
Milestone 1.

**Required work.** Add a workload-corpus test module of multi-statement
analysis scripts combining CTEs (plain, recursive, hinted), scoped and
unscoped temporary CTAS, definition-form temporary tables, `INSERT … SELECT`
and `INSERT … WITH`, `SELECT … INTO` temporary targets, and `DROP TABLE`
cleanup. Assert `sqlglot.parse` multi-statement boundaries, compact and
pretty round-trips, `dump()`/`Expression.load()` stability, and optimizer
traversal — qualification plus a column-level lineage smoke across
CTE/temporary-table chains, because downstream analysis depends on it.
Update `docs/COVERAGE.md` for every row Q01–Q05 changed (the SELECT/CTE
row's corpus evidence, the INTO TABLE contract, DROP TABLE, the
scoped-temporary-CTAS boundary note, and Q05's foreign-generation
contract), record the milestone in
`docs/ROADMAP.md`, and mark Milestone 1 complete in this plan's Current
state section.

**Explicit exclusions.** No new grammar in this task; named residuals stay
named; Milestone 2 families remain untouched.

**Primary sources.** Re-open the Q01–Q04 pages as needed.

**Implementation pointers (non-normative).** `sqlglot.parse` (not
`parse_one`) preserves multi-statement boundaries. For the optimizer and
lineage smoke, `sqlglot.optimizer.qualify.qualify` plus
`sqlglot.lineage.lineage` over a small explicit schema is sufficient; keep
corpus statements deterministic so compact and pretty round-trips stay
exact.

**Completion record.** Pending.

## Detailed tasks — Milestone 2: administration and remaining DDL (deferred)

Every Milestone 2 task is deferred until Q06 is `DONE`. The detailed P16–P35
specifications — outcome, required work, exclusions, primary sources, and
completion records — are maintained verbatim in
[AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md); they are
not part of the mandatory read while Milestone 1 is active. When a P task is
selected, read its full specification there before implementing and append
its completion record there; status transitions stay in this file's
dashboard. Specifications, dependencies, and numbering are intentionally
unchanged from the prior plan revision; completion records and coverage
notes reference these IDs.
