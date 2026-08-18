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
- Completed **Q03 — DROP TABLE grammar completion**. Q04 is the
  lowest-numbered remaining task.
- On 2026-08-16 the embedded foreign-property `KeyError` gap recorded by
  Q01 was scheduled as new task Q05, and the acceptance gate was renumbered
  Q05 → Q06 before any gate work began; no completion record references the
  old gate number.
- Completed **Q04 — official query-corpus hardening**. Q05 is the
  lowest-numbered remaining task.
- On 2026-08-17 the SELECT `[ AT epoch ]` historical-query-prefix gap
  recorded by Q04 was scheduled as new task Q06, and the acceptance gate was
  renumbered Q06 → Q07 before any gate work began; no completion record
  references the old gate number.
- Completed **Q05 — foreign embedded-property atomicity**. Q06 is the
  lowest-numbered remaining task.
- Completed **Q06 — SELECT `AT epoch` historical-query prefix**. Q07 is the
  lowest-numbered remaining task.
- On 2026-08-17, while confirming Q06 must not touch the structurally
  unrelated CTAS-only `AtEpochProperty` value-parsing helper, testing that
  helper's existing malformed-`AT` path directly (not merely reasoning about
  it) showed it crashes with raw `UnboundLocalError` instead of `ParseError`
  at `WARN`/`IGNORE`, because it uses plain `self.raise_error(...)` rather
  than a guaranteed-raise wrapper. This gap was scheduled as new task Q07,
  and the acceptance gate was renumbered Q07 → Q08 before any gate work
  began; no completion record references the old gate number.
- Completed **Q07 — CTAS historical-snapshot guaranteed-raise conformance**.
  Q08 is the lowest-numbered remaining task, and is the Milestone 1
  acceptance gate.
- Completed **Q08 — Milestone 1 acceptance gate** on 2026-08-17. **Milestone 1
  (the analysis parsing surface) is certified.** All Q01–Q08 tasks are `DONE`;
  Milestone 2 (administration and remaining DDL, tasks P16–P35, specified in
  [AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md)) is now
  eligible. P16 is the lowest-numbered remaining task overall.
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
| Q03 | DONE   | DROP TABLE grammar completion                 | —                   | `feat: complete drop table grammar`                     |
| Q04 | DONE   | Official query-corpus hardening               | —                   | `test: add official query corpus`                       |
| Q05 | DONE   | Foreign embedded-property atomicity           | —                   | `fix: close embedded property foreign atomicity gap`    |
| Q06 | DONE   | SELECT `AT epoch` historical-query prefix     | —                   | `feat: model select at epoch historical query prefix`   |
| Q07 | DONE   | CTAS historical-snapshot guaranteed-raise conformance | —            | `fix: harden ctas at epoch guaranteed raise`            |
| Q08 | DONE   | Milestone 1 acceptance gate                   | Q01–Q07             | `test: certify milestone one analysis surface`          |

### Milestone 2 — administration and remaining DDL (deferred)

Deferred until Q08 is `DONE`. Task numbering, dependencies, and
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
   become eligible only after Q08 is `DONE`. Within the active milestone,
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
  used to raise raw `KeyError`, not an intended atomic failure. Task Q05
  closed this: `src/sqlglot_vertica/foreign_properties.py` registers every
  `exp.Property` subclass introspected from `sqlglot_vertica.expressions`
  with PostgreSQL's, DuckDB's, MySQL's, and SQLite's generators, so a missing
  key for one of those classes now raises the same
  `ValueError("Unsupported expression type <Name>")` an unregistered custom
  root such as `vexp.DropViews` already raises, at every `unsupported_level`
  including `WARN`/`IGNORE` (see `ARCHITECTURE.md`'s AST-policy section for
  the mechanism). Because the registered set is introspected rather than
  hand-maintained, a new `Property` subclass is covered automatically the
  moment it is embedded and generated abroad, and
  `tests/test_foreign_property_atomicity.py` pins this with an exhaustive
  sweep plus a frozen-set enumeration assertion — a new task adding a
  `Property` subclass does not need to re-derive this coverage, only extend
  that frozen set (or document a `ResourcePoolParameter`-style exclusion if
  the class is never reachable through `locate_properties` at all). The
  registration is still scoped to the four release-gate foreign dialects: a
  Vertica-only property embedded and generated against some other foreign
  dialect not in that set still raises the original plain `KeyError`, and the
  generic bare-instantiation sweep still does not by itself prove embedded
  atomicity for a class outside that set.
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

### Q03 — DROP TABLE grammar completion — `DONE`

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

**Completion record.** Implemented with the DROP ROLE split representation
rather than the all-custom DROP VIEW/SCHEMA one, per this task's "canonical
where lossless, atomic root only for demonstrated loss" instruction: a
single-target statement still builds canonical `exp.Drop` (lossless for
`IF EXISTS`, up-to-three-part qualification, and `CASCADE`), while a
comma-separated list builds the new `vexp.DropTables` root, because the
canonical `Drop.expressions` generator demonstrably renders secondary
targets as malformed parentheses (`DROP TABLE a (b)`, verified against
installed 30.13). A new `TokenType.TABLE` branch in `_parse_drop` dispatches
to `_parse_drop_table`, with `_parse_drop_table_name` mirroring
`_parse_view_name` (`_parse_table_parts(schema=True)` plus the shared
per-component validator, so the sibling DROP families' 128-byte UTF-8 and
unquoted-identifier contracts now apply to table targets),
`_match_drop_table_keyword` enforcing unquoted-ASCII provenance for
`CASCADE`/`RESTRICT`, and a new guaranteed-raise `_raise_drop_table_error`
wrapper. Re-opening the primary source found no material contradiction: the
formal syntax is exactly `DROP TABLE [IF EXISTS]
[[{namespace.|database.}]schema.]table[,…] [CASCADE]`, its only modifiers
are prefix `IF EXISTS` (list-scoped per the parameter text, "if one or more
of the tables to drop does not exist") and one trailing `CASCADE`, and the
statement page carries no worked examples of its own (they live on the
admin "Dropping tables" page and are all single-target); the
namespace/database qualifier repeats Q02's observation — syntactically
indistinguishable three-part names resolved server-side. Making the family
deliberate closed several inherited-grammar leaks as intentional boundary
changes: `DROP TABLE t RESTRICT`, `… PURGE`, `DROP TEMP[ORARY] TABLE`,
`DROP MATERIALIZED TABLE`, `DROP ICEBERG TABLE`, four-part names
(`a.b.c.d`), ON-cluster/parenthesized tails, and over-128-byte target
components all previously parsed via the base parser and now raise
`ParseError` at every error level, and `DROP IF EXISTS TABLE t` previously
degraded to `exp.Command` (a standing policy violation) and now fails
closed through the same lookahead-guard pattern the view/schema families
use. Contextual words stay contextual: `cascade`, `local`, `restrict`, and
similar still parse as table names, and quoted `"CASCADE"`/`"RESTRICT"`
payloads never act as keywords. On the generator side, `drop_sql` now
intercepts kind `TABLE` (DROP ROLE pattern): shared validation requires at
least two targets for `DropTables`, rejects canonical `exp.Drop` carrying
`expressions` (eliminating the malformed parenthesized rendering), and
rejects `restrict`/`purge`/`temporary`/`materialized`/`iceberg`/`cluster`/
`concurrently`/`sync`/`constraints` on foreign-parsed or programmatic
canonical trees with `UnsupportedError` instead of emitting undocumented
Vertica, while valid unscoped canonical trees from foreign dialects still
render (`postgres`-parsed `DROP TABLE IF EXISTS a CASCADE` round-trips).
`DropTables` fails atomically abroad exactly like `DropViews`
(`ValueError`, PostgreSQL/DuckDB/MySQL/SQLite, at `RAISE`/`WARN`/`IGNORE`),
and the `test_ast_safety.py` bare-instantiation sweep picked the class up
automatically. One neighboring observation recorded, not fixed (out of
scope): `DROP TEMPORARY VIEW v` still reaches the base parser as canonical
`exp.Drop(kind="VIEW", temporary=True)`, bypassing the view family's
`DropViews` contract — a pre-existing view-family gap analogous to the
TEMPORARY leak this task closed for tables. The focused
`test_drop_table.py` module passed 138 tests; neighboring dispatch families
(schema/view, CREATE TABLE, AST safety, access policy, load-balance
groups, network addresses, PROFILE statement, user lifecycle, workload
routing, sequences, projection, core statements, DML, SELECT INTO,
keywords) passed 3,000. The default CPython 3.12.6 gate passed 5209 tests
at 93.34% branch coverage with Ruff, formatting, and strict mypy clean;
isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and
3.15.0rc1 suites each passed 5209 tests, with 3.15 treating deprecations
as errors. sdist/wheel build, clean force-install, `pip check`, and the
installed-wheel `python -I` entry-point smoke (multi-target
`DROP TABLE IF EXISTS t1, s.t2 CASCADE` round-trip returning `DropTables`)
passed.

### Q04 — official query-corpus hardening — `DONE`

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

**Completion record.** Re-opened the SELECT page and its FROM, joined-table,
WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, OFFSET, UNION, INTERSECT, EXCEPT,
MINUS, WITH clause, and WITH-clause-recursion subpages, plus the
data-analysis subqueries overview and subquery-examples guide (all added to
`docs/SOURCES.md`). Added `tests/test_select_query_corpus.py`, one test per
documented example family — SELECT `ALL`/`DISTINCT`/`MATCH_COLUMNS`/
`FOR UPDATE [OF …]`, `FROM`/`TABLESAMPLE`/multicolumn named subqueries,
`WHERE` boolean expressions, every joined-table form (default `INNER`,
`LEFT`/`RIGHT`/`FULL [OUTER]`, `NATURAL`, `CROSS`, dual-side `TABLESAMPLE`),
`GROUP BY` (plain aggregates, mixed expressions plus `ROLLUP`, and an
AST-shape assertion for `ROLLUP`/`CUBE`/`GROUPING SETS` combined), `HAVING`
(plain and subquery-bearing), `ORDER BY` (direction and ordinal position),
`LIMIT`/`OFFSET` (including `LIMIT ALL` and combined `LIMIT … OFFSET …`),
`UNION`/`UNION ALL`/per-branch `ORDER BY`/`LIMIT`, chained `INTERSECT` and
`EXCEPT`, `MINUS`-as-`EXCEPT`, single/multiple `WITH` CTEs (including the
`ROLLUP`+`GROUPING_ID()` example), a plain `WITH RECURSIVE` case (the
materialization-hinted form was already pinned in `test_hints.py`), and
WHERE/FROM/HAVING scalar, IN-list, derived-table, and UNION-bearing
subqueries — 44 tests, each asserting parse → AST-shape → compact/pretty
round-trip via `tests/helpers.py::assert_roundtrip`. Expanded the
reserved-word collision corpus in `tests/test_keywords.py` with a second
parametrized case (18 tests) covering `AT`, `EPOCH`, `TIME`, `LATEST`,
`ROLLUP`, `CUBE`, `SETS`, `GROUPING`, and `OFFSET` as column, table, and CTE
identifiers; probing confirmed these are fully contextual everywhere,
while `FETCH`, `MINUS`, and `RECURSIVE` were probed and found only
partially contextual (legal as a column but not as a table/CTE name, or not
as a CTE name for `RECURSIVE`) — pre-existing, generic (reproduced under
plain `postgres`) tokenizer/grammar behavior unrelated to this task's scope,
so they were deliberately left out of the "must work everywhere" corpus
rather than forced to pass or silently fixed. Reusable discovery for future
tasks: the installed SQLGlot 30.13 renames the two `Select`/query-node arg
keys that collide with Python keywords — `Select.args["from"]` is now
`"from_"` and `Select.args["with"]` is now `"with_"` (confirmed via direct
`.args.keys()` introspection; every other arg name checked in this task —
`group`, `where`, `joins`, `locks`, `limit`, `expressions`, `rollup`,
`cube`, `grouping_sets` — is unchanged); the existing `src/` code already
used the renamed keys correctly, but this is easy to get wrong when writing
new AST assertions by memory of older SQLGlot versions. Testing surfaced two
named residuals, recorded in `docs/COVERAGE.md` with concrete evidence
rather than fixed, per this task's "record named residuals rather than
guessing" instruction: (1) `LIMIT ALL` is discarded during parsing itself
(`expression.args.get("limit")` is `None` immediately after the first
parse, not just omitted on generation), reproduced identically parsing
plain `LIMIT ALL` under bare `postgres`, confirming this is a pre-existing
base-SQLGlot limitation predating this task and not specific to Vertica;
and (2) a `GROUP BY` built only from `ROLLUP`/`CUBE`/`GROUPING SETS` (no
plain expressions) regenerates in a fixed `grouping_sets, cube, rollup`
order rather than source order, because canonical `exp.Group` stores them
in three separate typed list args rather than one ordered mixed list —
also reproduced identically under plain `postgres`. Neither is fixed here:
both are generic, non-Vertica-specific representational limits of the
canonical AST this task's own scope (adding documented-example regressions,
not new grammar) does not license changing, and the second is directly
covered instead by an AST-shape assertion on `group.args["rollup"]`/
`"cube"`/`"grouping_sets"` rather than an exact-text round-trip. `MINUS` was
confirmed to already canonicalize losslessly to `EXCEPT` (`Except` root,
matching the source's "MINUS is an alias for EXCEPT" statement) with no gap.
Testing also confirmed the SELECT page's own formal-syntax `[ AT epoch ]
[ WITH-clause ] SELECT …` historical-query prefix does not parse at all
(`ParseError` at the token immediately following `AT`, for all three
documented forms: `EPOCH LATEST`, `EPOCH <integer>`, and `TIME '<timestamp>'`)
and has no worked SQL example on the SELECT page, any of its linked
clause subpages, or the WITH-clause-recursion page consulted for the
`RECURSIVE` corpus — so it entered no example-driven regression under this
task's "add each documented example" scope. Because it is formal-syntax
grammar with zero worked-example evidence to pin an exact contract against
(protocol rule 4), and because implementing it correctly requires new
custom-node design work (it must scope the entire top-level query — `WITH`
plus a possible `UNION`/`INTERSECT`/`EXCEPT` chain, not one `exp.Select` —
a materially different shape from the pre-existing, structurally unrelated
CTAS-only `AT EPOCH`/`AT TIME` snapshot property already implemented as
`vexp.AtEpochProperty`/`_parse_at_epoch_property`
(`src/sqlglot_vertica/parser.py:7054`), wired only into the CTAS
`AS [hint] [AT EPOCH|AT TIME] query` position and rendered as a
`POST_ALIAS`-located `exp.Properties` member — this is out of this test-only
task's bounded scope. Per protocol step 6, it is recorded here, in
`docs/COVERAGE.md`'s SELECT/CTE row, and in `docs/ROADMAP.md`, and scheduled
as new task Q06 with a pinned `ParseError` regression
(`test_at_epoch_query_prefix_is_a_documented_residual`) documenting the gap;
the acceptance gate is renumbered Q06 → Q07 so it keeps the highest number,
mirroring the precedent set when Q05 was carved out of Q01. The focused
`test_select_query_corpus.py` module passed 44 tests and the expanded
`test_keywords.py` passed 18; combined with neighboring dispatch families
(query extensions, core statements, hints, SELECT INTO, CREATE TABLE, DROP
TABLE, AST safety) the combined focused run passed 700 tests. The default
CPython 3.12.6 gate passed 5262 tests at 93.34% branch coverage with Ruff,
formatting, and strict mypy clean; isolated CPython 3.9.25, 3.10.20,
3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 5262
tests, with 3.15 treating deprecations as errors. sdist/wheel build, clean
force-install, `pip check`, and the installed-wheel `python -I` entry-point
smoke (`MINUS` round-trip returning `Except`) passed.

### Q05 — foreign embedded-property atomicity — `DONE`

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

**Completion record.** Delivered the preferred all-level-parity contract, not
the upstream `Properties.Location.UNSUPPORTED` fallback: the fallback was
rejected because it is gated by `self.unsupported(...)`, which silently drops
the clause at `WARN` (with only a log line) and at `IGNORE` (with no signal
at all) — exactly the "never allow foreign generation to silently drop a
clause" failure this file's AST-policy bullets prohibit. The delivered
contract needed no upstream-machinery change for non-Vertica trees: added
`src/sqlglot_vertica/foreign_properties.py`, whose `_FailAtomicPropertiesLocation`
dict subclass wraps each target generator's existing `PROPERTIES_LOCATION`
dict unchanged and only overrides `__missing__` — every already-registered
key (canonical or foreign-specific) resolves exactly as before, and any
missing key that is not one of the 15 classes introspected from
`sqlglot_vertica.expressions` still raises the original plain `KeyError`,
proven by a dedicated test with a `Property` subclass defined outside `vexp`.
For the 15 introspected classes, `__missing__` raises
`ValueError(f"Unsupported expression type {key.__name__}")` — reproducing
`vexp.DropViews`'s exact exception type and message for an unregistered
custom root — unconditionally, before `Generator.generate()`'s
`unsupported_level` gating ever runs, so it fires identically at `IMMEDIATE`,
`RAISE`, `WARN`, and `IGNORE`; this was verified directly for all 4 dialects
× 4 levels, not inferred. `patch_foreign_properties_location()` imports
`sqlglot.generators.{postgres,duckdb,mysql,sqlite}` directly and is called
once from `dialect.py` at Vertica-dialect import time; because Python caches
each module on first import regardless of who imports it, this reaches the
same single canonical generator class either way, so there is no
"Vertica-first" vs. "foreign-first" case where the patch is missed — proven
with two fresh-interpreter subprocess tests, one importing `sqlglot_vertica`
before anything touches `sqlglot.generators.duckdb` and one importing
`sqlglot.generators.duckdb` first. The trade-off recorded as part of that
proof: because the patch function itself imports all four target generator
modules, `import sqlglot_vertica` now unconditionally loads DuckDB's,
MySQL's, and SQLite's (lightweight, generator-only) submodules even for a
caller who only ever generates Vertica or PostgreSQL SQL; this was judged
acceptable rather than pursuing a lazier hook into SQLGlot's
`sqlglot/dialects/__init__.py` module `__getattr__`, which would have meant
patching shared upstream loader machinery instead of an additive per-class
dict. Audited all 15 `exp.Property` subclasses in `expressions.py`
(confirmed via `inspect.getmembers`, matching the plan's "15 as of
2026-08-16"). 14 are embedded through the generic `exp.Properties`/
`Generator.locate_properties` path this task fixes and are covered by an
exhaustive parametrized sweep (14 properties × 4 dialects × 4 levels) that
constructs each as a bare instance inside a synthetic `exp.Create`/
`exp.Properties` tree — the same shape `locate_properties` actually receives
in production, unlike the pre-existing bare-instantiation sweep in
`test_ast_safety.py`, which never wraps a class in a real `Properties`
container and therefore cannot see this class of gap either way. The 15th,
`vexp.ResourcePoolParameter`, was confirmed to never reach
`locate_properties` at all: it is only ever embedded inside
`vexp.CreateResourcePool`/`AlterResourcePool`, and those are themselves
canonical `exp.Create`/`exp.Alter` subclasses with no per-node dispatch entry
in any foreign generator, so `Generator.sql()`'s own "no dispatch, not a
`Func`/`Property`" fallback raises `ValueError("Unsupported expression type
CreateResourcePool")` first, atomically, before the tree is ever asked for
its properties — confirmed at all 4 dialects × 4 levels; it deliberately
carries no `PROPERTIES_LOCATION` entry, native or foreign, and giving it one
was rejected as unnecessary and untested-by-construction. Because the
registered set is introspected from `vexp` rather than hand-maintained, a
future `Property` subclass is covered automatically the moment it is
embedded and generated abroad; `tests/test_foreign_property_atomicity.py`
freezes the current 15-name enumeration in an assertion so a class silently
falling outside both the generic sweep and the `ResourcePoolParameter`-style
exclusion is caught immediately rather than discovered later. Also added
five embedded-context regressions reusing real parsed SQL already exercising
several properties together (definition-form full physical design, CTAS full
physical design, a GLOBAL temporary table, `CREATE LOCAL TEMPORARY TABLE …
AS`, and CREATE SCHEMA), each swept across 4 dialects × 4 levels; these
accept either `ValueError` or `UnsupportedError` rather than pinning one
exact type, because at `IMMEDIATE` specifically, DuckDB and SQLite blanket-map
most *canonical* properties (`exp.Order`, `exp.GlobalProperty`) to
`Properties.Location.UNSUPPORTED` too, and two of the five fixtures place one
of those before the Vertica-only property in list order — confirmed
pre-existing and unrelated to this task (`self.unsupported` only raises
synchronously at `IMMEDIATE`; at every other level the loop continues past a
canonical-UNSUPPORTED hit and still reaches the Vertica-only `ValueError`).
`KeyError` is explicitly excluded from the accepted set in that test, so a
regression reintroducing it would still fail the suite. Also added dedicated
regressions confirming `exp.GlobalProperty`'s existing PostgreSQL/MySQL
render and DuckDB/SQLite `UnsupportedError` are byte-for-byte unaffected (it
was already present, not missing, in all four dicts), confirming
`exp.TransientProperty` keeps its pre-existing warn-and-drop-at-`WARN`/
silent-drop-at-`IGNORE`/raise-at-`RAISE` semantics (the patch only
special-cases *missing* keys, never a registered one), and confirming
Vertica-dialect generation is byte-identical for all five embedded-context
fixtures. Updated the one pinned `KeyError` regression
(`test_create_local_temporary_table_as_foreign_generation_fails_atomically`
in `test_create_table.py`) to assert the new `ValueError` contract instead;
no sibling pins existed elsewhere. Updated the AST-policy bullet in this
file, `ARCHITECTURE.md`'s AST-policy section, the two affected `CREATE TABLE`
coverage rows plus the schema-lifecycle row in `COVERAGE.md`, `ROADMAP.md`,
and `CHANGELOG.md`. The focused `test_foreign_property_atomicity.py` module
passed 329 tests; combined with neighboring dispatch families
(`test_create_table.py`, `test_ast_safety.py`, `test_roles_resource_pools.py`,
`test_schema_view.py`) the combined focused run passed 1,164. The default
CPython 3.12.6 gate passed 5,591 tests at 93.35% branch coverage with Ruff,
formatting, strict mypy, and `git diff --check` clean; isolated CPython
3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each
passed 5,591 tests, with 3.15 treating deprecations as errors. sdist/wheel
build, clean force-install, `pip check`, and the installed-wheel `python -I`
entry-point smoke (`CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS id`
round-trip returning canonical `Create`) passed.

### Q06 — SELECT `AT epoch` historical-query prefix — `DONE`

**Outcome.** Make the SELECT statement's own documented
`[ AT epoch ] [ WITH-clause ] SELECT …` historical-query prefix parse and
regenerate for the whole top-level query, with a typed, tested contract, so
the Generic SELECT/CTE coverage row no longer names it as an unparseable
gap.

**Required work.** Re-open the 26.2 SELECT page and support the `AT epoch`
prefix, where `epoch` is `EPOCH { LATEST | integer }` or `TIME 'timestamp'`
per the page's own parameter description. The prefix precedes the entire
top-level query production — `[ AT epoch ] [ WITH-clause ] SELECT …` is
followed, in the same formal-syntax block, by `union-clause`/
`intersect-clause`/`except-clause` — so it scopes a possible `WITH` clause
and any subsequent `UNION`/`INTERSECT`/`EXCEPT` chain, not one bare
`exp.Select`. Design and document the AST contract accordingly: whatever
node carries the prefix must wrap the complete top-level query (`exp.Select`
or a set-operation root), analogous in spirit to how `SelectInto` and
`TimeseriesSelect` each promote the whole `Select` but generalized to a
`exp.Query`-rooted statement here. Decide, and record the decision, whether
the new node should reuse the existing CTAS-only `_parse_at_epoch_property`/
`vexp.AtEpochProperty` value-parsing logic (same `EPOCH LATEST`/
`EPOCH <integer>`/`TIME '<timestamp>'` grammar) or parse the value
independently — the two occupy structurally different grammar positions
(CTAS's is an `exp.Property` inside `AS [hint] [AT EPOCH|AT TIME] query`,
parsed at `src/sqlglot_vertica/parser.py:6876` and rendered at
`generator.py:4349` as a `POST_ALIAS`-located `exp.Properties` member; this
task's is a bare statement-level prefix with no `Properties` list at all)
and do not assume they must share a node class. Add a guaranteed-raise
`_raise_<family>_error` wrapper for malformed forms (missing `EPOCH`/`TIME`
keyword, non-integer epoch, unquoted `TIME` value) at every error level.
Test `EPOCH LATEST`, `EPOCH <integer>`, and `TIME '<timestamp>'`; the prefix
combined with a `WITH` clause; the prefix combined with `UNION`/`INTERSECT`/
`EXCEPT` (confirming it scopes the whole compound query); malformed forms;
serialization stability; and foreign-generation atomicity per the
established custom-root policy. Remove the pinned `ParseError` regression
this gap left in `tests/test_select_query_corpus.py`
(`test_at_epoch_query_prefix_is_a_documented_residual`) and replace it with
the new positive corpus. Update the SELECT/CTE row in `docs/COVERAGE.md` to
remove the named residual once closed.

**Explicit exclusions.** Epoch/timestamp existence and validity (server/
catalog state); TIMESERIES/MATCH/INTERPOLATE; the `INTO [TABLE]` clause
(Q02's contract); and the pre-existing CTAS-only `AT EPOCH`/`AT TIME`
snapshot property, which already has its own tested contract and must not
change unless this task proves shared code is the correct design.

**Primary sources.** [SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/)
(formal syntax and the `AT epoch` parameter description).

**Implementation pointers (non-normative, verified 2026-08-17).**
`AT EPOCH LATEST SELECT * FROM t`, `AT EPOCH 5 SELECT * FROM t`, and
`AT TIME '2024-01-01 00:00:00' SELECT * FROM t` each raise `ParseError`
("Invalid expression / Unexpected token") at the token immediately
following `AT` today. No worked SQL example for this prefix exists on the
SELECT page, any of its linked clause subpages, or the WITH-clause-recursion
page checked incidentally while building Q04's `WITH RECURSIVE` corpus;
re-confirm this during the primary-source re-open rather than assuming it
still holds. The reusable CTAS infrastructure is
`_parse_at_epoch_property` (`src/sqlglot_vertica/parser.py:7054`) and
`vexp.AtEpochProperty` (`src/sqlglot_vertica/expressions.py:741`).

**Completion record.** Re-opened the 26.2 SELECT page; the formal syntax and
the `epoch` parameter description reproduced exactly as Q04 recorded them
(`[ AT epoch ] [ WITH-clause ] SELECT … [ union-clause ] [ intersect-clause ]
[ except-clause ] …`, with `EPOCH LATEST`/`EPOCH integer`/`TIME 'timestamp'`
each documented and no worked SQL example anywhere on the page), confirming
the gap still held before implementation began.

Delivered a single wrapper node, `vexp.AtEpochQuery(exp.Expression)`
(`arg_types = {"this": True, "kind": True, "value": True}`), rather than the
`SelectInto`/`TimeseriesSelect`-style promotion this task's own text raised
as the analogous precedent. Promotion needs the wrapper to literally *become*
the concrete root it decorates by cloning its args (`vexp.Foo(**this.args,
extra=…)`), which works for those two families because their clause only
ever attaches to a bare `exp.Select`. This prefix scopes the *entire*
top-level query production — a possible `WITH` clause and any following
`UNION`/`INTERSECT`/`EXCEPT` chain — so the concrete root it must wrap can be
`exp.Select` or any `exp.SetOperation`, shapes with materially different
`arg_types`; promotion would have needed four parallel classes
(`AtEpochSelect`/`AtEpochUnion`/`AtEpochIntersect`/`AtEpochExcept`) each with
their own generator dispatch entry. Empirical probes confirmed a single
typed `this` avoids that entirely and loses nothing: parsing
`SELECT 1 UNION SELECT 2` under `vertica` already yields a bare `exp.Union`
root, and parsing `WITH cte AS (SELECT 1) SELECT * FROM cte UNION SELECT *
FROM cte` attaches `with_` to that same outer `Union`, not to the first
branch — so whatever `super()._parse_statement()` returns after the prefix
is consumed is already the exact, correctly-shaped `exp.Query` to store
unmodified. This also sidesteps a hazard the wrapper design doesn't share
with promotion: because `AtEpochQuery` is never itself an `exp.Select`, no
foreign dialect's `isinstance`-gated structural pre-dispatch rewrite (the
exact mechanism `SelectInto` was built to survive) ever runs on it — it fails
first, atomically, through the plain unregistered-custom-root fallback.
Reused the CTAS-only `AtEpochProperty`'s value grammar (`EPOCH LATEST`/
`EPOCH <integer>`/`TIME '<timestamp>'`) but not its parsing method or node
class, per this task's explicit "do not assume they must share a node class"
instruction: the two occupy structurally different grammar positions (a
`POST_ALIAS` `Properties` member inside CTAS's `AS […] query` versus a bare
statement-level prefix with no `Properties` list at all), and — discovered
while auditing the existing helper before deciding — sharing its parsing
method would have also imported a live bug (below) into the new family.

Parsing hooks into the existing `VerticaParser._parse_statement` override
(already a dispatch chain for `PROFILE`/`SAVE QUERY`/`GET DIRECTED QUERY`/
`ACTIVATE`/`DEACTIVATE DIRECTED QUERY`) with one new `elif
self._match_text_seq("AT"): expression =
self._parse_at_epoch_query(comments=profile_comments)` branch; `AT` cannot
collide with any of those or with `STATEMENT_PARSERS`, so branch order is
immaterial. `_parse_at_epoch_query` parses the value grammar, then delegates
the remainder to `super()._parse_statement()` (the base-class implementation,
not the family dispatch chain, matching how `_parse_profile_statement`
already delegates its own body) so the trailing `WITH`/`SELECT`/set-operation
chain parses exactly as an ordinary top-level query would, and wraps
whatever `exp.Query` instance results. A new guaranteed-raise wrapper,
`_raise_at_epoch_query_error`, rejects a missing/invalid `EPOCH`/`TIME` value
and a missing or non-`exp.Query` trailing statement at every error level.
Generation (`atepochquery_sql`) validates `kind`/`value`/`this` shape before
rendering and calls `self.unsupported(...)` on any mismatch, matching this
file's "validate programmatic ASTs before rendering" policy; foreign
generation reaches the plain "no dispatch, not a `Func`/`Property`" fallback
in `Generator.sql()` and raises `ValueError("Unsupported expression type
AtEpochQuery")` — the exact `DropViews`/`DropTables` contract — confirmed for
all 4 release-gate dialects × 3 `unsupported_level`s, both for a bare
detached instance and for the node embedded as a CTE body (below).

Testing surfaced four points worth recording precisely rather than assuming:

1. **Leading comments need explicit threading.** `self.expression(instance,
   comments=…)` alone does not preserve a comment attached before a keyword
   this method's own `elif` branch already consumed via `_match_text_seq`;
   `_parse_at_epoch_query` therefore accepts and forwards the same
   `profile_comments` snapshot the outer method already captures before
   dispatch, mirroring `_parse_profile_statement`'s identical `comments`
   parameter exactly. (Also matching that precedent: the comment lands after
   the generated SQL, not before it — `test_leading_comment_is_retained`
   asserts containment, not position, matching `test_select_into.py`'s own
   convention for the same reason.)
2. **`_parse_statement`'s custom dispatch is reentered by CTE bodies**, not
   only genuine per-script top-level statements: base
   `Parser._parse_select_query` calls `self._parse_statement()` right after
   parsing a CTE list's parenthesized body, and `self` always resolves to the
   concrete `VerticaParser`, so `WITH cte AS (AT EPOCH LATEST SELECT 1)
   SELECT * FROM cte` parses. Confirmed pre-existing and not specific to this
   family or task: `WITH cte AS (PROFILE SELECT 1) SELECT * FROM cte` parses
   identically on the unmodified, pre-Q06 codebase. Documented in
   `ARCHITECTURE.md` rather than fixed — closing it is a cross-cutting change
   spanning every family in that dispatch chain, not a Q06-scoped one — and
   pinned as observed (not endorsed) behavior in
   `test_cte_body_may_carry_its_own_prefix`. The complementary malformed
   case — a CTE list arriving *after* one of these roots
   (`WITH cte AS (...) AT EPOCH LATEST SELECT ...`) — already fails closed
   with a clean `ParseError` ("`atepochquery` does not support CTE"),
   identical to `PROFILE`'s own failure message shape, because neither root
   declares a `with_` arg for the generic CTE-attaching code to find.
3. **`qualify`/`optimize` run but do not fully qualify through the
   wrapper.** Both accept `AtEpochQuery` without error and preserve it as the
   root (satisfying the common release gate's "optimizer stability"
   requirement), but neither requires its input to already be an
   `exp.Query`, and their scope-building does not treat the wrapped `this` as
   a normal top-level scope: previously unqualified SELECT-list columns come
   back identifier-quoted only (`column.table == ""`), not resolved to their
   source table, unlike the identical query without the prefix. This is a
   documented residual, not corruption — a control case confirmed
   already-qualified references (a JOIN condition written `t1.a = t2.b`)
   pass through unaffected, and no column is ever resolved to the *wrong*
   table. `sqlglot.lineage.lineage` is stricter and simply raises
   ("Cannot build lineage, sql must be SELECT") against the wrapper
   directly; callers must pass `expression.this`. None of this closes fully
   — Q07 (the acceptance gate)'s own multi-statement corpus does not include
   the `AT epoch` prefix, so full lineage/qualify parity was never a
   requirement this task carried.
4. **The reused CTAS value grammar's existing malformed-`AT` handling has a
   live bug**, found while confirming it must stay untouched: `AT FOO SELECT
   1` inside `CREATE TABLE t AS …` — an inherited-property call still built on
   plain `self.raise_error(...)`, not a guaranteed-raise wrapper — crashes
   with raw `UnboundLocalError` instead of `ParseError` at `WARN`/`IGNORE`,
   confirmed directly against the installed package rather than inferred.
   Out of scope here (this task's own exclusions bar changing
   `AtEpochProperty`), so scheduled as new task Q07 per protocol step 6, and
   the acceptance gate renumbered Q07 → Q08 before any gate work began; no
   completion record references the old gate number.

The focused `test_at_epoch_query.py` module passed 176 tests and the edited
`test_select_query_corpus.py` (one pinned `ParseError` residual replaced by
five documented-grammar positive cases) passed 48; combined with neighboring
dispatch families (`test_keywords.py`'s reserved-word corpus, CREATE TABLE,
SELECT INTO, DROP TABLE, schema/view, AST safety, foreign property
atomicity, core statements, hints, query extensions, DML) the combined
focused run passed 1,763. The default CPython 3.12.6 gate passed 5,772 tests
at 93.38% branch coverage with Ruff, formatting, strict mypy, and
`git diff --check` clean; isolated CPython 3.9.25, 3.10.20, 3.11.15,
3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 5,772 tests, with
3.15 treating deprecations as errors. sdist/wheel build, clean force-install,
`pip check`, and the installed-wheel `python -I` entry-point smoke
(`AT EPOCH LATEST SELECT 1` round-trip returning `AtEpochQuery`) passed.

### Q07 — CTAS historical-snapshot guaranteed-raise conformance — `DONE`

**Outcome.** Make the CTAS-only `AT EPOCH`/`AT TIME` historical-snapshot
property (`_parse_at_epoch_property`/`vexp.AtEpochProperty`) fail with
`ParseError` at every error level when its value grammar is malformed,
matching this file's guaranteed-raise policy, instead of crashing with raw
`UnboundLocalError` at `WARN`/`IGNORE`.

**Required work.** Route `_parse_at_epoch_property`'s three
`self.raise_error(...)` call sites (missing `EPOCH`/`TIME` keyword, a
non-`LATEST`/non-integer epoch value, and a missing quoted `TIME` value)
through the CTAS family's existing `_raise_create_table_error`
guaranteed-raise wrapper instead. The method's `else` branch currently
leaves `kind`/`value` unassigned before an unconditional
`assert value is not None`; because plain `raise_error` only raises
immediately at `IMMEDIATE` and only aggregates for a later `check_errors()`
call at `RAISE`, that `assert` is reached with `value` never bound at
`WARN`/`IGNORE`, producing `UnboundLocalError` instead of `ParseError`. Test
all three malformed forms at `IMMEDIATE`, `RAISE`, `WARN`, and `IGNORE`, for
both the temporary (scoped and unscoped) and permanent CTAS positions,
confirming `ParseError` — never `UnboundLocalError` or any other raw Python
exception — at every level. Confirm byte-identical Vertica generation and the
existing positive `AtEpochProperty` regressions (`EPOCH LATEST`,
`EPOCH <integer>`, `TIME '<timestamp>'`) are unaffected.

**Explicit exclusions.** The independent, structurally unrelated Q06
`AtEpochQuery` statement-level prefix, which already has its own
guaranteed-raise wrapper and must not change; `vexp.AtEpochProperty`'s
`arg_types` or rendering; any other pre-existing bare `self.raise_error(...)`
call site outside this one method (`ARCHITECTURE.md`'s AST-policy section
already records that the guaranteed-raise pattern "has not been retrofitted
onto every pre-existing call site," and this task does not change that).

**Primary sources.** None beyond this repository: `ARCHITECTURE.md`'s
AST-policy section and this file's own guaranteed-raise policy bullet already
specify the required contract; no OpenText page governs internal
error-handling mechanics.

**Implementation pointers (non-normative, verified 2026-08-17).**
`_parse_at_epoch_property` reproduces
`UnboundLocalError: cannot access local variable 'value' where it is not
associated with a value` for `CREATE TABLE t AS AT FOO SELECT 1` at
`error_level={WARN,IGNORE}`, confirmed directly against the installed
package (grep `def _parse_at_epoch_property` for its current line — Q06
added an unrelated method earlier in `parser.py`, shifting it).
`_raise_create_table_error` (grep `def _raise_create_table_error`) is the
established guaranteed-raise wrapper already used throughout the surrounding
CTAS clause list for sibling malformed-clause cases.

**Completion record.** Confirmed the reported gap still held before touching
code, and went further: probing all three malformed forms at all four error
levels directly against the installed, unmodified package (rather than
reasoning about it) showed the pre-fix defect was not one uniform failure but
three different raw-Python outcomes, all wrong but each wrong differently,
because `value` and `kind` end up in different binding states depending on
which of the three `if`/`elif`/`else` branches runs and how far its own
value-parser got before the bare `self.raise_error(...)` call: (1)
`AT EPOCH 1.5` (`_parse_number()` still returns a bound, non-`None`
non-integer `Literal`) raised `ParseError` correctly at `IMMEDIATE`/`RAISE`
(the `RAISE` case only because a later top-level `check_errors()` call
happens to catch the aggregated error before anything reads the stale
`value`), but at `WARN`/`IGNORE` fell all the way through to a `return`,
silently building an `AtEpochProperty` from the invalid `1.5` literal with no
exception at all; (2) `AT TIME now` (`_parse_string()` returns bound `None`
because `now` is not a string token) raised `ParseError` at `IMMEDIATE` but
`AssertionError` at `RAISE`, `WARN`, and `IGNORE` alike, since
`assert value is not None` fails synchronously the instant it runs,
regardless of error level; (3) `AT SNAPSHOT 1` (the `else` branch assigns
neither `value` nor `kind` at all) raised `ParseError` at `IMMEDIATE` but raw
`UnboundLocalError` at `RAISE`/`WARN`/`IGNORE`, matching the plan's own
implementation-pointers example exactly. Routed all three call sites through
`_raise_create_table_error` (unconditional `self.raise_error(message)` then
`check_errors()` at `RAISE` then an explicit `raise ParseError(message)` at
`IGNORE`/`WARN`) exactly as the required work specified; no other change to
the method. Because the wrapper never returns control to its caller at any
error level (`IMMEDIATE` raises inside `raise_error` itself; `RAISE` raises
from `check_errors()`; `IGNORE`/`WARN` raise from the wrapper's own trailing
statement), none of the three post-call fall-through paths — the silent
`return`, the `AssertionError`-raising `assert`, or the `UnboundLocalError`-
raising read — can execute any more, independent of which binding state
`value`/`kind` were left in; re-running the identical probe after the change
showed all three malformed forms raising plain `ParseError` at all four
levels, confirmed both standalone and, per the required work's explicit
CTAS-position scope, across permanent, unscoped-temporary, and
scoped-temporary (`LOCAL TEMPORARY`) CTAS (48 combinations: 3 forms × 4
positions-inclusive-of-permanent × 4 levels, counting the standalone probe
plus the position sweep). Added
`test_ctas_at_epoch_malformed_forms_fail_closed_at_every_error_level` to
`test_create_table.py`, a 36-case matrix (3 malformed forms × 3 CTAS
positions [permanent, unscoped temporary, `LOCAL TEMPORARY`] × 4 error
levels) asserting `ParseError` with the expected message at every cell,
mirroring `test_at_epoch_query.py`'s own stacked-`parametrize` pattern for
its sibling family's guaranteed-raise sweep
(`test_recognized_invalid_at_epoch_query_fails_closed`). Confirmed the three
pre-existing positive `AtEpochProperty` regressions (`EPOCH LATEST`,
`EPOCH <integer>`, `TIME '<timestamp>'`, already covered across permanent,
unscoped-temporary, and scoped-temporary CTAS by
`test_create_table_as_historical_epoch_forms`,
`test_create_table_as_full_physical_design`,
`test_create_temporary_table_as`, and
`test_create_scoped_temporary_table_as_full_physical_design`) still pass
unmodified, and separately confirmed byte-identical Vertica generation for
all three valid forms across all three CTAS positions by direct round-trip.
Confirmed Q06's independent `AtEpochQuery` statement-level prefix — a
structurally unrelated node with its own `_raise_at_epoch_query_error`
wrapper — is untouched: its positive round-trip, its `properties`-vs-root
dispatch-neighbor distinction from `AtEpochProperty`
(`test_dispatch_neighbors_unchanged`), and its own malformed-prefix
guaranteed-raise behavior at `WARN` all still hold. Updated the
`CREATE TABLE AS`/temporary-tables and SELECT `[ AT epoch ]` rows in
`docs/COVERAGE.md`, the Milestone 1 paragraph in `docs/ROADMAP.md`, added a
paragraph to `docs/ARCHITECTURE.md` next to the existing `AtEpochQuery`/
`AtEpochProperty` distinction documenting the fix and its precedent (P15's
identical-shaped `AssertionError`-instead-of-`ParseError` fix for the CREATE
TABLE definition/CTAS/LIKE dispatch), and added a `CHANGELOG.md` entry. No
OpenText primary source governs this task (confirmed in the required-work
text); `ARCHITECTURE.md`'s AST-policy section and this file's own
guaranteed-raise policy bullet already specified the target contract and
needed no correction, only conformance. The focused `test_create_table.py`
module passed 122 tests (86 pre-existing plus the 36 new); combined with
neighboring dispatch families (`test_at_epoch_query.py`, `test_ast_safety.py`,
`test_select_query_corpus.py`, `test_foreign_property_atomicity.py`,
`test_select_into.py`, `test_drop_table.py`, `test_schema_view.py`) the
combined focused run passed 1,608. The default CPython 3.12.6 gate passed
5,808 tests at 93.38% branch coverage with Ruff, formatting, strict mypy, and
`git diff --check` clean; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13,
3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 5,808 tests, with 3.15
treating deprecations as errors. sdist/wheel build, clean force-install,
`pip check`, and the installed-wheel `python -I` entry-point smoke
(`CREATE TABLE t AS AT EPOCH LATEST SELECT 1 AS id` round-trip returning
canonical `Create`) passed.

### Q08 — Milestone 1 acceptance gate — `DONE`

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
Update `docs/COVERAGE.md` for every row Q01–Q07 changed (the SELECT/CTE
row's corpus evidence, the INTO TABLE contract, DROP TABLE, the
scoped-temporary-CTAS boundary note, the LIMIT/OFFSET/FETCH and identifier
rows' Q04 evidence, Q05's foreign-generation contract, and Q06's
`AtEpochQuery` row), record the milestone in `docs/ROADMAP.md`, and mark
Milestone 1 complete in this plan's Current state section.

**Explicit exclusions.** No new grammar in this task; named residuals stay
named; Milestone 2 families remain untouched.

**Primary sources.** Re-open the Q01–Q07 pages as needed.

**Implementation pointers (non-normative).** `sqlglot.parse` (not
`parse_one`) preserves multi-statement boundaries. For the optimizer and
lineage smoke, `sqlglot.optimizer.qualify.qualify` plus
`sqlglot.lineage.lineage` over a small explicit schema is sufficient; keep
corpus statements deterministic so compact and pretty round-trips stay
exact.

**Completion record.** Re-read `docs/ARCHITECTURE.md`, `docs/COVERAGE.md`, and
`docs/ROADMAP.md` per protocol step 1; no primary source re-open was required
beyond that, since this task introduces no new grammar and its own primary
sources are "the Q01–Q07 pages as needed." Added `tests/test_workload_corpus.py`
with two realistic multi-statement analysis scripts. The staging pipeline
combines a definition-form `LOCAL TEMPORARY TABLE` populated by
`INSERT ... SELECT`, a scoped (`LOCAL`) temporary CTAS whose own query carries
a plain CTE, a `SELECT ... INTO LOCAL TEMP TABLE` target, and ordered
multi-target `DROP TABLE` cleanup (no `IF EXISTS`). The recursive-archive
pipeline combines an unscoped temporary CTAS built from a plain CTE, a second
unscoped temporary CTAS built from a `WITH RECURSIVE` CTE, an archival
`INSERT ... WITH` carrying an `ENABLE_WITH_CLAUSE_MATERIALIZATION` hint (the
`WithHint` root, confirming the hinted-CTE family composes with `INSERT`'s
target-following `WITH` form), and `DROP TABLE ... IF EXISTS` multi-target
cleanup — together exercising every family the required work lists (plain,
recursive, and hinted CTEs; scoped and unscoped temporary CTAS; definition-form
temporary tables; `INSERT ... SELECT` and `INSERT ... WITH`;
`SELECT ... INTO` temporary targets; and `DROP TABLE` cleanup). Added a shared
`assert_script_roundtrip` helper to `tests/helpers.py`, mirroring the existing
`assert_roundtrip` single-statement contract but for a `sqlglot.parse`-produced
statement list: it asserts the exact expected type sequence (multi-statement
boundaries), then, per statement, non-`Command` status, compact generation and
reparse equality, pretty generation and reparse equality, and
`dump()`/`Expr.load()` stability. Both scripts pass through it, and a
dedicated shape test per script asserts representative AST facts (property
list order and identity on the definition-form table; the `with_` node type
and `filtered`/`cutoff` CTE aliases; `recursive=True` and the inner `Union`
body on the `RECURSIVE` CTE; `IntoTableClause`'s `scope`/`on_commit`; ordered
`DropTables` targets and `exists` state). A third test confirms a leading
comment on the closing `DROP TABLE` statement of a two-statement script
survives the statement boundary (`"pipeline cleanup" in drop_t.sql(...)`),
closing a combination gap no single-family module could exercise on its own.
For optimizer traversal, one test calls `qualify()` on the staging pipeline's
`SelectInto` against `customer_totals`'s own schema and asserts both columns
resolve to `customer_totals` and the `SelectInto`/`IntoTableClause` contract
survives `dump()`/`load()`; a second calls `optimize()` over the same
statement with a two-table schema and asserts root-class and `dump()`/`load()`
stability, mirroring `test_select_into.py`'s own optimizer-stability
regression. The column-level lineage smoke traces `"customer_id"` from the
`SelectInto` target through `customer_totals`'s real CTAS query (passed via
`lineage()`'s `sources` mapping, which internally calls `exp.expand` before
qualifying — `qualify()` itself has no `sources` parameter, confirmed by
inspecting `sqlglot.optimizer.qualify.qualify`'s signature) down to the
`filtered` CTE inside that query, and finally to the definition-form
`staging_orders` table's declared schema entry: the returned node's
`{downstream.name for downstream in node.walk()}` set contains
`"customer_totals.customer_id"`, `"filtered.customer_id"`, and
`"staging_orders.customer_id"`, proving downstream lineage tooling can follow
a chain built entirely from Milestone 1's statement families through both a
temporary-table boundary and a nested CTE. `vexp.AtEpochQuery` (Q06) was
deliberately not included in either script: it is not named in this task's
required-work statement-family list, and `ARCHITECTURE.md` already records
that it degrades `qualify`/`lineage` behavior in ways orthogonal to what this
gate certifies, so including it would have conflated two unrelated residuals
rather than proving the combination the task actually specifies.

Updated `docs/COVERAGE.md`'s SELECT/CTE, `INTO [TABLE]`,
`CREATE TABLE AS`/temporary-tables, and `DROP TABLE` rows with this corpus's
evidence. The LIMIT/OFFSET/FETCH row, the identifier row's Q04 reserved-word
corpus, Q05's foreign-generation contract, and Q06's `AtEpochQuery` row were
re-read and left unchanged: this task's corpus contains no `LIMIT`/`OFFSET`/
`FETCH` clause, introduces no new identifier corpus, exercises no additional
foreign-dialect surface beyond what Q05's own exhaustive sweep already covers
for the property classes this corpus's `CREATE TABLE`/CTAS statements embed,
and deliberately excludes `AtEpochQuery` for the reason above — recording this
explicitly rather than padding those four rows with text that would overstate
what changed. Updated `docs/ROADMAP.md`'s Milestone 1 paragraph to record Q08
complete and Milestone 1 certified on 2026-08-17, updated the "Remaining"
introduction to reflect that Q01–Q08 no longer defer Milestone 2, and updated
`CHANGELOG.md` with a milestone-certification entry. Updated this plan's
Current state section to record Milestone 1 as certified and P16 as the
lowest-numbered remaining task overall. Also corrected a stale cross-reference
found while re-reading the mandatory task-selection documents: `AGENTS.md`'s
milestone-precedence bullet still said Milestone 2 becomes eligible "after Q06
is `DONE`", left over from before the acceptance gate was renumbered Q06 → Q07
→ Q08 across Q04's and Q06's completion records; corrected to "after Q08 is
`DONE`" so a future agent's very first mandatory read does not misstate the
condition this task makes live.

The focused `test_workload_corpus.py` module passed 8 tests; combined with
neighboring dispatch families (`test_select_into.py`, `test_create_table.py`,
`test_drop_table.py`, `test_at_epoch_query.py`, `test_dml.py`, `test_hints.py`,
`test_select_query_corpus.py`, `test_keywords.py`, `test_ast_safety.py`,
`test_query_extensions.py`, `test_foreign_property_atomicity.py`,
`test_schema_view.py`, `test_core_statements.py`) the combined focused run
passed 1,807. The default CPython 3.12.6 gate passed 5,816 tests (5,808 plus
this task's 8) at 93.38% branch coverage with Ruff, formatting, strict mypy,
and `git diff --check` clean; isolated CPython 3.9.25, 3.10.20, 3.11.15,
3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 5,816 tests, with
3.15 treating deprecations as errors. sdist/wheel build, clean force-install,
`pip check`, and the installed-wheel `python -I` entry-point smoke
(`SELECT customer_id, total_amount INTO LOCAL TEMP TABLE top_customers ON
COMMIT PRESERVE ROWS FROM customer_totals WHERE total_amount > 1000`
round-trip returning `SelectInto`) passed. No new grammar was introduced;
every named residual recorded by Q01–Q07 (`LIMIT ALL` discarded at parse
time, the `GROUP BY` grouping-construct ordering limit, `AtEpochQuery`'s
partial `qualify`/`lineage` support, and the CTE-body dispatch-reentry
observation) remains named and unchanged. **Milestone 1 — the analysis
parsing surface — is certified.**

## Detailed tasks — Milestone 2: administration and remaining DDL (deferred)

Every Milestone 2 task is deferred until Q08 is `DONE`. The detailed P16–P35
specifications — outcome, required work, exclusions, primary sources, and
completion records — are maintained verbatim in
[AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md); they are
not part of the mandatory read while Milestone 1 is active. When a P task is
selected, read its full specification there before implementing and append
its completion record there; status transitions stay in this file's
dashboard. Specifications, dependencies, and numbering are intentionally
unchanged from the prior plan revision; completion records and coverage
notes reference these IDs.
