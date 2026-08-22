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
  renumbered Q06 → Q07 before any gate work began. Q06's later completion
  record preserves that intermediate gate number as historical context.
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
  began. Q06's completion record necessarily retains the earlier Q07 gate
  reference because it records the discovery that caused this renumbering.
- Completed **Q07 — CTAS historical-snapshot guaranteed-raise conformance**.
  Q08 is the lowest-numbered remaining task, and is the Milestone 1
  acceptance gate.
- Completed **Q08 — Milestone 1 acceptance gate** on 2026-08-17. Its positive
  workload corpus and release-gate result remain valid historical evidence,
  but the certification conclusion is superseded by the audit below.
- On 2026-08-21, a fresh source-backed audit reran the default coverage gate
  (5,816 tests passed at 93.38% branch coverage) and then exercised formal
  negative boundaries that Q08 did not cover. It found milestone blockers in
  ordered multilevel `GROUP BY`, set-operation modifiers, inherited SELECT
  modifiers and joined-table grammar, direct analysis of `AT epoch` query
  roots, WITH/CTE root placement, guaranteed-raise handling for temporary
  `CREATE TABLE` and `INSERT`, cross-family table-target identifiers,
  `SELECT INTO` tail atomicity, and programmatic `CREATE TABLE` generation.
  Q08 therefore remains `DONE` as a historical positive gate, while
  **Milestone 1 is reopened and is not certified**.
- Tasks Q09–Q21 below are the bounded remediation, formal-negative audit, and
  recertification queue. Milestone 2
  (P16–P35) is ineligible until every Q task is `DONE`; Q21 is the current
  recertification gate and must remain the highest-numbered Q task if Q20
  schedules another bounded fix.
- Completed **Q09 — ordered multilevel GROUP BY losslessness**. Q10 is the
  lowest-numbered remaining task.
- Completed **Q10 — set-operation modifier conformance**. Q11 is the
  lowest-numbered remaining task.
- Completed **Q11 — SELECT modifier, row-limit, and lock-tail conformance**.
  Q12 is the lowest-numbered remaining task.
- Completed **Q12 — joined-table formal grammar**. Q13 is the lowest-numbered
  remaining task.
- Completed **Q13 — analyzer-safe historical query roots**. Q14 is the
  lowest-numbered remaining task.
- Completed **Q14 — WITH/CTE query-expression and placement conformance**.
  Q15 is the lowest-numbered remaining task.
- Completed **Q15 — CREATE TABLE guaranteed-raise completion**. Q16 is the
  lowest-numbered remaining task.
- Completed **Q16 — INSERT fail-closed parser conformance**. Q17 is the
  lowest-numbered remaining task.
- A Git remote is configured. Repository agents make local commits only and
  never push.

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
| Q09 | DONE   | Ordered multilevel GROUP BY losslessness      | Q08                 | `feat: preserve ordered multilevel group by`             |
| Q10 | DONE   | Set-operation modifier conformance            | Q09                 | `fix: enforce Vertica set operation modifiers`           |
| Q11 | DONE   | SELECT modifier, row-limit, and lock-tail conformance | Q10           | `fix: enforce Vertica select modifiers`                  |
| Q12 | DONE   | Joined-table formal grammar                   | Q11                 | `fix: enforce Vertica joined table grammar`              |
| Q13 | DONE   | Analyzer-safe historical query roots          | Q09–Q12             | `fix: make historical queries analyzer safe`             |
| Q14 | DONE   | WITH/CTE query-expression and placement conformance | Q13           | `fix: enforce cte query expression boundaries`           |
| Q15 | DONE   | CREATE TABLE guaranteed-raise completion      | Q14                 | `fix: complete create table guaranteed raises`           |
| Q16 | DONE   | INSERT fail-closed parser conformance         | Q14, Q15            | `fix: make insert parsing fail closed`                   |
| Q17 | TODO   | Analysis table-target identifier conformance  | Q02, Q03, Q15, Q16  | `fix: align analysis table target identifiers`           |
| Q18 | TODO   | SELECT INTO placement and tail atomicity      | Q02, Q17            | `fix: make select into tails atomic`                     |
| Q19 | TODO   | CREATE TABLE strict AST generation contract   | Q05, Q15, Q17       | `fix: validate create table asts`                        |
| Q20 | TODO   | Milestone 1 formal-syntax negative audit      | Q09–Q19             | `test: audit milestone one formal negatives`             |
| Q21 | TODO   | Milestone 1 recertification gate              | Q20                 | `test: recertify milestone one analysis surface`         |

### Milestone 2 — administration and remaining DDL (deferred)

Deferred until every Milestone 1 Q task is `DONE`; Q21 is the current final
gate. Milestone 2 task numbering, dependencies, and specifications are
intentionally unchanged from the prior plan revision.

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
   become eligible only after every Q task is `DONE`. Within the active
   milestone, select the lowest-numbered `TODO` task whose dependencies are
   all `DONE`, change it to `IN_PROGRESS` in both the dashboard and its detail
   heading, and do no other task.
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

The bounded tasks below close verified gaps between the completed foundation
and the milestone goal — parsing, analyzing, and regenerating
`SELECT`/CTE/temporary-table workloads. Q01–Q08 preserve their historical
completion records. The 2026-08-21 audit reopened the milestone with Q09–Q21
because several named residuals were milestone blockers and the positive Q08
corpus did not exercise the required formal-negative boundaries. No
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
   the acceptance gate renumbered Q07 → Q08 before any gate work began.
   Earlier references to Q07 in this same record describe the then-current
   gate and are retained as historical sequencing.

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

**2026-08-21 audit supersession.** The preceding paragraph is retained as
Q08's historical completion record, not as the current milestone verdict.
The fresh audit recorded in Current state proved that several of those named
residuals violate the milestone's own parsing/analyzing/regenerating outcome
and found additional uncovered formal-negative paths. Q08 remains `DONE`, but
Milestone 1 is reopened. Only the current highest-numbered recertification
gate may certify it again.

### Q09 — ordered multilevel `GROUP BY` losslessness — `DONE`

**Outcome.** Preserve the source order and meaning of every documented
ordinary and multilevel grouping item instead of storing each construct in a
fixed bucket that regenerates in a different order.

**Required work.** Re-open the 26.2 `GROUP BY`, `ROLLUP`, `CUBE`, `GROUPING
SETS`, and `GROUPING_ID` pages and inspect the installed SQLGlot parser,
canonical `exp.Group` contract, generator, scope builder, and optimizer
rewrites before choosing a representation. Give Vertica one typed,
source-ordered sequence capable of interleaving ordinary expressions,
`ROLLUP`, `CUBE`, and `GROUPING SETS`, including repeated constructs of the
same kind. `GROUP BY ROLLUP(a), CUBE(b), GROUPING SETS(c)` and `GROUP BY
CUBE(a), c, ROLLUP(b)` must regenerate in that exact order in compact and
pretty modes. Preserve parentheses and empty grouping sets exactly where they
are semantically material. Audit inherited `Group` fields and source forms
such as `GROUP BY ALL`, `DISTINCT`, and `TOTALS`; any form outside the pinned
Vertica grammar must fail through a dedicated guaranteed-raise path at all
four parser error levels, and malformed/programmatic group trees must be
rejected by strict Vertica generation rather than reordered, dropped, or
rendered as foreign SQL.

Add positive and negative matrices covering ordinary-only, one and multiple
instances of each multilevel construct, every interleaving direction,
no-argument and explicit-argument `GROUPING_ID`, aliases/ordinals where the
source permits them, nested queries, CTEs, set-operation branches, comments,
compact/pretty regeneration, parse-after-generate equality, `dump()`/load,
copy/transform parent metadata, and optimizer/qualification/lineage
stability. If a Vertica-specific node is required, include the customary
four-dialect direct/nested foreign-generation matrix and verify installed
SQLGlot transforms do not silently replace it with the old bucketed shape.

**Explicit exclusions.** Server-side grouping cardinality, aggregate-value
evaluation, optimizer cost choices, and unrelated window-function ordering.
Do not redesign set-operation nodes (Q10) or historical query roots (Q13).

**Primary sources.** [GROUP BY clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/group-by-clause/),
[ROLLUP aggregate](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/group-by-clause/rollup-aggregate/),
[CUBE aggregate](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/group-by-clause/cube-aggregate/),
[GROUPING SETS aggregate](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/group-by-clause/grouping-sets-aggregate/),
and [GROUPING_ID](https://docs.vertica.com/26.2.x/en/sql-reference/functions/aggregate-functions/grouping-id/).

**Completion record.** Re-opened all five 26.2 primary sources and found no
material grammar contradiction. The GROUP BY page explicitly describes an
ordered aggregate-expression list, permits multiple `GROUPING SETS`, `CUBE`,
and `ROLLUP` aggregates in one query, and includes the exact formerly-lossy
`GROUP BY ROLLUP(a), CUBE(b), GROUPING SETS(c)` example; the subordinate pages
confirm parentheses as semantically material (`ROLLUP((a,b),c)`), `()` as the
grand-total grouping set, `CUBE`/`ROLLUP` nesting inside `GROUPING SETS`, and
both zero-argument and explicit-argument `GROUPING_ID`. The GROUP BY formal
syntax also documents one `/*+GBYTYPE(HASH|PIPE)*/` hint. Two editorial slips
were treated as non-normative because the surrounding syntax, restrictions,
and examples are unambiguous: the CUBE page says “use the ROLLUP clause” in
one introductory sentence, and its displayed syntax is the generic
`GROUP BY group-expression[, ...]` rather than a CUBE-specific production.

Added `vexp.VerticaGroup(exp.Group)`, retaining canonical Group identity for
scope/optimizer code while replacing SQLGlot 30.13's four fixed buckets
(`expressions`, `grouping_sets`, `cube`, `rollup`) with one source-ordered
typed `expressions` list. Ordinary expressions and repeated/interleaved
canonical `exp.Rollup`, `exp.Cube`, and `exp.GroupingSets` children now render
in exact source order in compact and pretty modes; parentheses, tuple groups,
and empty grouping sets remain canonical children. An optional typed
`algorithm` child preserves `GBYTYPE(HASH|PIPE)` in its documented position.
The dedicated `_raise_group_by_error` path guarantees `ParseError` at
`IMMEDIATE`, `RAISE`, `WARN`, and `IGNORE` for inherited `GROUP BY ALL`,
`DISTINCT`, `TOTALS`, `WITH ROLLUP`/`WITH CUBE`, malformed construct lists,
and malformed/duplicate GBYTYPE hints. `VerticaGenerator.group_sql` accepts
ordinary-only canonical `exp.Group` trees for foreign/programmatic
interoperability, but rejects canonical bucket fields, all/totals modifiers,
falsey extras, empty/wrong children, nested invalid constructs, and invalid
algorithms with `UnsupportedError` rather than reordering, dropping, or
emitting foreign SQL. `VerticaGroup` fails atomically, direct or SELECT-nested,
against PostgreSQL, DuckDB, MySQL, and SQLite at `RAISE`, `WARN`, and `IGNORE`.
Qualification, optimization, scope traversal, lineage, copy, transform,
parent/index metadata, dump/load, CTE/subquery/set-branch placement, aliases,
ordinals, comments, and both `GROUPING_ID` forms are pinned; installed
SQLGlot transforms preserve the custom Group subclass and never reconstruct
the old bucketed shape. Updated the Q04 corpus regression from its former
named-loss assertion to the ordered contract, plus architecture, coverage,
roadmap, source inventory, and changelog documentation.

The focused `test_group_by.py` module passed 134 tests; the affected Q04
corpus plus neighboring workload, keyword, query-extension, and AST-safety
suites passed 278 tests. The default CPython 3.12.6 gate passed 5,951 tests at
93.25% branch coverage with Ruff lint/formatting, strict mypy, and diff checks
clean. Isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7,
and 3.15.0rc1 each passed 5,951 tests, with 3.15 treating deprecations as
errors. The sdist/wheel build, clean force-install, `pip check`, and installed-
wheel `python -I` smoke (`SELECT a, b FROM t GROUP BY CUBE(a), b, ROLLUP(a)`,
returning `Select` with a `VerticaGroup` child) passed.

### Q10 — set-operation modifier conformance — `DONE`

**Outcome.** Make the canonical set-operation tree express exactly Vertica's
operator-specific duplicate and branch contract, with no inherited modifier
that generates unsupported SQL.

**Required work.** Re-open all four 26.2 set-operation pages and audit the
installed SQLGlot set parser, precedence/associativity logic, canonical
`SetOperation` fields, generator, scope traversal, and optimizer rewrites.
Support `UNION` with its default/DISTINCT and `ALL` modes. Treat `INTERSECT`,
`EXCEPT`, and its `MINUS` synonym as DISTINCT-only, rejecting `ALL` at all
four parser error levels. Reject inherited name-matching or correspondence
forms (`BY NAME`, `CORRESPONDING`, and their canonical `by_name`/`on`/`side`/
`kind` states) for every operator unless a re-opened 26.2 primary source
explicitly admits one. Strict Vertica generation must validate direct,
nested, and programmatically mutated set trees before emitting any text; it
must not emit `INTERSECT ALL`, `EXCEPT ALL`, or foreign UNION syntax and must
not silently discard a modifier.

Preserve Vertica's precedence and left-to-right behavior, parentheses,
`MINUS` parsing/canonicalization, CTE and subquery placement, branch-local
`ORDER BY`/`LIMIT`/`OFFSET`, whole-compound tails, comments, compact/pretty
round trips, serialization, transform/parent metadata, scope traversal,
qualification, optimization, and lineage. Test operator chains whose
individual branches carry different legal modifiers so validation is applied
to the owning branch rather than only the compound root. Include strict AST
mutation cases for every relevant installed-SQLGlot field and all-level
source-negative matrices.

**Explicit exclusions.** Ordered grouping (Q09), the exact SELECT tail value
grammar (Q11), historical prefix wrapping (Q13), and server-side type/
cardinality compatibility between branches.

**Primary sources.** [UNION clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/union-clause/),
[INTERSECT clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/intersect-clause/),
[EXCEPT clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/except-clause/),
and [MINUS clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/minus-clause/).

**Completion record.** Re-opened all four 26.2 primary sources and found no
material contradiction. UNION's formal grammar admits omitted/default
DISTINCT, explicit DISTINCT, and ALL; INTERSECT and EXCEPT explicitly prohibit
ALL and describe distinct results; EXCEPT explicitly requires left-to-right
evaluation unless parentheses intervene; and the MINUS page defines MINUS
only as an EXCEPT alias. None documents SQLGlot's BY NAME, CORRESPONDING,
side, kind, or column-matching forms. Explicit DISTINCT on INTERSECT/EXCEPT/
MINUS is accepted as a semantic-no-op spelling and canonicalized to the same
DISTINCT-only tree/output as omission, matching UNION's existing explicit-
DISTINCT canonicalization and the task's “DISTINCT-only” contract rather than
inventing a second duplicate state.

Audited installed SQLGlot 30.13's `Parser.parse_set_operation`, iterative
left-associated `_parse_set_operations`, canonical `SetOperation.arg_types`,
`Generator.set_operation`/`set_operations`, and scope/optimizer behavior.
Kept the canonical `exp.Union`, `exp.Intersect`, and `exp.Except` nodes: the
existing `distinct` Boolean is lossless, MINUS already tokenizes to EXCEPT,
and the canonical nested tree already preserves parentheses, left
association, CTE/subquery placement, branch-local ORDER BY/LIMIT/OFFSET, and
whole-compound tails. Added `_raise_set_operation_error` and a narrow
`parse_set_operation` override. It rejects INTERSECT/EXCEPT/MINUS ALL and
every non-`None` `by_name`/`on`/`side`/`kind` state at IMMEDIATE, RAISE, WARN,
and IGNORE, so permissive levels cannot return or normalize an unsupported
tree. UNION retains default/explicit DISTINCT and ALL exactly.

Added strict `VerticaGenerator.set_operation` validation before rendering
each direct or nested operator: only exact canonical operator classes, two
query operands, a real Boolean duplicate mode, the operator-specific
DISTINCT/ALL domain, and absent name-matching fields are accepted. This also
rejects falsey programmatic extras (`by_name=False`, empty `on`, empty
`side`/`kind`) rather than treating them as absent, and invalid inner nodes
raise before the generator returns any compound SQL. Valid foreign-parsed
canonical set trees still generate Vertica. Added
`tests/test_set_operations.py` with 86 tests covering every documented mode,
MINUS canonicalization, mixed chains and per-node modifier ownership,
parentheses, CTE/subquery and branch/compound-tail placement, comments,
compact/pretty round trips, dump/load, copy/transform parent metadata,
all-level source negatives, strict direct/nested AST mutations, scope
traversal, qualification, optimization, lineage, and foreign-parsed valid
trees. Updated architecture, coverage, roadmap, and changelog contracts; the
four source links were already present in `docs/SOURCES.md` and needed no
duplicate entries.

The focused Q10 module passed 86 tests; the neighboring set/query/group/
workload/hint/AST suites passed 858 tests. The default CPython 3.12.6 release
gate passed 6,037 tests at 93.25% branch coverage with Ruff lint/formatting,
strict mypy, and diff checks clean. Isolated CPython 3.9.25, 3.10.20, 3.11.15,
3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed 6,037 tests, with 3.15
treating deprecations as errors. The sdist/wheel build, clean force-install,
`pip check`, and installed-wheel `python -I` smoke (`SELECT 1 UNION ALL SELECT
2 INTERSECT SELECT 3`, returning `Intersect`) passed.

### Q11 — SELECT modifier, row-limit, and lock-tail conformance — `DONE`

**Outcome.** Own the ordinary SELECT-level qualifier and tail grammar so
foreign SQLGlot modifiers cannot parse, partially survive, or regenerate as
if they were Vertica syntax.

**Required work.** Re-open the formal SELECT, LIMIT, and OFFSET pages and the
relevant 26.2 syntax-error entries, then audit installed SQLGlot's SELECT
qualifier, TOP/FETCH/LIMIT/OFFSET, lock, parser-finalization, generator, and
optimizer code. Preserve only the documented SELECT qualifier forms `ALL`
and `DISTINCT`; reject PostgreSQL-style `DISTINCT ON` in source and
programmatic trees. Pin the exact primary-source value grammar and clause
order for ordinary `LIMIT` and `OFFSET`, while retaining Vertica's separate
partitioned `LIMIT ... OVER` extension. Explicitly decide and test whether
`LIMIT ALL` is stored or deliberately canonicalized to clause absence; either
choice must be documented as semantic no-op canonicalization rather than an
accidental loss.

Reject `FETCH`, comma-form `LIMIT`, `PERCENT`, `WITH TIES`, and recognized
`TOP` forms at every parser error level; permissive levels must not return a
partial `SELECT TOP` or normalize an unsupported form into different SQL.
Support only `FOR UPDATE [OF table-name[, ...]]` and reject foreign lock
strengths (`SHARE`, `KEY SHARE`, `NO KEY UPDATE`) and wait options (`NOWAIT`,
`SKIP LOCKED`). Audit and validate every installed canonical limit/fetch/lock
field during Vertica generation so a programmatic or foreign AST either
renders valid Vertica SQL or raises the documented unsupported exception
atomically. Do not silently discard any recognized tail.

Cover direct queries, subqueries, CTE bodies, every set-operation ownership
position stabilized by Q10, comments, parameters and boundary values allowed
by the primary sources, clause permutations, all four parser error levels,
strict AST mutation, compact/pretty round trips, serialization, and
qualification/optimization/lineage stability. Correct the
LIMIT/OFFSET/FETCH coverage row to distinguish supported grammar from
intentional canonicalization and explicit rejection.

**Explicit exclusions.** Join conditions (Q12), set-operation modifier
ownership (Q10), `TIMESERIES`, and catalog/transaction lock effects. Valid
semantic lowerings for unrelated non-Vertica input, such as the existing
`QUALIFY` lowering, are not broadened or prohibited here.

**Primary sources.** [SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/),
[LIMIT clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/limit-clause/),
[OFFSET clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/offset-clause/),
and [SQLSTATE 42601 messages](https://docs.vertica.com/26.2.x/en/error-messages/sql-state-list/messages-associated-with-sqlstate-42601/).

**Completion record.** Re-opened all four 26.2 primary sources and audited
installed SQLGlot 30.13's SELECT qualifier/TOP parser, query-modifier loop,
LIMIT/FETCH/OFFSET/lock parsers, canonical `Distinct`/`Limit`/`LimitOptions`/
`Fetch`/`Offset`/`Lock` fields, generator ordering, set-operation modifier
promotion, scope traversal, qualification, optimization, and lineage. The
sources confirm only omitted/explicit `ALL`, plain `DISTINCT`, ordinary and
partitioned LIMIT, OFFSET, and `FOR UPDATE [OF table-name[, ...]]`; the error
catalog independently pins comma-form LIMIT plus duplicate LIMIT, OFFSET, and
FOR UPDATE as syntax errors. Two editorial contradictions were recorded rather
than guessed away. First, the current LIMIT formal block displays only
`num-rows OVER (...) | ALL`, accidentally omitting the ordinary numeric branch
that the same page's prose and worked `LIMIT 10` example exercise. Second,
SELECT's formal block places OFFSET before LIMIT, while the official
set-operation pages and existing official-example corpus use LIMIT before
OFFSET. Both relative source orders are therefore accepted and canonicalized
to stable `LIMIT ... OFFSET ...`; ORDER must precede either and FOR UPDATE must
follow both.

Added `_raise_select_modifier_error` and a Vertica-owned query-modifier loop so
recognized duplicate or misordered SELECT tails raise `ParseError` at
IMMEDIATE, RAISE, WARN, and IGNORE instead of returning a partial AST. SELECT
qualifiers are closed to omitted/explicit ALL (canonical absence) and plain
`exp.Distinct`; DISTINCT ON, duplicate qualifiers, SELECT kinds/operation
modifiers, and contextual unquoted-ASCII TOP fail closed. Ordinary LIMIT and
OFFSET remain canonical nodes and accept lexically nonnegative integer
literals, including zero and arbitrarily large digits without `int()`
conversion, plus SQLGlot's anonymous JDBC placeholder. Negative, decimal,
string, expression, and named-placeholder counts fail closed, as do FETCH,
comma-form LIMIT, PERCENT, ROW/ROWS, WITH TIES, and BY fields. `LIMIT ALL` is
now a deliberate semantic-no-op canonicalization: a private parse-only marker
keeps subsequent OFFSET/FOR UPDATE parsing and comments intact, then is removed
before the AST escapes. The independent `PartitionedLimit` path remains typed
and now pins a positive literal count plus nonempty PARTITION BY and ORDER BY.

FOR UPDATE remains one canonical `exp.Lock`; SHARE/KEY SHARE/NO KEY UPDATE,
NOWAIT/WAIT/SKIP LOCKED, empty OF lists, and duplicates fail closed. Auditing
set tails found SQLGlot promotes ORDER/LIMIT/OFFSET from the right SELECT to the
compound root but omits `locks`, producing invalid `right SELECT FOR UPDATE
ORDER BY ...` on generation. Vertica now promotes that trailing lock too, so
the documented tail owns the whole compound query. Strict generator validation
checks direct and nested qualifier/limit/offset/lock nodes, every installed
field including falsey extras, and foreign/programmatic trees before returning
SQL; valid foreign-parsed canonical trees still render. Updated architecture,
coverage, roadmap, source inventory, changelog, and Q04's former LIMIT ALL
residual regression. Catalog table existence, transaction permissions, and
lock effects remain server concerns.

The focused `test_select_modifiers.py` module passed 222 tests; the combined
focused query/set/group/workload/hint/AST suites passed 1,080. The default
CPython 3.12.6 release gate passed 6,259 tests at 93.13% branch coverage with
Ruff lint/formatting, strict mypy, and diff checks clean. Isolated CPython
3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed
6,259 tests, with 3.15 treating deprecations as errors. The sdist/wheel build,
clean force-install, `pip check`, and installed-wheel `python -I` smoke
(`SELECT DISTINCT a FROM t ORDER BY a LIMIT 2 OFFSET 1 FOR UPDATE`, returning
`Select`) passed.

### Q12 — joined-table formal grammar — `DONE`

**Outcome.** Enforce Vertica's documented joined-table kinds and predicate
rules at both parse and generation boundaries.

**Required work.** Re-open the 26.2 joined-table, join-syntax, natural-join,
inner-join, and outer-join pages and audit installed SQLGlot's join parser,
canonical `exp.Join` fields, dialect rewrites, generator, scope traversal, and
the existing Vertica hint override. Preserve documented INNER/default,
LEFT/RIGHT/FULL `[OUTER]`, NATURAL, CROSS, comma, and NATURAL outer variants,
plus `ON`, the documented alternative `USING`, `TABLESAMPLE`, and structured
Vertica join hints in their legal positions. Require `ON` or `USING` for
ordinary INNER/LEFT/RIGHT/FULL joined-table forms and reject either predicate
form on CROSS or NATURAL joins, as the primary sources require.

Reject join kinds that the Vertica grammar does not name and that the current
generator emits verbatim, including `ASOF` and `STRAIGHT_JOIN`, at all four
parser error levels. Validate programmatic/foreign `Join` trees before
generation, including every installed method/kind/side/on/using field and
invalid combinations; no unsupported kind or predicate may be silently
lowered, dropped, or rendered as Vertica. Keep existing intentional
equivalence lowerings such as SEMI/ANTI/APPLY only if the installed generator
produces valid canonical Vertica and the architecture contract explicitly
classifies that behavior; Q20 will audit those classifications rather than
this task guessing a new strict-input policy.

Test each legal kind, NATURAL outer combinations, predicate requirements,
multi-join chains, nested joins/subqueries/CTEs, join hints, samples on both
sides, comments, all error levels, strict AST mutations, compact/pretty
round trips, serialization, transform/parent metadata, qualification,
optimization, and lineage.

**Explicit exclusions.** Event-series `INTERPOLATE` semantic restrictions,
server-side join predicate type checks, optimizer join reordering/costing,
and SELECT tails (Q11).

**Primary sources.** [Joined-table](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/from-clause/joined-table/),
[Join syntax](https://docs.vertica.com/26.2.x/en/data-analysis/queries/joins/join-syntax/),
[Natural joins](https://docs.vertica.com/26.2.x/en/data-analysis/queries/joins/inner-joins/natural-joins/),
[Inner joins](https://docs.vertica.com/26.2.x/en/data-analysis/queries/joins/inner-joins/),
and [Outer joins](https://docs.vertica.com/26.2.x/en/data-analysis/queries/joins/outer-joins/).

**Completion record.** Re-opened all five exact 26.2 primary sources and
audited installed SQLGlot 30.13's join token sets, `_parse_join`/
`_parse_joins`, canonical `exp.Join.arg_types`, generic/PostgreSQL join and
lateral generation, PostgreSQL's SELECT preprocessing, scope traversal,
qualification, optimization, and lineage. The sources confirm default/
explicit INNER, LEFT/RIGHT/FULL `[OUTER]`, NATURAL, CROSS, comma joins,
TABLESAMPLE, ON, and the older USING alternative. One editorial tension is
now recorded explicitly: the joined-table and join-syntax display blocks put
`ON join-predicate` in optional brackets, while both pages' accompanying
restriction says ON is invalid for NATURAL/CROSS and required for every other
join type; the alternative-syntax section separately documents USING. The
task's required predicate matrix and those restriction paragraphs were
followed, so every ordinary explicit join requires exactly one ON or USING.
The natural-join page's more specific formal syntax requires OUTER in
`NATURAL {LEFT|RIGHT|FULL} OUTER JOIN`; that requirement is enforced even
though ordinary LEFT/RIGHT/FULL joins may omit OUTER.

Kept canonical `exp.Join` nodes and added a dedicated guaranteed-raise
`_raise_join_error` path. The parser captures whether the source token was a
comma before delegating to SQLGlot, because canonical SQLGlot deliberately
stores both a comma join and a predicate-free default JOIN as the same
fieldless node; comma joins remain valid, while source `JOIN b` now raises
`ParseError` at IMMEDIATE, RAISE, WARN, and IGNORE. Default/INNER and ordinary
outer forms require ON or a nonempty identifier-only USING list; CROSS and
NATURAL reject both; invalid method/side/kind combinations, ASOF, and
STRAIGHT_JOIN fail closed at all four levels. NATURAL inner and all three
formal NATURAL outer forms, multi-join chains, nested relations/subqueries/
CTEs, comments, TABLESAMPLE on both inputs, and existing structured
JTYPE/DISTRIB join hints retain canonical shape and round-trip behavior.

Strict generation validates every installed Join field, including falsey
foreign/programmatic `global_`, `match_condition`, `directed`, `expressions`,
and pivot extras, child/predicate/USING types, hint structure, and all
operator/predicate combinations. Canonical SELECT joins are validated through
a Vertica transform before inherited PostgreSQL preprocessing can remove or
rewrite them; direct/non-SELECT Join roots are validated again at `join_sql`.
This ordering closes the otherwise-silent hazard where an invalid SEMI/ANTI
tree could be eliminated before per-Join dispatch. Two pre-existing
equivalence lowerings were retained only after direct output probes and are
now classified in `ARCHITECTURE.md`: a SELECT-owned left SEMI/ANTI join with
one ON predicate becomes correlated `[NOT] EXISTS`, while CROSS/OUTER APPLY
becomes INNER/LEFT `JOIN LATERAL ... ON TRUE`. Right/full, USING, hinted, or
detached SEMI/ANTI variants and modifier-bearing APPLY forms fail rather than
emitting foreign syntax or dropping metadata. The canonical fieldless-node
ambiguity remains an intentional boundary: strict generation treats it as the
documented comma form because no AST provenance can distinguish a
programmatic missing-predicate JOIN; source text is unambiguous and rejected.

Added `tests/test_joins.py` with 111 focused tests covering documented kinds,
predicate rules, natural-outer spelling, samples/hints, chains/nesting/CTEs,
comments, all four parser error levels, the bounded lowerings, strict direct
and nested AST mutations, dump/load, copy/transform parent metadata,
qualification, optimization, scope traversal, lineage, and foreign-parsed
canonical interoperability. The focused module passed 111 tests; the combined
join/query/hint/DML/analysis neighbors passed 940. Updated architecture,
coverage, roadmap, source inventory, and changelog documentation. The default
CPython 3.12.6 release gate passed 6,370 tests at 93.13% branch coverage with
Ruff lint/formatting, strict mypy, and diff checks clean. Isolated CPython
3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed
6,370 tests, with 3.15 treating deprecations as errors. The sdist/wheel build,
clean force-install, `pip check`, and installed-wheel `python -I` smoke
(`SELECT * FROM a NATURAL LEFT OUTER JOIN b`, returning `Select`) passed.

### Q13 — analyzer-safe historical query roots — `DONE`

**Outcome.** Make a parsed SELECT `[ AT epoch ]` root participate directly in
ordinary SQLGlot query analysis with parity to the same unprefixed query,
without requiring callers to unwrap `.this`.

**Required work.** Re-open the formal SELECT and historical-query pages and
inspect installed SQLGlot query expression classes, `traverse_scope`, scope
building, qualification, optimization, lineage, expansion, transforms, and
generator dispatch before choosing the representation. Redesign the
parser-emitted historical-query root so direct calls to `traverse_scope`,
`qualify`, `optimize`, and `lineage` recognize it as a real query for plain
SELECT and UNION/INTERSECT/EXCEPT roots, including queries with a leading WITH
clause. The prefixed and unprefixed forms must expose equivalent source,
column, CTE, and scope graphs while the prefix continues to apply to the
entire compound query rather than one branch.

Preserve the Q06 epoch/time value contract, comments, compact/pretty output,
parentheses, whole-query tail ownership, `dump()`/load, copy/transform parent
links, multi-statement boundaries, and atomic foreign-generation behavior.
Audit compatibility with already serialized `AtEpochQuery` trees and provide
a safe load/generation path or an explicit documented migration if the node
shape must change. Strict Vertica generation must reject malformed
programmatic prefix/query combinations atomically. Add direct analysis tests
for SELECT and each set-operation root, joined/grouped queries, CTE and source
expansion, ambiguous and qualified columns, and column lineage; calling
`.this` in those tests is not acceptable evidence.

**Explicit exclusions.** The CTAS-only `AtEpochProperty` remains Q07's
independent property. Whether an AT-prefixed query is legal as a CTE body is
decided in Q14 after this analyzer-safe shape exists. No catalog snapshot
availability or historical-data semantics are modeled.

**Primary sources.** [SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/)
and [Historical queries](https://docs.vertica.com/26.2.x/en/data-analysis/queries/historical-queries/).

**Completion record.** Re-opened both exact 26.2 primary sources. SELECT still
places `[ AT epoch ]` before the optional WITH clause and the complete
SELECT/set-operation production; Historical queries describes the same
`EPOCH LATEST`/integer and `TIME 'timestamp'` forms and only catalog/runtime
restrictions (AHM range, snapshot retention, and temporary-table behavior).
No material grammar contradiction was found.

Replaced the parser-emitted Q06 wrapper with four analyzer-visible concrete
roots: `AtEpochSelect(exp.Select)`, `AtEpochUnion(exp.Union)`,
`AtEpochIntersect(exp.Intersect)`, and `AtEpochExcept(exp.Except)`. Each stores
the prefix in typed `at_epoch_kind`/`at_epoch_value` children while retaining
the complete canonical query fields, so `traverse_scope`, `qualify`,
`optimize`, source expansion, and `lineage` now accept the public prefixed root
directly for plain, joined/grouped, CTE, UNION, INTERSECT, and EXCEPT queries.
The source/column/CTE/scope graphs match unprefixed controls; ambiguous-column
failures match as well. Parser provenance preserves the documented
prefix-before-WITH order now that these roots legitimately expose `with_`.

Vertica generation validates prefix values and the existing strict SELECT or
set-operation contract before rendering. SQLGlot's base set renderer indexes
operator defaults by exact class, so validated historical set roots are copied
to their canonical operator only inside generation; the public tree remains
the custom analyzer-safe subclass. All four roots fail atomically in direct
and CTE-nested PostgreSQL, DuckDB, MySQL, and SQLite generation. The public
Q06 `AtEpochQuery` wrapper remains loadable and renderable, with a dump/load
regression, as the compatibility path for previously serialized trees; new
parsing never emits it. The independent CTAS `AtEpochProperty` is unchanged.

The focused `test_at_epoch_query.py` module passed 187 tests; the affected
Q04 corpus plus focused Q09–Q13 query/AST neighbors passed 806 tests. The
default CPython 3.12.6 gate passed 6,385 tests at 93.08% branch coverage with
Ruff lint/formatting, strict mypy, and diff checks clean. Isolated CPython
3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed
6,385 tests, with 3.15 treating deprecations as errors. The sdist/wheel build,
clean force-install, `pip check`, and installed-wheel `python -I` smoke
(`AT EPOCH LATEST SELECT a FROM t UNION SELECT a FROM u`, returning
`AtEpochUnion`) passed.

### Q14 — WITH/CTE query-expression and placement conformance — `DONE`

**Outcome.** Restrict WITH and every CTE body to the documented query surface,
with guaranteed failure instead of top-level dispatcher re-entry, truncation,
empty SQL, or raw Python exceptions.

**Required work.** Re-open the 26.2 WITH syntax, recursion, materialization,
SELECT, and INSERT pages and inspect installed SQLGlot's `_parse_cte`, outer
WITH attachment, statement dispatcher, canonical `With`/`CTE` fields,
generator, optimizer, and scope code. Source-pin an explicit allowed-root
contract rather than testing only `isinstance(exp.Query)`: ordinary SELECT
and Vertica query extensions, supported set operations, subordinate WITH,
and documented recursive query forms must work; side-effecting `SELECT INTO`
and all DML, PROFILE, EXPLAIN, directed-query, DDL, and administrative roots
must not be CTE bodies. Decide AT-prefixed CTE legality from the formal
`query-expression` contract only after Q13's analyzer-safe representation is
stable. Pin inherited `VALUES` and bare-`FROM` behavior explicitly instead of
accepting it by accident.

Enforce the corresponding outer-WITH placement contract. Preserve leading
WITH on SELECT and the documented target-following `INSERT INTO target WITH
... SELECT` form; reject leading-WITH UPDATE/DELETE/INSERT/MERGE, CREATE, DROP,
TRUNCATE, COPY, PROFILE/EXPLAIN, directed-query, historical-prefix, and other
non-query forms without returning a DML AST, a bare `With` sentinel, or a
truncated prefix at permissive error levels. Route every recognized violation
through a dedicated guaranteed-raise wrapper at IMMEDIATE, RAISE, WARN, and
IGNORE. Reject inherited per-CTE `AS [NOT] MATERIALIZED` and recursive
`SEARCH`/`CYCLE` fields unless a re-opened 26.2 source expressly supports
them; preserve Vertica's clause-level materialization hint and documented
plain/multiple/subordinate/recursive CTEs.

Strict Vertica generation must validate direct and nested programmatic
`With`/`CTE` children, root placement, aliases/column lists, recursion fields,
and modifiers before rendering any text. Add source and AST matrices for
direct/nested invalid bodies, comments around the body boundary, malformed
multi-statement input, all four parser error levels, compact/pretty valid
round trips, serialization, parent metadata, qualification/optimization/
lineage, and foreign generation. Retain valid hinted and recursive workload
cases from Q08.

**Explicit exclusions.** General INSERT validation outside WITH placement
(Q16), historical-root analysis internals (Q13), and server recursion depth or
materialization choices.

**Primary sources.** [WITH clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/with-clause/),
[WITH clause recursion](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/with-clause/with-clause-recursion/),
[Materialization of WITH clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/with-clause/materialization-of-with-clause/),
[SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/),
and [INSERT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/insert/).

**Completion record.** Re-opened all five 26.2 primary sources and audited
installed SQLGlot 30.13's `_parse_select_query`, `_parse_with`, `_parse_cte`,
statement dispatch, canonical `With`/`CTE` fields, generator, scope traversal,
qualification, optimization, and lineage. The WITH formal production places
`[ subordinate-WITH-clause ] query-expression` inside each CTE and documents
plain/multiple/subordinate CTEs, clause-level
`ENABLE_WITH_CLAUSE_MATERIALIZATION`, and UNION/UNION ALL recursion. Its broad
restriction says WITH supports SELECT and INSERT statements, while its sole
INSERT example is specifically `INSERT INTO target WITH ... SELECT`; the
separate INSERT formal syntax likewise owns the target before its SELECT
query-expression. This was treated as the source-backed distinction between a
side-effect-free SELECT query-expression in each CTE body and the documented
target-following outer INSERT form, not permission for INSERT to become a CTE
body or for leading-WITH INSERT. SELECT's separate `[ AT epoch ] [ WITH-clause
] SELECT ...` statement production confirms `AT epoch` is a prefix outside the
CTE `query-expression`, so AT-prefixed CTE bodies are now rejected. No source
documents inherited bare `VALUES`, bare `FROM`, per-CTE `AS [NOT]
MATERIALIZED`, `USING KEY`, or recursive SEARCH/CYCLE forms; all fail closed.

Added a CTE parsing-depth boundary to `VerticaParser._parse_statement` and a
Vertica-owned `_parse_cte`. While a CTE body is active, only a nonempty SELECT
(including supported Vertica query extensions), a supported canonical
UNION/INTERSECT/EXCEPT tree whose branches satisfy the same rule, and a
subordinate WITH may parse. PROFILE, EXPLAIN, directed-query, AT-prefix,
SELECT-INTO, DML, DDL, COPY, administrative, VALUES, and bare-FROM roots now
raise through `_raise_cte_error` at IMMEDIATE, RAISE, WARN, and IGNORE instead
of re-entering the full top-level dispatcher, returning a With sentinel,
truncating, or producing empty SQL. The same wrapper owns invalid outer-WITH
placement; ordinary SELECT and the official target-following INSERT form remain
valid, while leading-WITH INSERT/UPDATE/DELETE/MERGE/CREATE/DROP/TRUNCATE/COPY/
PROFILE/EXPLAIN/historical-prefix forms fail atomically. Parenthesis-boundary
comments are retained explicitly. Clause-level materialization hints and
plain/multiple/subordinate/recursive workload cases remain byte-stable.

Strict generation now validates direct and nested `With`/`WithHint`/`CTE`
trees before returning SQL: root placement, a nonempty typed CTE list,
recursive/search state, exact alias and optional column-list shapes, body-root
allowlists, materialized/scalar/key modifiers, hint identity, and unknown
fields. Valid plain canonical CTEs remain portable to foreign dialects; the
existing custom `WithHint` continues to fail atomically in PostgreSQL,
DuckDB, MySQL, and SQLite. Added `tests/test_cte.py` with 163 tests covering
the positive forms, exhaustive all-level source negatives, malformed
multi-statement boundaries, comments, strict AST mutations, parent metadata,
dump/load and compact/pretty round trips, scope traversal, qualification,
optimization, lineage, and foreign contracts; updated Q13's former
AT-prefixed-CTE observation into the new four-level rejection contract. The
combined focused query/DML/analysis neighbors passed 1,738 tests. The default
CPython 3.12.6 gate passed 6,539 tests at 93.02% branch coverage with Ruff
lint/formatting, strict mypy, and diff checks clean. Isolated CPython 3.9.25,
3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed 6,539
tests, with 3.15 treating deprecations as errors. The sdist/wheel build, clean
force-install, `pip check`, and installed-wheel `python -I` smoke (subordinate
WITH query returning `Select`) passed.

### Q15 — CREATE TABLE guaranteed-raise completion — `DONE`

**Outcome.** Make every recognized malformed CREATE TABLE form in the
Milestone 1 lifecycle fail with `ParseError` at every parser error level,
without silent normalization, generic `Command` fallback, truncated ASTs, or
raw Python exceptions.

**Required work.** Re-open the 26.2 CREATE TABLE and CREATE TEMPORARY TABLE
pages and audit every CREATE TABLE front-door, lookahead, and shared
definition/CTAS/LIKE helper that can call plain `raise_error`, assert, or
continue after an error. Route table-family validation through the existing
dedicated guaranteed-raise contract (or a narrowly factored equivalent),
including CTAS column-name lists and encodings, `ON COMMIT`, `DISK_QUOTA`,
segmentation, ordering, partitioning, inherited privileges, projection
segmentation, scope/temporary prefixes, and table-only CREATE modifiers.
Recognized malformed TABLE syntax must never degrade to `exp.Command` at any
error level.

Cover the audit's concrete failures: invalid or incomplete `ON COMMIT`, empty
CTAS column lists, invalid `ACCESSRANK`/`ENCODED BY`/segmentation clauses,
scope without TEMPORARY, LOCAL/GLOBAL misuse, `OR REPLACE`, duplicate or
contradictory scope/temporary prefixes, misplaced clauses, unexpected end of
input, and malformed multi-statement boundaries. Run every negative at
IMMEDIATE, RAISE, WARN, and IGNORE and assert `ParseError` rather than merely
asserting that parsing fails somehow. Preserve all currently valid permanent
control forms and unscoped/GLOBAL/LOCAL temporary definition, LIKE, and CTAS
forms, including Q01/Q07 behavior, comments, compact/pretty output,
serialization, multi-statement parsing, and query analysis.

**Explicit exclusions.** New CREATE grammar, flex/external tables, identifier
byte/qualification rules (Q17), and programmatic CREATE generation validation
(Q19). Shared helper edits may protect permanent TABLE forms, but acceptance
scope is the already-semantic TABLE family, not other CREATE statement kinds.

**Primary sources.** [CREATE TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-table/)
and [CREATE TEMPORARY TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-temporary-table/).

**Completion record.** Re-opened both exact 26.2 primary sources and audited
the installed SQLGlot 30.13 CREATE parser plus every plugin CREATE TABLE
front door and definition/LIKE/CTAS helper. No new material contradiction was
found: the permanent grammar has definition, LIKE, and CTAS productions; the
temporary grammar has definition and CTAS productions, one optional
GLOBAL/LOCAL scope before TEMPORARY, and the documented ON COMMIT, physical-
design, privilege, and quota clauses. Q01's already-recorded formal split
that omits scope from the displayed temporary-CTAS production remains the
deliberate operational-evidence exception and was not changed. All displayed
comma lists require another item after each comma, so trailing commas are
invalid in definition, CTAS name, GROUPED, and ENCODED BY lists.

Made CREATE TABLE one fail-closed parser transaction: `_parse_create_table`
temporarily uses `ErrorLevel.IMMEDIATE` while its body and inherited/shared
helpers run, then restores the caller's configured level in `finally`. This
is narrowly scoped to the already-semantic TABLE family and guarantees that
plain SQLGlot `raise_error` calls in schema disambiguation, CTAS column and
encoding parsing, ON COMMIT, quota, segmentation, ordering, partitioning,
privilege, and end-of-input helpers cannot return at WARN/IGNORE, aggregate
past unsafe code at RAISE, silently repair input, produce a partial AST, or
reach an assertion/unbound local. Front-door scope-without-TEMPORARY and OR
REPLACE errors now use `_raise_create_table_error`; a provenance-aware
lookahead rejects duplicate or contradictory GLOBAL/LOCAL/TEMPORARY prefixes
before generic CREATE fallback can turn them into `Command`. Added explicit
trailing-comma checks where SQLGlot's generic CSV helper intentionally accepts
them. Valid permanent and unscoped/GLOBAL/LOCAL temporary definition, LIKE,
and CTAS parsing remains unchanged, including Q01 scoped CTAS and Q07
historical-snapshot behavior. Programmatic CREATE validation remains Q19.

Expanded `tests/test_create_table.py` from 122 to 314 tests with 39 malformed
forms swept at IMMEDIATE, RAISE, WARN, and IGNORE, six valid definition/LIKE/
CTAS controls at every level, and three malformed multi-statement scripts at
every level. The focused module passed 314 tests; neighboring constraint,
foreign-property, workload, projection, external-table, and CTE suites passed
874 tests. The default CPython 3.12.6 release gate passed 6,731 tests at
92.97% branch coverage with Ruff lint/formatting, strict mypy, and diff checks
clean. Isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7,
and 3.15.0rc1 each passed 6,731 tests, with 3.15 treating deprecations as
errors. The sdist/wheel build, clean force-install, `pip check`, and installed-
wheel `python -I` smoke (`CREATE GLOBAL TEMPORARY TABLE q15_guard (id BIGINT)
ON COMMIT DELETE ROWS`, returning `Create`) passed.

### Q16 — INSERT fail-closed parser conformance — `DONE`

**Outcome.** Make malformed INSERT syntax fail at the parser boundary at every
error level instead of returning a normalized, unusable, or blank-rendering
`exp.Insert`.

**Required work.** Re-open the 26.2 INSERT and WITH pages and audit
`_parse_insert`, the DML validation helpers, all raw `raise_error` sites, and
parser finalization. Add a dedicated guaranteed-raise INSERT path and route
missing `INTO`, invalid target shapes/aliases, missing or conflicting query/
VALUES/default sources, empty column or VALUES lists, unsupported RETURNING
and foreign tail clauses, and any other recognized `insert_errors` result
through it. WARN and IGNORE must raise the same family `ParseError` as RAISE
and IMMEDIATE; they must not invent `INTO`, return a partial Insert, silently
drop a tail, or rely on later generator validation to produce empty SQL.

Preserve supported VALUES/default and INSERT-SELECT forms, explicit column
lists, hints/labels, the Q14 target-following WITH form, comments,
multi-statement boundaries, compact/pretty round trips, serialization,
qualification, optimization, and lineage. Add an exhaustive all-level source
matrix and direct AST/parser-shape tests for every error emitted by the shared
DML helper. Re-audit the existing strict INSERT generator only for regression
parity; any newly discovered independent generation gap must be scheduled as
a separate bounded Q task under protocol rule 6.

**Explicit exclusions.** UPDATE/DELETE/MERGE behavior, WITH root-placement
ownership (Q14, retained here only as regression coverage), cross-family target
identifier rules (Q17), and server constraint/default evaluation.

**Primary sources.** [INSERT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/insert/)
and [WITH clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/with-clause/).

**Completion record.** Re-opened both exact 26.2 primary sources and audited
installed SQLGlot 30.13's `_parse_insert`, insert-table and VALUES helpers,
canonical `Insert` fields, parser finalization, and generator. No material
contradiction was found. INSERT's formal grammar requires `INTO`, a named
table with an optional nonempty column list, and exactly one of `DEFAULT
VALUES`, one or more parenthesized nonempty VALUES rows, or a SELECT query.
The WITH page's official INSERT example confirms the already-supported
target-following `INSERT INTO target WITH ... SELECT` form. Catalog constraint,
default, coercion, and projection behavior remains server-side.

Added `_raise_insert_error` and made the inherited INSERT parse a narrowly
scoped `ErrorLevel.IMMEDIATE` transaction with the caller's level restored in
`finally`. Missing INTO and multi-table roots, every shared `insert_errors`
result, strict target/VALUES list provenance, and unconsumed tails now route
through the INSERT-specific guaranteed-raise boundary. IMMEDIATE, RAISE, WARN,
and IGNORE therefore all raise `ParseError` instead of inventing INTO,
returning a normalized or blank-rendering partial `Insert`, silently dropping
a tail, or reaching a raw helper failure. Closed inherited acceptances for
bare `VALUES 1`, trailing target/value/row commas, target PARTITION clauses,
missing/conflicting sources, aliases, empty lists, RETURNING, ON CONFLICT,
STORED, BY NAME, IF EXISTS, SETTINGS, REPLACE WHERE, and other recognized
foreign prefixes/tails. Shared structural validation now rejects a partition
stored on the target table as well, so parser and existing strict generator
remain in parity; the generator audit found no independent gap requiring a
new task.

Expanded `tests/test_dml.py` from 111 to 232 tests. The negative source matrix
runs every case at all four parser error levels; direct AST/helper cases cover
every INSERT validator branch; valid VALUES/default/SELECT/target-following
WITH controls run at every level; malformed multi-statement input proves the
following statement is not swallowed; and comment, compact/pretty round-trip,
dump/load, qualification, optimization, lineage, and strict generation
contracts remain pinned. The focused DML module passed 232 tests and the DML,
CTE, workload, PROFILE, and hint neighborhood passed 559. The default CPython
3.12.6 gate passed 6,852 tests at 93.01% branch coverage with Ruff lint and
formatting, strict mypy, and diff checks clean. Isolated CPython 3.9.25,
3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 each passed 6,852
tests, with 3.15 treating deprecations as errors. The sdist/wheel build, clean
force-install, `pip check`, and installed-wheel `python -I` smoke (`INSERT INTO
q16_target SELECT 1`, returning `Insert`) passed.

### Q17 — analysis table-target identifier conformance — `TODO`

**Outcome.** Give every Milestone 1 table-target family one consistent,
source-backed identifier and qualification contract in both parsing and
generation.

**Required work.** Re-open the 26.2 identifier, CREATE TEMPORARY TABLE, INSERT,
INTO TABLE, and DROP TABLE pages. Extract the already strict Q03 DROP target
component validation into a shared contract where appropriate, then apply it
to CREATE TABLE definition/LIKE/CTAS targets, INSERT targets,
`IntoTableClause` targets, and DROP TABLE controls. Pin the formal one-, two-,
and three-part qualification shapes, require schema when catalog is present,
reject a fourth part, and enforce valid UTF-8 plus the 128-byte limit per
component. Apply the established quoted-payload, empty-name, unquoted-start/
continuation, reserved/contextual-keyword, and case-folding rules consistently
rather than allowing each front door to inherit a different SQLGlot default.

Validate both source text at all four parser error levels and programmatic/
foreign `exp.Table`/`Identifier` trees during strict Vertica generation. The
boundary matrix must include 127-, 128-, and 129-byte ASCII and multibyte
identifiers, valid quoted Unicode, invalid unpaired surrogates, empty quoted
and unquoted components, catalog-without-schema AST shapes, each legal
qualification depth, four-part names, comments/aliases in adjacent legal
positions, and parse/generate/reparse shape equality. Demonstrate that all
four target families accept and reject the same names unless a primary source
documents a family-specific exception.

**Explicit exclusions.** Column/expression aliases, identifiers throughout the
rest of the repository, server catalog existence/cross-database access, and
statement-specific tail placement (Q18). Do not turn this into a general
tokenizer rewrite.

**Primary sources.** [Identifiers](https://docs.vertica.com/26.2.x/en/sql-reference/language-elements/identifiers/),
[CREATE TEMPORARY TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-temporary-table/),
[INSERT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/insert/),
[INTO TABLE clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/into-table-clause/),
and [DROP TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-table/).

### Q18 — SELECT INTO placement and tail atomicity — `TODO`

**Outcome.** Reject recognized but misplaced or duplicated INTO/ON COMMIT
syntax atomically at every parser error level, instead of returning a
truncated SELECT or silently dropping the malformed tail.

**Required work.** Re-open the formal SELECT and INTO TABLE pages, audit the
legal-slot `_parse_into` override and inherited SELECT final-token behavior,
and add a dedicated guaranteed-raise path that can distinguish ordinary
trailing junk from recognized misplaced INTO-family clauses. Reject INTO
after FROM/WHERE/other later clauses, duplicate INTO, aliases or column lists
attached to the target, duplicate/misplaced `ON COMMIT`, permanent-target
temporary clauses, and any recognized incomplete variant at IMMEDIATE, RAISE,
WARN, and IGNORE. No permissive level may return a plain `Select`, a partial
`SelectInto`, or a canonical query with the offending tail removed.

Preserve the legal Q02 contract and verify composition with leading WITH,
subqueries, TIMESERIES and other Vertica query extensions, parenthesized
queries, and every set-operation position the re-opened primary syntax
permits. Test comments at clause boundaries, multi-statement atomicity,
compact/pretty round trips, `dump()`/load, transform/parent metadata,
qualification/optimization/lineage, Q17 target validation, and strict
programmatic generation of the existing `SelectInto`/`IntoTableClause` shape.

**Explicit exclusions.** New target forms, table-target lexical rules (Q17),
temporary-table storage effects, and unrelated generic SELECT trailing-token
policy.

**Primary sources.** [SELECT](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/)
and [INTO TABLE clause](https://docs.vertica.com/26.2.x/en/sql-reference/statements/select/into-table-clause/).

### Q19 — CREATE TABLE strict AST generation contract — `TODO`

**Outcome.** Validate a canonical CREATE TABLE tree completely before
rendering so programmatic or foreign ASTs cannot produce invalid Vertica SQL
or lose a recognized property silently.

**Required work.** Re-open the 26.2 CREATE TABLE and CREATE TEMPORARY TABLE
pages and audit `VerticaGenerator.create_sql`, installed SQLGlot's canonical
`exp.Create` fields/property sorting, every table property renderer, and any
preprocessing that can mutate the tree before dispatch. Add a table-specific
structural validator that runs before property ordering or text emission. It
must validate root/kind, definition versus LIKE versus CTAS shape, expression
and property node types, duplicates/mutual exclusions, scope/temporary
combinations, `ON COMMIT`, `DISK_QUOTA`, `NO PROJECTION`, segmentation/order/
partition clauses, CTAS-only `AtEpochProperty` and encoded-by fields, and all
other installed canonical CREATE extras against the parser-supported contract.

At `unsupported_level=RAISE`, direct and nested programmatic mutations must
raise `UnsupportedError` atomically for concrete audit cases including LOCAL
without TEMPORARY, contradictory GLOBAL/LOCAL/TEMPORARY states, permanent
`ON COMMIT`, LOCAL temporary plus `DISK_QUOTA`, temporary CTAS plus illegal
segmentation, CTAS plus definition-only `NO PROJECTION`, definition-form
`AtEpochProperty`, wrong node types, duplicate properties, and foreign-only
Create fields. No property may be silently discarded even when the base
generator lacks a renderer. Preserve valid parser-produced property ordering,
compact/pretty output, Q01/Q07 behavior, Q17 target validation, serialization,
query analysis, and Q05's direct/nested four-dialect embedded-property
atomicity. Add a strict mutation matrix across definition, LIKE, and CTAS
roots rather than testing only one reversed valid property list.

**Explicit exclusions.** New CREATE syntax, parser guaranteed-raise work
(Q15), flex/external tables, physical-design validity that the existing parser
delegates to the server, and foreign-dialect support for Vertica properties.

**Primary sources.** [CREATE TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-table/)
and [CREATE TEMPORARY TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-temporary-table/).

### Q20 — Milestone 1 formal-syntax negative audit — `TODO`

**Outcome.** Prove that the remediated Milestone 1 surface owns every inherited
SQLGlot parse/generate field it exposes, and schedule any remaining concrete
gap before recertification.

**Required work.** This is a test-and-documentation audit, not an
implementation task. Re-open the complete 26.2 formal syntax for SELECT core,
FROM/joined tables, subqueries, GROUP BY/HAVING/ORDER BY, query extensions,
set operations, LIMIT/OFFSET/locks, WITH/recursion, SELECT INTO, temporary
CREATE definition/LIKE/CTAS, INSERT, and DROP TABLE. Inventory the installed
SQLGlot parser and canonical expression fields for each family, then classify
every exposed source/programmatic form as documented Vertica syntax, an
architecture-approved semantic lowering/canonicalization, an explicit
fail-closed boundary, or an uncovered product gap. Include direct roots,
nested/CTE/set-operation positions, comments, multi-statement boundaries, all
four parser error levels, and strict generator mutations.

Add durable negative matrices for the fixed boundaries from Q09–Q19 and
positive pins for deliberate canonicalizations such as the final Q11 decision
on `LIMIT ALL`. Re-evaluate existing equivalence lowerings (`QUALIFY`,
SEMI/ANTI joins, APPLY, and any other inherited rewrite found by the inventory)
against `ARCHITECTURE.md`; preserve them only when they generate valid,
semantically equivalent Vertica and are documented as such. Correct stale or
overbroad `docs/COVERAGE.md` rows, including ordered grouping, supported
LIMIT/OFFSET versus rejected FETCH, CTE root constraints, direct historical
analysis, and lifecycle identifier/fail-closed boundaries.

If the audit finds a new product gap, do not implement it here and do not mark
the milestone certified. Add one narrowly scoped Q task with its own source,
tests, exclusions, dependency, and commit title; place it after Q20, renumber
the recertification gate so it remains the highest Q number, and update every
gate cross-reference in this file, `AGENTS.md`, and `docs/ROADMAP.md`. Q20 may
be marked `DONE` only after its audit inventory and passing contract tests are
committed and every discovered implementation gap is represented by such a
task.

**Explicit exclusions.** Opportunistic grammar or production-code fixes,
Milestone 2 families, catalog-aware/server-only semantics, and milestone
certification itself (the final gate owns that decision).

**Primary sources.** The Q09–Q19 pages plus the linked 26.2 SELECT and
temporary-table statement subtrees. Record the exact pages re-opened in the
completion note.

### Q21 — Milestone 1 recertification gate — `TODO`

**Outcome.** Re-prove the complete analysis surface end to end and certify
Milestone 1 only if every remediation and formal-negative boundary holds.

**Required work.** Introduce no new grammar. Re-read the Q09–Q20 completion
records and extend the realistic workload corpus so it exercises ordered
multilevel grouping, legal set-operation modifiers and branch tails,
documented joins and SELECT tails, direct analyzer-safe AT-prefixed SELECT and
set-operation roots, legal plain/subordinate/recursive/hinted CTEs, and the
full temporary-table lifecycle. Add negative multi-statement scripts proving
unsupported query/CTE/CREATE/INSERT/INTO forms raise atomically at all four
parser error levels without swallowing the following statement or returning
empty SQL.

Strengthen the data-flow proof beyond Q08's supplied-schema boundary: trace a
column through SELECT INTO -> CTAS/CTE -> a definition-form temporary table
populated by INSERT -> the raw source query, with qualification, optimization,
scope traversal, and lineage all invoked on their ordinary public roots.
Assert statement boundaries, root classes, compact/pretty regeneration,
parse-after-generate equality, `dump()`/load, copy/transform parents, comments,
strict programmatic AST validation, and the applicable direct/nested foreign
generation contracts.

Re-audit every Milestone 1 coverage row and deliberate residual against the
committed tests. Update `docs/COVERAGE.md`, `docs/ROADMAP.md`,
`docs/ARCHITECTURE.md` where contracts changed, `CHANGELOG.md`, this Current
state section, dashboard/gate references, and installation-facing milestone
claims. Then run the complete common release gate: default tests with branch
coverage, every supported CPython minor including 3.15 warnings-as-errors,
lint/format/strict typing, sdist/wheel build, clean-wheel install and smoke,
repository-wide hooks, and diff hygiene. Record exact counts and versions.

If any product gap is found, do not fix it in this gate and do not certify the
milestone. Schedule a bounded Q task, renumber this gate to remain the highest
Q number, and stop after committing only the gate's in-scope test/docs work.
Milestone 2 becomes eligible only after the final recertification task is
`DONE` and its completion record expressly certifies Milestone 1.

**Explicit exclusions.** New grammar, Milestone 2 implementation, live-server
catalog semantics, and silent waiver of any failing or untested boundary.

**Primary sources.** Re-open every page named by Q09–Q20 as needed to verify
the final documented contract.

## Detailed tasks — Milestone 2: administration and remaining DDL (deferred)

Every Milestone 2 task is deferred until every Milestone 1 Q task is `DONE`;
Q21 is the current final gate. The detailed P16–P35
specifications — outcome, required work, exclusions, primary sources, and
completion records — are maintained verbatim in
[AGENT_TASK_PLAN_MILESTONE_2.md](AGENT_TASK_PLAN_MILESTONE_2.md); they are
not part of the mandatory read while Milestone 1 is active. When a P task is
selected, read its full specification there before implementing and append
its completion record there; status transitions stay in this file's
dashboard. Specifications, dependencies, and numbering are intentionally
unchanged from the prior plan revision; completion records and coverage
notes reference these IDs.
