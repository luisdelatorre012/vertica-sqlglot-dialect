# Sequential agent implementation plan

This is the executable backlog for continuing the coverage-driven Vertica
dialect. It is intentionally written for a capable **Sol Medium** agent working
one bounded slice at a time.

The architectural target remains OpenText Analytics Database 26.2, SQLGlot
30.13.x, and Python 3.9 through 3.15. `docs/COVERAGE.md` defines the public
coverage contract; this file defines implementation order.

## Copy-paste prompt

The repository-level `AGENTS.md` makes this prompt sufficient:

> Complete the next remaining task in the plan and update progress to mark this
> task as complete. Do not complete multiple tasks.

## Current state

- Completed through **P15 — Ordinary constraint conformance**.
- Next eligible tasks are selected by dependency and numeric order; P16 is the
  lowest-numbered remaining task.
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

## Status dashboard

Allowed states are `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`. At most one
task may be `IN_PROGRESS`.

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

1. Read this entire file, the selected task, `docs/ARCHITECTURE.md`, and the
   relevant rows in `docs/COVERAGE.md` and `docs/ROADMAP.md`.
2. If a task is `IN_PROGRESS`, resume it. Otherwise select the lowest-numbered
   `TODO` task whose dependencies are all `DONE`, change it to `IN_PROGRESS` in
   both the dashboard and its detail heading, and do no other task.
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
   scope; do not begin the next task.
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
- Recognized malformed Vertica syntax must raise `ParseError`; it must not fall
  back to `exp.Command`, truncate a tail, or emit a warning and partial AST at
  any `ErrorLevel`.
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
   diagnosing a failure.

8. Full tests on every installed supported runtime, CPython 3.9 through 3.15,
   plus the sdist/wheel build and clean installed-wheel smoke. Use the checked-in
   release driver, supplying one distinctive statement and expected root class:

   ```powershell
   ./scripts/release_gate.ps1 -TaskId pNN `
       -SmokeSql "TASK-DISTINCTIVE SQL" `
       -ExpectedClass "ExpectedExpressionClass"
   ```

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

## Detailed tasks

Completed task specifications and completion records for P01–P08 are archived
in [AGENT_TASK_PLAN_ARCHIVE.md](AGENT_TASK_PLAN_ARCHIVE.md). They are historical
context and are not part of the mandatory active-plan read.

### P09 — AUTHENTICATION SET security boundary — `DONE`

**Outcome.** Implement only a proved-safe non-secret parameter allowlist behind
a generalized secret firewall.

**Required work.** First audit every 26.2 parameter and classify it as safe,
secret-bearing, or catalog/unknown. Add pre-AST sanitized rejection for
`bind_password`, `client_secret`, and every unknown potentially sensitive name.
Only then add typed SET support for the reviewed non-secret allowlist. Reuse and
expand the USER sentinel harness across standard, escape, Unicode, national,
dollar, bit, hex, and tokenizer-fallback literal forms at all error levels.

**Stop condition.** If a complete safe allowlist cannot be established from
primary sources, mark this task `BLOCKED` with the audit and do not implement a
partial permissive parser.

**Primary sources.** [ALTER AUTHENTICATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-authentication/)
and [OAuth configuration](https://docs.vertica.com/26.2.x/en/security-and-authentication/client-authentication/oauth-2-0-authentication/configuring-oauth-authentication/).

**Completion record.** Audited the documented LDAP, Ident, Kerberos, and OAuth
parameter surfaces and added ordered typed SET support only for the two
non-secret parameters with closed 26.2 value domains: standard-string
`validate_type` (`IDP`/`JWT`) and `jit_enabled` (`yes`/`no`). Explicit
`bind_password`/`client_secret` values, every arbitrary or incompletely pinned
documented parameter, unknown future names, out-of-domain allowlisted values,
and standard, escape, Unicode, national, dollar, bit, hex, and raw-fallback
literal payloads fail through the fixed pre-AST sanitizer at every error level.
Serialization, copying, transformation, optimizer/type traversal, comments,
multi-statement boundaries, strict programmatic mutation, and direct/nested
foreign generation are covered. The source audit found one material scope
contradiction: ALTER AUTHENTICATION says SET is required for LDAP, Ident, and
OAuth, while the 26.2 Kerberos guide documents `SET REALM`; REALM remains
fail-closed because its arbitrary string domain can carry unreviewed payloads.
The OAuth parameter page labels `validate_hostname` Boolean without pinning
accepted SET spellings, so it also remains fail-closed rather than guessed.
Method compatibility, parameter combinations, record state, endpoints,
identities, roles/claims, and runtime authentication effects remain catalog or
server concerns. The default CPython 3.12.6 gate passed 3832 tests at 93.51%
branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15,
3.14.7, and 3.15.0rc1 suites each passed 3832 tests, with 3.15 treating
deprecations as errors. Ruff, formatting, strict mypy, sdist/wheel build, clean
force-install, `pip check`, and installed-wheel entry-point/SET round-trip smoke
passed.

### P10 — COMMENT ON family — `DONE`

**Outcome.** Make the complete documented COMMENT ON family semantic, including
comment removal with `NULL`.

**Required work.** Cover aggregate, analytic, scalar and transform functions,
column, constraint, library, node, projection, schema, sequence, table, and
view targets. Reuse typed routine signatures and qualified object nodes. Test
all target shapes, constraint-on-table and column ownership, quoted comments,
NULL removal, malformed signatures/targets, serialization, and a deliberate
foreign policy.

**Explicit exclusions.** Catalog ownership/existence and the server's comment
length/truncation behavior.

**Primary source.** [COMMENT ON statements](https://docs.vertica.com/26.2.x/en/sql-reference/statements/comment-on-statements/).

**Completion record.** Added an atomic `CommentOn` root for all 13 documented
target forms. Aggregate, analytic, scalar, and transform functions reuse typed
qualified `RoutineSignature` children; ordinary catalog objects use qualified
tables, columns preserve their database/schema/object ownership path, and a
dedicated constraint target retains both the constraint and owning table.
Standard-string comments and explicit `NULL` removal round-trip distinctly;
malformed target/signature/value shapes fail atomically at every error level,
and direct or nested foreign generation rejects the Vertica nodes. The 26.2
source consistently documents an 8192-character server limit with truncation
and a message, so length enforcement remains deliberately server-side along
with ownership and existence, as required by the task exclusion. The focused
suite passed 130 tests. The default CPython 3.12.6 gate passed 3964 tests at
93.48% branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13,
3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 3964 tests, with 3.15 treating
deprecations as errors. Ruff, formatting, strict mypy, sdist/wheel build, clean
force-install, `pip check`, and installed-wheel entry-point/COMMENT round-trip
smoke passed.

### P11 — VIEW lifecycle — `DONE`

**Outcome.** Complete typed ALTER/DROP VIEW around the existing semantic CREATE
VIEW implementation.

**Required work.** Implement documented owner, schema, and inherited-privilege
actions; equal-cardinality multi-view rename lists; and ordered multi-target
`DROP VIEW [IF EXISTS]`. Re-audit whether 26.2 permits dependency modifiers and
reject undocumented ones. Test qualified names, list cardinality, collision
with TABLE and local temporary views, CREATE interoperability, and foreign
atomicity.

**Primary sources.** [ALTER VIEW](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-view/)
and [DROP VIEW](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-view/).

**Completion record.** Added atomic `AlterView` and `DropViews` roots around
qualified, table-shaped names while retaining the existing canonical CREATE
VIEW tree. ALTER supports exactly one typed owner transfer, schema move,
INCLUDE/EXCLUDE/MATERIALIZE privilege action, or equal-cardinality ordered
multi-view rename; rename targets remain unqualified. DROP preserves an ordered
nonempty target list and postfix `IF EXISTS`. The re-opened 26.2 DROP syntax has
no dependency modifier, consistent with the view-management documentation, so
`CASCADE` and `RESTRICT` now fail closed rather than leaking through SQLGlot's
generic DROP grammar. Name existence, uniqueness, ownership, current-database
resolution, and dependency effects remain catalog/server checks. CREATE VIEW,
TABLE lifecycle, and local-temporary-view dispatch remain separate. The focused
schema/view suite passed 201 tests. The default CPython 3.12.6 gate passed 4149
tests at 93.43% branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15,
3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 4149 tests, with
3.15 treating deprecations as errors. Ruff, formatting, strict mypy,
sdist/wheel build, clean force-install, `pip check`, and installed-wheel
entry-point/ALTER VIEW round-trip smoke passed.

### P12 — SCHEMA lifecycle — `DONE`

**Outcome.** Complete typed ALTER/DROP SCHEMA while preserving the existing
CREATE SCHEMA extensions.

**Required work.** Support default include/exclude schema privileges, owner
transfer and documented cascade form, disk quota value/NULL reset, equal-length
multi-schema renames, and ordered multi-drop with exact cascade/restrict rules.
Test namespace/database qualification, quota shapes, action exclusivity,
existing CREATE behavior, and collisions with compound CREATE SCHEMA.

**Explicit exclusions.** Compound CREATE SCHEMA bodies remain separately
planned; catalog namespace resolution and dependency effects stay server-side.

**Primary sources.** [ALTER SCHEMA](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-schema/)
and [DROP SCHEMA](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-schema/).

**Completion record.** Added atomic `AlterSchema` and `DropSchemas` roots around
SQLGlot's canonical database-reference-shaped schema names while retaining the
existing canonical CREATE SCHEMA tree. ALTER supports exactly one typed default
INCLUDE/EXCLUDE SCHEMA PRIVILEGES action, owner transfer with optional object
CASCADE, quoted disk quota or `SET NULL` reset, or equal-cardinality ordered
multi-schema rename. The disk-quota guide pins accepted values to unsigned
integer strings with K/M/G/T units; units normalize to uppercase, zero and
arbitrarily large digits remain lexical, and signs, decimals, spaces, other
units, and nonstandard literal forms fail closed. Explicit source namespaces
must be preserved by corresponding rename targets. DROP preserves ordered
qualified targets, prefix `IF EXISTS`, and at most one postfix `CASCADE` or
explicit `RESTRICT`; omission retains the server's default restrictive policy.
Compound CREATE SCHEMA bodies remain separately planned and now fail atomically
at every error level. Namespace/database mode, current-database resolution,
ownership, object dependencies, quota relationships, and runtime effects remain
catalog/server checks. The re-opened 26.2 sources had no material contradiction;
the disk-quota guide clarifies the ALTER page's broad `value` placeholder. The
focused schema/view suite passed 442 tests. The default CPython 3.12.6 gate
passed 4396 tests at 93.36% branch coverage; isolated CPython 3.9.25, 3.10.20,
3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 4396 tests,
with 3.15 treating deprecations as errors. Ruff, formatting, strict mypy,
sdist/wheel build, clean force-install, `pip check`, and installed-wheel
entry-point/ALTER SCHEMA round-trip smoke passed.

### P13 — administrative privilege targets — `DONE`

**Outcome.** Close the named remaining GRANT/REVOKE target gaps without
regressing the current role, authentication, workload, resource-pool, routine,
location, and object forms.

**Required work.** Add official fixture matrices and exact privilege domains for
KEY, LIBRARY, DATA LOADER, and TLS CONFIGURATION. Audit existing factory-UDx
signature coverage before changing it. Enforce target-specific cardinality,
`EXTEND`, grant/admin option, cascade, qualification, and principal rules in
both parser and strict generator.

**Primary sources.** [GRANT DATA LOADER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/grant-statements/grant-data-loader/),
[GRANT KEY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/grant-statements/grant-key/),
[GRANT LIBRARY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/grant-statements/grant-library/),
and [GRANT TLS CONFIGURATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/grant-statements/grant-tls-config/).

**Completion record.** Added exact structured KEY, LIBRARY, DATA LOADER, and
TLS CONFIGURATION targets to the canonical GRANT/REVOKE roots, including
direction-specific privilege domains, target cardinality and qualification,
`ALL [PRIVILEGES]`, grant-option, `EXTEND`, cascade, principal, and 128-byte
identifier validation in both parser and strict generator. Single targets now
retain `VerticaPrivilegeTarget`, so direct and nested foreign generation fails
atomically instead of losing the Vertica object kind. The existing scalar,
aggregate, analytic, transform, filter, parser, and source UDx grant signatures
remain typed and unchanged. The re-opened 26.2 pages expose deliberate
directional asymmetries: TLS grants do not accept ALL although TLS revokes do;
LIBRARY grants accept DROP and optional ALL EXTEND while revokes accept only
USAGE or ALL; and only DATA LOADER and LIBRARY revokes accept CASCADE. These
formal syntax and parameter domains are enforced as documented. Ownership,
object existence, principal user/role type, current-database resolution, and
grant-chain effects remain catalog/server checks. The focused P13 suite passed
97 tests. The default CPython 3.12.6 gate passed 4493 tests at 93.13% branch
coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7,
and 3.15.0rc1 suites each passed 4493 tests, with 3.15 treating deprecations as
errors. Ruff, formatting, strict mypy, sdist/wheel build, clean force-install,
`pip check`, and installed-wheel entry-point/KEY GRANT round-trip smoke passed.

### P14 — access-policy lifecycle — `DONE`

**Outcome.** Add semantic CREATE/ALTER/DROP ACCESS POLICY roots with traversable
targets and expressions.

**Required work.** Model exact table/column targets, policy expression,
enable/disable, replacement and drop modifiers, and each documented ALTER
action. Prevent policy expressions from consuming trailing actions. Test
expression traversal/type/optimizer behavior, dispatch collisions, malformed
tails, serialization, and foreign atomicity.

**Explicit exclusions.** Catalog target types, ownership, policy expression
volatility, permissions, and runtime evaluation.

**Primary sources.** [CREATE ACCESS POLICY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-access-policy/),
[ALTER ACCESS POLICY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-access-policy/),
and [DROP ACCESS POLICY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-access-policy/).

**Completion record.** Added atomic `CreateAccessPolicy`, `AlterAccessPolicy`,
and `DropAccessPolicy` roots around a shared row/column `AccessPolicyTarget`,
with traversable policy expressions, explicit trust/state fields, a distinct
COPY destination, exact table qualification, strict 128-byte identifier
validation, serialization, optimizer/type traversal, and direct/nested atomic
foreign failure. The parser prevents policy expressions from consuming
trailing actions and rejects malformed tails, statement modifiers, quoted or
non-ASCII compound object keywords, invalid expression shapes, and malformed
programmatic nodes across strict parser/generator modes. Re-opened 26.2 sources
contain two material conflicts: the ALTER prose/examples omit `GRANT TRUSTED`
although the formal grammar requires it, and the management guide shows a
schema-qualified COPY destination although the formal ALTER and DROP grammars
use unqualified table targets. Per the plan's source policy, the formal grammar
is enforced; catalog target type/existence, ownership, permissions, expression
volatility and UDTF behavior, and runtime evaluation remain server checks. The
focused P14 suite passed 169 tests. The default CPython 3.12.6 gate passed 4666
tests at 93.16% branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15,
3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 4666 tests, with
3.15 treating deprecations as errors. Ruff, formatting, strict mypy,
sdist/wheel build, clean force-install, `pip check`, and installed-wheel
entry-point/CREATE ACCESS POLICY round-trip smoke passed.

### P15 — ordinary constraint conformance — `DONE`

**Outcome.** Turn the current Generic ordinary column/table constraint row into
a documented Vertica contract, using canonical SQLGlot nodes wherever exact.

**Required work.** Audit every 26.2 column/table constraint and current SQLGlot
parse/generate behavior. Add a broad official positive corpus and deterministic
Vertica negative restrictions for definition-form tables, CTAS/LIKE/temp/flex
contexts, names, defaults, references, check expressions, and clause order.
Only add custom nodes for demonstrable information loss. Update the coverage
row to Semantic or Partial with named residuals.

**Explicit exclusions.** Referential existence, type compatibility, uniqueness,
volatility, enforcement state, and dependency checks.

**Primary sources.** The [CREATE TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-table/)
subpages for column definitions, column constraints, and table constraints.

**Completion record.** Re-audited the column-definition, column-constraint,
table-constraint, and admin constraints-guide pages against current canonical
SQLGlot behavior. The prior "Generic" status understated both gaps and
un-Vertica-documented Postgres leakage: `ENABLED`/`DISABLED` enforcement on
`PRIMARY KEY`/`UNIQUE`/`CHECK`, `SET USING`, and `DEFAULT USING` did not parse
at all; `AUTO_INCREMENT`/`IDENTITY` silently dropped its cache-size argument
and generated Postgres's unrelated `GENERATED ... AS IDENTITY` syntax; and the
inherited Postgres grammar accepted undocumented `ON DELETE`/`UPDATE`,
`MATCH`, `DEFERRABLE`, `INCLUDE`, `GENERATED AS IDENTITY`, `CHARACTER SET`,
`COLLATE`, `COMMENT`, `EXCLUDE`, `PERIOD`, multi-kind named table constraints,
and interleaved column-definition/table-constraint order. `CONSTRAINT_PARSERS`
is now an explicit allowlist (not spread from Postgres); every other inherited
keyword fails through a natural leftover-token `ParseError`. New
`VerticaIdentityColumnConstraint`, `SetUsingColumnConstraint`, and
`DefaultUsingColumnConstraint` nodes model syntax with no canonical
equivalent. `PRIMARY KEY`/`UNIQUE`/`CHECK` reuse their canonical nodes when no
enforcement marker is written, keeping bare constraints portable to foreign
dialects, and switch to detached (not subclassed) `VerticaPrimaryKeyColumnConstraint`/
`VerticaUniqueColumnConstraint`/`VerticaPrimaryKey`/`VerticaCheckColumnConstraint`
nodes once a marker is present; testing proved detachment necessary; because
the canonical `CheckColumnConstraint.enforced` field already means MySQL
`ENFORCED`, and because SQLite's generator structurally rewrites plain
`exp.PrimaryKey` by `isinstance` before per-node dispatch, a subclass let a
foreign generator reinterpret or silently drop Vertica's marker instead of
failing atomically — a real, demonstrated leak, not a hypothetical one. Table-
constraint dispatch is now an exclusive one-of-four parser; column-level
`CONSTRAINT` naming is restricted to `CHECK`/`PRIMARY KEY`/`REFERENCES`/`UNIQUE`;
column-level `REFERENCES` is capped at one column. A same-statement pass
enforces column-definitions-before-table-constraints order, single
`PRIMARY KEY`/`AUTO_INCREMENT`/`IDENTITY` cardinality, temporary-table
exclusion of `AUTO_INCREMENT`/`IDENTITY`, `DEFAULT`/`SET USING`
non-repetition and `DEFAULT USING` exclusivity, and the documented
single-SELECT-statement/temporary-table-subquery limits on `DEFAULT`/
`SET USING`/`DEFAULT USING`. Proving these restrictions at every `ErrorLevel`
surfaced a latent, pre-existing defect: the CREATE TABLE definition/CTAS/LIKE
dispatch called the plain, level-dependent `raise_error` immediately before an
`assert ... is not None`, so at `RAISE`/`WARN`/`IGNORE` several negatives could
reach the assert without having raised and crash with `AssertionError` instead
of `ParseError`; every call site in that dispatch now uses the same
guaranteed-raise wrapper already established for other statement families.
The re-opened 26.2 column-constraint page's own formal grammar has an internal
inconsistency: the `PRIMARY KEY`/`REFERENCES` alternative is missing the `|`
that separates every other alternative in the same production, unlike the
table-constraint page's clean four-way alternation; per the plan's source
policy this is recorded rather than resolved by guessing, and `PRIMARY KEY`
and `REFERENCES` are parsed as separate, independently optional pieces,
consistent with the surrounding prose and every worked example. CHECK
expression content restrictions (subqueries, aggregates, window functions,
meta-functions, epoch-column/other-table references) and its Boolean-return
requirement remain a named server-side residual per the task's own exclusions,
along with referential existence, type compatibility (including
collection-typed key columns), same-database name uniqueness, unspecified
enforcement state, and dependency effects. Native flex-table definition
parsing is unaffected and remains an opaque `Command` pending P16. The focused
P15 suite passed 188 tests. The default CPython 3.12.6 gate passed 4861 tests
at 93.24% branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13,
3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 4861 tests, with 3.15
treating deprecations as errors. Ruff, formatting, strict mypy, sdist/wheel
build, clean force-install, `pip check`, and installed-wheel entry-point/
CREATE TABLE constraint round-trip smoke passed.

### P16 — native flexible-table definition form — `TODO`

**Outcome.** Add semantic non-external, non-CTAS `CREATE FLEX[IBLE] TABLE` with
an honest flex-specific AST contract.

**Required work.** Support persistent definition-form tables with optional
materialized columns, mandatory/empty parentheses as documented, implicit
`__raw__`/`__identity__` semantics without inventing AST columns, physical
design clauses allowed by 26.2, privileges, and exact IF NOT EXISTS behavior.
Reuse ordinary table nodes but keep a typed flex marker/root so foreign dialects
cannot silently emit a regular table. Test FLEX/FLEXIBLE normalization, quoted
collisions, constraints, column types, physical clauses, and external-flex
dispatch regressions.

**Explicit exclusions.** Temporary flex forms (documentation order conflict),
CTAS (P17), external flex (already semantic), and catalog-generated projections.

**Primary sources.** [CREATE FLEXIBLE TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-flexible-table/)
and [Creating flex tables](https://docs.vertica.com/26.2.x/en/flex-tables/creating-flex-tables/).

**Completion record.** Pending.

### P17 — flexible-table CTAS — `TODO`

**Outcome.** Add the persistent `CREATE FLEX[IBLE] TABLE ... AS query` form as a
separate bounded slice after P16.

**Required work.** Model schema privileges, query, trailing quota, and the three
materialization states described by 26.2: omitted parentheses materialize all
result columns, `()` materializes none, and a name list materializes that named
prefix. Keep the source query traversable. Reject typed column definitions and
`ENCODED BY` in CTAS. Test all three parenthesis states, queries with and without
`__raw__`, matching names, CTEs, hints, comments, quota placement,
serialization, optimizer traversal, and foreign failure.

**Explicit exclusions.** Temporary flex CTAS until the documented modifier-order
conflict is validated against a 26.2 server; external flex remains unchanged.

**Primary source.** The CREATE FLEXIBLE TABLE page and flex guide linked in P16.

**Completion record.** Pending.

### P18 — flex map transform core — `TODO`

**Outcome.** Give the four source-sensitive flex transform functions stable
semantic contracts without over-modeling scalar VMAP functions.

**Required work.** Model `MAPAGGREGATE(keys, values ...) OVER (...)`,
`MAPITEMS(vmap [, passthrough ...]) OVER (...)`, `MAPKEYS(vmap ...) OVER (...)`,
and `MAPVALUES(vmap ...) OVER (...)`, including ordered `USING PARAMETERS`.
Require an OVER clause but do not require one specific partition mode: the 26.2
MAPKEYS prose and examples conflict on `PARTITION BEST` versus `OVER()`.
Preserve passthrough arguments, source-sensitive spellings, result types, and
optimizer traversal. Test missing/detached OVER, nested calls, parameter
names/order/duplicates/enums/ranges, quoted function provenance, malformed
programmatic nodes, and atomic foreign failure.

**Explicit exclusions.** Other scalar map functions, flex data/extractor
functions, catalog key inference, data scans, and generated view/column validity.

**Primary sources.** The [Flex map function index](https://docs.vertica.com/26.2.x/en/sql-reference/functions/flex-functions/flex-map-functions/)
and its MAPAGGREGATE, MAPITEMS, MAPKEYS, and MAPVALUES pages.

**Completion record.** Pending.

### P19 — ALTER LIBRARY — `TODO`

**Outcome.** Complete the existing semantic CREATE/DROP LIBRARY family with its
documented replacement statement.

**Required work.** Implement exact `ALTER LIBRARY` name, optional dependency
path, and replacement path order while reusing existing catalog-name and
library-path validation. Test local/cloud-looking opaque paths, omitted
dependencies, duplicates/order errors, create/drop interoperability, strict AST
mutations, serialization, and foreign atomicity.

**Explicit exclusions.** Filesystem access, binary/SDK compatibility, dependency
loading, UDx invalidation, and undocumented language changes.

**Primary source.** [ALTER LIBRARY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-library/).

**Completion record.** Pending.

### P20 — common factory-backed UDx metadata ALTER — `TODO`

**Outcome.** Add a shared typed ALTER layer for the already-semantic bodyless UDx
catalog families.

**Required work.** Cover scalar, aggregate, analytic, transform, filter, parser,
and source signatures with the three common metadata actions: owner, rename,
and schema. Reuse `RoutineSignature`; require parentheses and exactly one typed
action. Test empty/named/typed overload signatures, every kind/action pair,
CREATE/DROP interoperability, kind/action keyword provenance, and collision
with PostgreSQL/SQL-function ALTER syntax.

**Explicit exclusions.** `SET FENCED` requires a later per-kind matrix because
aggregate and SQL functions differ; also exclude SQL-expression function
bodies, stored procedures, catalog overload resolution, and runtime language/
fence compatibility.

**Primary source.** [ALTER FUNCTION statement family](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-function-statements/).

**Completion record.** Pending.

### P21 — partition-maintenance completion — `TODO`

**Outcome.** Replace the deliberate fail-closed boundary for comma-separated
ALTER TABLE actions with a structured multi-action model.

**Required work.** Support documented mixes containing partition definition,
grouping, active partition count, and REORGANIZE alongside other supported ALTER
actions. Preserve action order, commas inside expressions, and the distinction
between metadata-only partition change and physical reorganization. Add an
official regression corpus for MOVE/SWAP/COPY/DROP partition management
functions that already parse as canonical SELECT calls; do not add custom nodes
without a demonstrated semantic loss. Correct any stale roadmap wording.

**Explicit exclusions.** Catalog partition existence/state, tuple-mover effects,
locks, and unsupported archive operations.

**Primary sources.** [ALTER TABLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-table/)
and [partition functions](https://docs.vertica.com/26.2.x/en/sql-reference/functions/management-functions/partition-functions/).

**Completion record.** Pending.

### P22 — routine-body parsing foundation — `TODO`

**Outcome.** Establish lossless statement-boundary handling for Vertica routine
bodies before adding stored or SQL-expression routines.

**Required work.** Audit exact 26.2 delimiter rules and add a focused tokenizer/
parser representation for the documented untagged `$$...$$` body. Preserve body
text opaquely, including internal semicolons/comments/quotes, and prove correct
multi-statement chunking. Reject tagged dollar delimiters unless a 26.2 primary
source explicitly documents them. Add mutation, serialization, comment,
delimiter-collision, malformed/unclosed-body, and cross-version tests.

**Explicit exclusions.** Do not parse PL/vSQL internals, create procedures, or
create SQL functions in this task. The result is infrastructure and fixtures
only.

**Primary sources.** [CREATE PROCEDURE (stored)](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-procedure-stored/)
and [CREATE FUNCTION (SQL)](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-function-statements/create-function-sql/).

**Completion record.** Pending.

### P23 — stored-procedure CREATE shell — `TODO`

**Outcome.** Add semantic stored-procedure creation using the opaque body
foundation, without colliding with the existing external-procedure AST.

**Required work.** Implement `CREATE [OR REPLACE] PROCEDURE [IF NOT EXISTS]
qualified-name([mode name type, ...]) [LANGUAGE 'PLvSQL'|'PLpgSQL'] [SECURITY
DEFINER|INVOKER] AS $$ source $$` after confirming exact 26.2 spellings. Use
canonical typed signature/options plus one opaque heredoc/body child. Enforce
allowed modes/types, modifier conflicts, exact Vertica SECURITY spelling, and
clause order. Test internal semicolons/comments/DDL-looking text, malformed or
unterminated delimiters, external-procedure dispatch, serialization, and atomic
foreign failure.

**Explicit exclusions.** DROP (P24), CALL, DO, triggers, ALTER PROCEDURE,
PL/vSQL semantic parsing, execution validation, tagged dollar delimiters, and
SQL-expression functions (P34).

**Primary source.** [CREATE PROCEDURE (stored)](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-procedure-stored/).

**Completion record.** Pending.

### P24 — stored/external procedure DROP discrimination — `TODO`

**Outcome.** Parse stored-procedure DROP independently from the already-semantic
external-procedure DROP grammar.

**Required work.** Implement `DROP PROCEDURE [IF EXISTS]
qualified-name([parameter-type-list]) [CASCADE]` using an atomic stored root or
an explicitly discriminated procedure root. Preserve empty/typed signatures,
exact modifier placement, and catalog qualification. Test stored versus
external signatures, CASCADE, missing/invalid types, named parameters where
forbidden, dump/load, strict malformed ASTs, and atomic foreign failure.

**Explicit exclusions.** CREATE is P23. Do not change external CREATE PROCEDURE,
CALL, DO, ALTER PROCEDURE, or routine-body parsing.

**Primary source.** [DROP PROCEDURE (stored)](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-procedure-stored/).

**Completion record.** Pending.

### P25 — fault-group lifecycle — `TODO`

**Outcome.** Add typed CREATE/ALTER/DROP FAULT GROUP as one bounded cluster-admin
family.

**Required work.** Re-audit exact parent/member/create options and each ALTER
action, using load-balance-group member and identifier policies where exact.
Require one action, exact modifiers, safe identifiers, serialization, and
foreign atomicity. Add collisions with load-balance groups, nodes, tables, and
identifiers named FAULT/GROUP.

**Explicit exclusions.** Topology existence, parent/child cycles, spread state,
membership compatibility, permissions, and runtime rebalancing.

**Primary sources.** [CREATE FAULT GROUP](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-fault-group/),
[ALTER FAULT GROUP](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-fault-group/),
and [DROP FAULT GROUP](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-fault-group/).

**Completion record.** Pending.

### P26 — node administration — `TODO`

**Outcome.** Add typed ALTER NODE actions only, retaining unrelated management
functions under their existing contracts.

**Required work.** Re-audit each 26.2 ALTER NODE action and model it as a typed,
single-action root with exact keyword provenance and identifier/address values.
Test NODE keyword collisions, fault-group/network-address references, modifiers,
action exclusivity, huge numeric values if present, serialization, and foreign
failure.

**Explicit exclusions.** Cluster startup/shutdown functions, node existence,
cluster/spread state, transaction legality, topology effects, and host access.

**Primary source.** [ALTER NODE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-node/).

**Completion record.** Pending.

### P27 — standard namespace lifecycle — `TODO`

**Outcome.** Add semantic standard Eon `CREATE/DROP NAMESPACE` without absorbing
credential-adjacent Iceberg namespace syntax.

**Required work.** Implement `CREATE NAMESPACE name [SHARD COUNT unsigned]` and
`DROP NAMESPACE [IF EXISTS] name` with lexical huge-number validation, exact
keyword provenance, strict identifiers, modifier negatives, serialization, and
foreign atomicity. Preserve neighboring schema/database/table qualification.

**Explicit exclusions.** CREATE/ALTER ICEBERG NAMESPACE, especially REST_AUTH;
namespace catalog existence; cloud credentials; and undocumented dependency
modifiers. Recognized Iceberg namespace forms need a separate security audit.

**Primary sources.** [CREATE NAMESPACE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-namespace/)
and [DROP NAMESPACE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-namespace/).

**Completion record.** Pending.

### P28 — Eon subnet lifecycle — `TODO`

**Outcome.** Add typed CREATE/ALTER/DROP SUBNET as an isolated compound-object
family.

**Required work.** Re-audit exact CIDR/address and action grammar, keep addresses
opaque when the server accepts host/network forms, and use network-address
identifier/provenance helpers only where contracts match. Test partial compound
keywords, quoted lookalikes, prefixes, huge values, serialization, neighboring
SUBCLUSTER/subquery identifiers, and foreign failure.

**Explicit exclusions.** CIDR validity, cloud topology, overlap, node ownership,
reachability, permissions, and catalog state.

**Primary sources.** [CREATE SUBNET](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-subnet/),
[ALTER SUBNET](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-subnet/),
and [DROP SUBNET](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-subnet/).

**Completion record.** Pending.

### P29 — Eon subcluster alterations — `TODO`

**Outcome.** Add semantic ALTER SUBCLUSTER SQL while preserving current typed
subcluster selectors in pools, routing, users, and load balancing.

**Required work.** Re-audit every documented action, model exactly one typed
action, and share identifier/selectors only where shape and meaning match.
Test action order/exclusivity, current/named selector collisions, quoted names,
serialization, existing consumer regressions, and atomic foreign failure.

**Explicit exclusions.** Management functions for create/drop/scale unless an
audit demonstrates semantic loss, node membership, control-subcluster rules,
running state, and Eon catalog checks.

**Primary source.** [ALTER SUBCLUSTER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-subcluster/).

**Completion record.** Pending.

### P30 — storage-location administration — `TODO`

**Outcome.** Add semantic CREATE LOCATION and exact typed contracts for the
location-management operations that are currently generic function calls.

**Required work.** Model CREATE LOCATION's ordered path/node/usage/label clauses.
Audit `ALTER_LOCATION_LABEL`, `ALTER_LOCATION_USE`, and `DROP_LOCATION`: retain
canonical functions if lossless, otherwise use thin typed wrappers with exact
spellings and result types. Test paths as opaque strings, node/usage enums,
duplicate/order negatives, existing LOCATION grants, and foreign policy.

**Explicit exclusions.** Storage-policy management, filesystem/cloud access,
path existence, shared-storage semantics, object placement, and node state.

**Primary sources.** [CREATE LOCATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-location/),
[ALTER_LOCATION_USE](https://docs.vertica.com/26.2.x/en/sql-reference/functions/management-functions/storage-functions/alter-location-use/),
and [DROP_LOCATION](https://docs.vertica.com/26.2.x/en/sql-reference/functions/management-functions/storage-functions/drop-location/).

**Completion record.** Pending.

### P31 — archive lifecycle — `TODO`

**Outcome.** Add typed CREATE/ALTER/DROP ARCHIVE only.

**Required work.** Implement `CREATE ARCHIVE name [LIMIT unsigned]`, exactly one
ALTER action (`OWNER TO owner` or `LIMIT unsigned`), and `DROP ARCHIVE name
[CASCADE]`. Use lexical huge-number validation and leave undocumented limit
ranges server-side. Test identifiers equal to LIMIT/OWNER/CASCADE, clause order,
duplicates, action exclusivity, negative/decimal/string/huge limits, unsupported
IF EXISTS, malformed flags/containers, serialization, and atomic foreign
failure.

**Explicit exclusions.** SAVE/REMOVE/RESTORE POINT and REPLICATE operations,
archive existence/ownership, retention effects, and server state.
The REMOVE RESTORE POINT documentation has known selector/ordering conflicts;
do not implement it without a 26.2 server fixture.

**Primary sources.** [CREATE ARCHIVE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-archive/),
[ALTER ARCHIVE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-archive/),
and [DROP ARCHIVE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-archive/).

**Completion record.** Pending.

### P32 — TLS-configuration lifecycle — `TODO`

**Outcome.** Add typed CREATE/ALTER/DROP TLS CONFIGURATION, treating certificate
and key names as catalog references rather than secret material.

**Required work.** Model certificate references, ordered CA additions/removals,
cipher-suite strings, finite TLS modes, owner/action clauses, exact dependency
modifiers, and their kind-specific conflicts. Test empty cipher sentinel,
duplicate/reordered clauses, grants from P13, serialization, and foreign
atomicity.

**Explicit exclusions.** Certificate/private-key contents, passphrases, PEM data,
cryptographic validation, catalog existence, and runtime TLS negotiation.

**Primary sources.** [CREATE TLS CONFIGURATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-tls-config/),
[ALTER TLS CONFIGURATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-tls-config/),
and [DROP TLS CONFIGURATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-tls-config/).

**Completion record.** Pending.

### P33 — non-secret cryptographic-object core — `TODO`

**Outcome.** Perform a security review, then implement only generation/reference
forms of KEY, CERTIFICATE, and CA BUNDLE proven not to carry private material.

**Required work.** Classify every CREATE/ALTER/DROP branch as generated/reference
only or secret/import bearing. Implement typed roots only for the safe subset.
Add pre-AST sanitized rejection for private keys, passphrases, imported PEM, and
unknown secret-capable branches. Extend sentinel tests to long, dollar,
Unicode, escape, national, raw-fallback, bit, and hex literal token forms across
all error/log channels. Test lifecycle options, privilege integration,
serialization, and atomic foreign failure.

**Stop condition.** If primary sources cannot prove a branch contains no secret
material, leave it fail-closed and record it as excluded. Lossless round-trip is
never more important than preventing credential/key disclosure.

**Primary sources.** [CREATE KEY](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-key/),
[CREATE CERTIFICATE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-certificate/),
and [CREATE CA BUNDLE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-ca-bundle/),
plus their 26.2 ALTER/DROP pages.

**Completion record.** Pending.

### P34 — SQL-expression function lifecycle — `TODO`

**Outcome.** Add semantic SQL-function CREATE/ALTER/DROP without capturing the
factory-backed UDx family.

**Required work.** Use typed signatures/return types/options and the P22 body
container for `BEGIN RETURN ...; END`. Re-audit exact overload/drop grammar,
volatility/security/fence clauses, and ALTER actions. Test internal semicolon
chunking, zero/multiple arguments, type restrictions, P20 factory-dispatch
boundaries, serialization, and foreign atomicity.

**Explicit exclusions.** PL/vSQL procedures, factory UDx registration, catalog
overload resolution, and executing/type-checking the function body.

**Primary source.** [CREATE FUNCTION statements](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-function-statements/)
and the corresponding 26.2 ALTER/DROP SQL-function pages.

**Completion record.** Pending.

### P35 — coverage audit and queue refresh — `TODO`

**Outcome.** Reconcile the finished implementation with the complete 26.2 SQL
index and append the next bounded queue. This is a docs/test-planning task, not a
feature grab bag.

**Required work.** Probe every remaining Preserved/Partial/Planned coverage row
and the 26.2 statement index. Correct stale descriptions where canonical
SQLGlot already provides an exact traversable AST. Add new task entries with one
grammar family, dependencies, explicit exclusions, primary sources, specialized
tests, and a commit title. Candidate families include compound CREATE SCHEMA,
temporary flex-table forms after a server fixture, restore points, DATA LOADER,
notifier/schedule/trigger, database alterations, text indexes, storage policies,
and deterministic TIMESERIES/MATCH/INTERPOLATE restrictions.

**Rules.** Do not implement any candidate feature in P35. Do not mark a family
Semantic from a round-trip string alone; require AST and negative-contract
evidence. Reset the dashboard so the first newly appended task is the only next
`TODO` item after P35 becomes `DONE`.

**Primary source.** [OpenText Analytics Database 26.2 SQL reference](https://docs.vertica.com/26.2.x/en/sql-reference/).

**Completion record.** Pending.
