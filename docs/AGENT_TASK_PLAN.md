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

- Completed through **P02 — executable PROFILE statement**.
- Next eligible tasks are selected by dependency and numeric order; P03 is the
  lowest-numbered remaining task.
- There is intentionally no Git remote. Make local commits only; never push.

## Status dashboard

Allowed states are `TODO`, `IN_PROGRESS`, `DONE`, and `BLOCKED`. At most one
task may be `IN_PROGRESS`.

| ID | Status | Task | Required dependency | Commit title |
| --- | --- | --- | --- | --- |
| P01 | DONE | PROFILE lifecycle | `6ca2a0d` | `feat: model profile lifecycle` |
| P02 | DONE | Executable `PROFILE` statement | P01 | `feat: model profiled statement execution` |
| P03 | TODO | USER profile and resource-pool assignments | P01 | `feat: add user workload assignments` |
| P04 | TODO | USER time and capacity limits | P03 | `feat: model non-secret user limits` |
| P05 | TODO | USER search path and default roles | P03 | `feat: model user path and default roles` |
| P06 | TODO | Safe USER configuration/reset actions | P04, P05 | `feat: model safe user configuration actions` |
| P07 | TODO | AUTHENTICATION create/drop core | P06 | `feat: model authentication creation and drop` |
| P08 | TODO | AUTHENTICATION structural ALTER actions | P07 | `feat: model authentication alter actions` |
| P09 | TODO | AUTHENTICATION SET security boundary | P08 | `feat: add safe authentication parameters` |
| P10 | TODO | COMMENT ON family | P02 | `feat: make Vertica comment statements semantic` |
| P11 | TODO | VIEW lifecycle | P10 | `feat: complete semantic view lifecycle` |
| P12 | TODO | SCHEMA lifecycle | P11 | `feat: complete semantic schema lifecycle` |
| P13 | TODO | Administrative privilege targets | P09 | `feat: complete administrative privilege targets` |
| P14 | TODO | Access-policy lifecycle | P13 | `feat: model access policy lifecycle` |
| P15 | TODO | Ordinary constraint conformance | P12 | `feat: enforce Vertica constraint grammar` |
| P16 | TODO | Native flexible-table definition form | P15 | `feat: model native flexible table definitions` |
| P17 | TODO | Flexible-table CTAS | P16 | `feat: model flexible table ctas` |
| P18 | TODO | Flex map transform core | P16 | `feat: model flex map transforms` |
| P19 | TODO | ALTER LIBRARY | P10 | `feat: model library alterations` |
| P20 | TODO | Common factory-backed UDx metadata ALTER | P19 | `feat: model factory udx alterations` |
| P21 | TODO | Partition-maintenance completion | P12 | `feat: complete partition maintenance actions` |
| P22 | TODO | Routine-body parsing foundation | P20 | `feat: add routine body parsing foundation` |
| P23 | TODO | Stored-procedure CREATE shell | P22 | `feat: model stored procedure creation shells` |
| P24 | TODO | Stored/external procedure DROP discrimination | P23 | `feat: distinguish stored and external procedure drops` |
| P25 | TODO | Fault-group lifecycle | P14 | `feat: model fault group lifecycle` |
| P26 | TODO | Node administration | P25 | `feat: model node alterations` |
| P27 | TODO | Standard namespace lifecycle | P16 | `feat: model namespace lifecycle` |
| P28 | TODO | Eon subnet lifecycle | P27 | `feat: model subnet lifecycle` |
| P29 | TODO | Eon subcluster alterations | P28 | `feat: model subcluster alterations` |
| P30 | TODO | Storage-location administration | P29 | `feat: model storage location administration` |
| P31 | TODO | Archive lifecycle | P30 | `feat: model archive lifecycle` |
| P32 | TODO | TLS-configuration lifecycle | P13 | `feat: model tls configuration lifecycle` |
| P33 | TODO | Non-secret cryptographic-object core | P32 | `feat: add non-secret cryptographic object core` |
| P34 | TODO | SQL-expression function lifecycle | P22, P24 | `feat: model sql function lifecycle` |
| P35 | TODO | Coverage audit and queue refresh | P01–P34 | `docs: refresh remaining sql coverage backlog` |

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
   do not resolve it by guessing server behavior.
5. Implement only the stated scope. Explicit exclusions must either retain their
   already-documented behavior or fail closed when they are recognized members
   of the newly semantic family.
6. Run the common release gate and all task-specific tests. Fix failures within
   scope; do not begin the next task.
7. Update the coverage matrix, roadmap, sources, architecture, and changelog as
   applicable. Change this task to `DONE`, update the dashboard, and add a short
   completion record with test counts and any deliberate boundary.
8. Run the versioned pre-commit suite over the entire repository. If a fixer
   changes files, inspect the diff, restage only task files, rerun affected tests
   and the hook suite, and do not proceed until it is clean.
9. Stage only the selected task and its plan/status updates. Commit locally with
   the exact listed title so the installed code-quality and commit-message hooks
   execute. Never use `--no-verify`, `SKIP`, or another hook bypass. Stop
   immediately after the commit.
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
7. Full default-runtime suite with branch coverage at or above 90%:

   ```console
   .venv/Scripts/python -m pre_commit run --all-files --show-diff-on-failure
   .venv/Scripts/python -m pytest --cov
   .venv/Scripts/python -m ruff check .
   .venv/Scripts/python -m ruff format --check .
   .venv/Scripts/python -m mypy src
   git diff --check
   ```

8. Full tests on the available CPython 3.14 and 3.15 runtimes; run 3.15 with
   `-W error::DeprecationWarning`. If an expected local runtime is unavailable,
   record that fact and run the closest available prerelease—do not claim it ran.
9. Build sdist/wheel without isolation when the sandbox cannot download build
   dependencies. Force-install the exact new wheel into a clean `.wheel-venv`,
   run `pip check`, and use `python -I` to verify entry-point discovery plus one
   distinctive AST/round-trip smoke from this task.

## Detailed tasks

### P01 — PROFILE lifecycle — `DONE`

**Outcome.** Finish the already-started semantic CREATE/ALTER/DROP PROFILE
family. No unrelated slice may land first because the current dispatch calls
undefined methods.

**Required work.**

- Preserve and complete `ProfileParameter`, `ProfileLimit`, `CreateProfile`,
  `AlterProfile`, and `DropProfiles`.
- Implement exactly:
  - `CREATE PROFILE name LIMIT parameter value [parameter value ...]`
  - `ALTER PROFILE name LIMIT parameter value [parameter value ...]`
  - `ALTER PROFILE name RENAME TO new_name`
  - `DROP PROFILE [IF EXISTS] name[, ...] [CASCADE]`
- Support all 15 names already listed in `VerticaParser.PROFILE_PARAMETERS`.
  Preserve order, require a nonempty list, and reject case-insensitive duplicates.
- Support numeric values and `UNLIMITED` for CREATE/ALTER. Support explicit
  `DEFAULT` only as an ALTER reset; reject explicit CREATE defaults.
- Enforce documented per-setting domains lexically, including
  `PASSWORD_MAX_LENGTH` 8–512 and the positive/nonnegative groups. Reject only
  decidable minimum-setting values above an explicit numeric max in the same
  list; inherited/catalog relationships remain server checks.
- `ALTER PROFILE DEFAULT LIMIT ...` is valid. Reject quoted or unquoted DEFAULT
  as CREATE name, DROP target, or rename source/destination.
- Reuse the USER-era unqualified identifier, tokenizer-parity, 128-byte UTF-8,
  surrogate, huge-number, and strict-generation policies.
- Add generator methods/transforms with mirrored invariants. Rendering must stop
  after `unsupported()`; never render a known-invalid child.
- Add `tests/test_profiles.py` covering every parameter/value class, rename,
  multi-drop, DEFAULT rules, duplicates, commas, empty/unknown/signed/decimal/
  string/out-of-range values, explicit-max conflicts, modifiers, keyword
  provenance, identifiers, malformed ASTs, serialization, optimizer/type
  stability, foreign failure, comments, and all error levels.
- Update all five project docs and the changelog. State that PROFILE settings are
  policy metadata, not passwords; assignments, inheritance effects, ownership,
  and current-password effects are catalog/server concerns.

**Explicit exclusions.** USER `PROFILE` assignment and executable top-level
`PROFILE` are P03 and P02. Do not implement either here.

**Primary sources.** [CREATE PROFILE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-profile/),
[ALTER PROFILE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-profile/),
[ALTER PROFILE RENAME](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-profile-rename/),
[DROP PROFILE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-profile/),
and the [Profiles guide](https://docs.vertica.com/26.2.x/en/security-and-authentication/client-authentication/hash-authentication/passwords/profiles/).

**Completion record.** Added typed CREATE/ALTER/DROP PROFILE roots and ordered
limit/parameter children for all 15 policy settings, including lexical value
domains, ALTER-only DEFAULT resets, rename, multi-drop, identifier parity,
serialization/optimizer/type stability, and atomic foreign failure. The 26.2
source re-audit found no material grammar contradiction. PROFILE values are
policy metadata, not passwords; USER assignment, ownership, inheritance and
current-password effects remain catalog/server concerns, and executable
top-level PROFILE remains P02. The default CPython 3.12.6 gate passed 2633 tests
at 93.76% branch coverage; Ruff, formatting, strict mypy, full pre-commit,
sdist/wheel build, clean force-install, `pip check`, and isolated installed-wheel
smoke passed. CPython 3.14 and 3.15 were not available locally (`py -0p` exposed
only 3.12), so those runtime suites were not claimed.

### P02 — executable `PROFILE` statement — `DONE`

**Outcome.** Add one custom wrapper with a traversable statement child for
`PROFILE {sql-statement}`.

**Required work.** Accept the documented SELECT and DML/COPY/MERGE statement
families, retain hints/comments and semicolon ownership, reject empty bodies,
DDL, transaction control, and nested PROFILE, and keep lifecycle PROFILE
dispatch collision-free. Test every accepted root, multi-statements,
serialization/optimizer traversal, and atomic foreign failure.

**Primary source.** [PROFILE](https://docs.vertica.com/26.2.x/en/sql-reference/statements/profile/).

**Completion record.** Added an atomic `ProfileStatement` wrapper around one
traversable SELECT/set-operation, INSERT, UPDATE, DELETE, Vertica COPY, or MERGE
child. Hints/comments, serialization, optimizer/type traversal, parent links,
and batch/semicolon ownership are preserved; empty, VALUES-only, malformed,
DDL, transaction-control, and nested PROFILE bodies fail closed at every error
level, and foreign generation is atomic. The 26.2 source re-audit found no
material contradiction; execution output and catalog writes remain Vertica
runtime effects. The default CPython 3.12.6 gate passed 2769 tests at 93.82%
branch coverage; Ruff, formatting, strict mypy, full pre-commit, sdist/wheel
build, clean force-install, `pip check`, and isolated installed-wheel smoke
passed. CPython 3.14 and 3.15 were not available locally (`py -0p` exposed only
3.12), so those runtime suites were not claimed.

### P03 — USER profile and resource-pool assignments — `TODO`

**Outcome.** Extend the non-secret USER AST from a singular action into an
ordered parameter representation without losing compatibility with P01.

**Required work.** Support typed `PROFILE {DEFAULT|name}` and `RESOURCE POOL
name [FOR SUBCLUSTER name]` on documented CREATE/ALTER branches, legal ordering,
duplicate/conflict checks, and serialization of existing USER actions. Preserve
the credential firewall unchanged and treat profile/pool existence and grants
as server checks.

**Explicit exclusions.** No `IDENTIFIED BY`, `SALT`, `REPLACE`, capacity limits,
roles, search path, or arbitrary configuration values.

**Primary sources.** [CREATE USER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-user/)
and [ALTER USER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-user/).

**Completion record.** Pending.

### P04 — USER time and capacity limits — `TODO`

**Outcome.** Add the remaining deterministic non-secret capacity/time policy
parameters to the ordered USER representation.

**Required work.** Implement `GRACEPERIOD`, `IDLESESSIONTIMEOUT`,
`MAXCONNECTIONS` including `ON DATABASE|NODE`, `MEMORYCAP`, `RUNTIMECAP`,
`TEMPSPACECAP`, and `SECURITY_ALGORITHM`. Pin accepted sentinel/value forms and
validate sizes/intervals lexically. Make literal rejection clause-aware because
legitimate limits use strings, while proving that `IDENTIFIED BY`, `SALT`, and
`REPLACE` still fail without disclosure.

**Explicit exclusions.** Password material, search paths, roles, and arbitrary
SET/CLEAR configuration.

**Primary sources.** The 26.2 CREATE/ALTER USER pages linked in P03.

**Completion record.** Pending.

### P05 — USER search path and default roles — `TODO`

**Outcome.** Model list-valued USER settings without confusing their commas
with outer parameter separators.

**Required work.** Support `SEARCH_PATH {DEFAULT|schema-list}` on documented
CREATE/ALTER forms and exclusive ALTER `DEFAULT ROLE {NONE|ALL|role-list|ALL
EXCEPT role-list}`. Enforce DEFAULT ROLE isolation, list cardinality, ordered
names, qualification rules, and existing role/USER collision contracts.

**Explicit exclusions.** Catalog grant/existence validation and credentials.

**Primary source.** [ALTER USER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-user/).

**Completion record.** Pending.

### P06 — safe USER configuration/reset actions — `TODO`

**Outcome.** Close the deterministic, non-secret remainder of ALTER USER while
leaving unknown configuration values fail-closed.

**Required work.** Add `TOTPSECRET RESET`, `CLEAR [PARAMETER] name-list`, and
only a primary-source-audited, static non-secret allowlist for `SET [PARAMETER]
name=value`. Unknown or string-valued parameters that could carry secrets must
raise through the sanitizer and never enter an AST. Extend the credential
sentinel harness across all literal token forms and error/log channels.

**Primary source.** The 26.2 ALTER USER page linked in P05.

**Completion record.** Pending.

### P07 — AUTHENTICATION create/drop core — `TODO`

**Outcome.** Add a non-secret semantic core for CREATE/DROP AUTHENTICATION.

**Required work.** Audit and implement a typed name, finite `METHOD`,
`LOCAL|HOST [TLS|NO TLS] 'address'`, documented MFA/fallthrough flags, and
single-target `DROP AUTHENTICATION [IF EXISTS] name [CASCADE]`. Keep network
addresses opaque strings and catalog validation server-side. Add exact dispatch
collision tests with USER, PROFILE, grants, quoted/confusable object kinds, and
unsupported SET tails.

**Explicit exclusions.** OAuth/LDAP bind credentials and all ALTER SET
parameters. Recognized excluded tails must fail closed and be sanitized.

**Primary sources.** [CREATE AUTHENTICATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/create-statements/create-authentication/)
and [DROP AUTHENTICATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/drop-statements/drop-authentication/).

**Completion record.** Pending.

### P08 — AUTHENTICATION structural ALTER actions — `TODO`

**Outcome.** Add one-action typed ALTER roots without opening parameter/secret
syntax.

**Required work.** After re-auditing the exact 26.2 matrix, support enable/
disable, LOCAL/HOST access, rename, method, nonnegative priority, documented MFA
state, and `[NO] FALLTHROUGH`. Enforce action exclusivity, exact host/TLS order,
lexical huge-number handling, and generator symmetry.

**Explicit exclusions.** ALTER SET and catalog method compatibility.

**Primary source.** [ALTER AUTHENTICATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-authentication/).

**Completion record.** Pending.

### P09 — AUTHENTICATION SET security boundary — `TODO`

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

**Completion record.** Pending.

### P10 — COMMENT ON family — `TODO`

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

**Completion record.** Pending.

### P11 — VIEW lifecycle — `TODO`

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

**Completion record.** Pending.

### P12 — SCHEMA lifecycle — `TODO`

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

**Completion record.** Pending.

### P13 — administrative privilege targets — `TODO`

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

**Completion record.** Pending.

### P14 — access-policy lifecycle — `TODO`

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

**Completion record.** Pending.

### P15 — ordinary constraint conformance — `TODO`

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

**Completion record.** Pending.

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
