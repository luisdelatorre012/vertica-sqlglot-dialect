# Completed agent task archive

This file preserves completed task specifications and completion records moved
out of the executable backlog. It is historical context and is not required
reading when selecting the next task. The active dashboard and remaining work
are maintained in [AGENT_TASK_PLAN.md](AGENT_TASK_PLAN.md).

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

### P03 — USER profile and resource-pool assignments — `DONE`

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

**Completion record.** Added ordered typed USER parameter lists for profile
`DEFAULT`/named assignments and global or subcluster-specific resource-pool
assignments on CREATE and ALTER, while preserving existing account-state,
password-expiry, rename, serialization, and credential-sanitization contracts.
Duplicate/conflicting scopes, malformed ordering, identifiers, programmatic
ASTs, and foreign generation fail atomically; profile/pool existence, grants,
LDAP restrictions, and runtime effects remain catalog/server checks. The 26.2
source re-audit found no material grammar contradiction. The default CPython
3.12.6 gate passed 2871 tests at 93.86% coverage; Ruff, formatting, strict mypy,
full pre-commit, sdist/wheel build, clean force-install, `pip check`, and
isolated installed-wheel smoke passed. CPython 3.14 and 3.15 were not available
locally (`py -0p` exposed only 3.12), so those runtime suites were not claimed.

### P04 — USER time and capacity limits — `DONE`

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

**Completion record.** Added ordered typed USER parameters for grace, idle
session, and runtime intervals; database/node-scoped connection counts;
memory/temporary-space caps; and ALTER-only security-algorithm selection.
Documented sentinels, percentage/unit shapes, interval ceilings, duplicates,
programmatic ASTs, serialization/optimizer/type traversal, comments, and
foreign generation are validated atomically. Literal admission is clause-aware,
so legitimate limit strings are retained while `IDENTIFIED BY`, `SALT`, and
`REPLACE` credential values still fail with fixed sanitized errors. The 26.2
ALTER example places `SECURITY_ALGORITHM` immediately before excluded
`IDENTIFIED BY` without the comma required by the page's general account-
parameter grammar; this implementation follows the explicit comma-delimited
grammar for the supported non-secret subset and does not infer credential
behavior. Privileges, LDAP compatibility, effective limit interactions, and
runtime password-expiration effects remain catalog/server concerns. The
default CPython 3.12.6 gate passed 3042 tests at 93.82% coverage; isolated
CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1
suites each passed 3042 tests, with 3.15 treating deprecations as errors. Ruff,
formatting, strict mypy, full pre-commit, sdist/wheel build, clean force-install,
`pip check`, and installed-wheel entry-point/round-trip smoke passed.

### P05 — USER search path and default roles — `DONE`

**Outcome.** Model list-valued USER settings without confusing their commas
with outer parameter separators.

**Required work.** Support `SEARCH_PATH {DEFAULT|schema-list}` on documented
CREATE/ALTER forms and exclusive ALTER `DEFAULT ROLE {NONE|ALL|role-list|ALL
EXCEPT role-list}`. Enforce DEFAULT ROLE isolation, list cardinality, ordered
names, qualification rules, and existing role/USER collision contracts.

**Explicit exclusions.** Catalog grant/existence validation and credentials.

**Primary source.** [ALTER USER](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-user/).

**Completion record.** Added typed `UserSearchPath` and `UserDefaultRoles`
children inside the ordered USER parameter model. CREATE/ALTER SEARCH_PATH now
retains DEFAULT or a nonempty ordered schema list with at most one namespace
qualifier; ALTER DEFAULT ROLE retains NONE, ALL, a nonempty role list, or ALL
EXCEPT a nonempty role list and remains isolated from every other action.
Identifier provenance, 128-byte UTF-8 limits, duplicate/cardinality checks,
serialization, optimizer/type traversal, strict programmatic generation, and
atomic foreign failure are covered. The 26.2 source re-audit found no material
grammar contradiction. Schema/role existence, access or grants, session search
precedence, and login-time role activation remain catalog/server concerns. The
default CPython 3.12.6 gate passed 3159 tests at 93.67% branch coverage;
isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and
3.15.0rc1 suites each passed 3159 tests, with 3.15 treating deprecations as
errors. Ruff, formatting, strict mypy, full pre-commit, sdist/wheel build, clean
force-install, `pip check`, and installed-wheel entry-point/round-trip smoke
passed.

### P06 — safe USER configuration/reset actions — `DONE`

**Outcome.** Close the deterministic, non-secret remainder of ALTER USER while
leaving unknown configuration values fail-closed.

**Required work.** Add `TOTPSECRET RESET`, `CLEAR [PARAMETER] name-list`, and
only a primary-source-audited, static non-secret allowlist for `SET [PARAMETER]
name=value`. Unknown or string-valued parameters that could carry secrets must
raise through the sanitizer and never enter an AST. Extend the credential
sentinel harness across all literal token forms and error/log channels.

**Primary source.** The 26.2 ALTER USER page linked in P05.

**Completion record.** Added typed isolated `TOTPSECRET RESET`, ordered
value-free `CLEAR [PARAMETER]` names, and a static five-parameter depot SET
allowlist. The four reviewed Boolean controls accept only numeric 0/1;
`DepotOperationsForQuery` accepts quoted or unquoted ALL/FETCHES/NONE and
normalizes to an unquoted enum. Unknown names and unsafe/string values fail
through the fixed pre-AST credential sanitizer across every supported literal
token form and error/log channel. The 26.2 source re-audit found no material
grammar contradiction: ALTER USER shows the five USER-level depot parameters,
while the Eon parameter and depot guides define their finite values and show
both quoted and unquoted enum usage. Parameter level eligibility, privileges,
session propagation, TOTP enrollment, Eon mode, and runtime effects remain
catalog/server concerns. The default CPython 3.12.6 gate passed 3326 tests at
93.69% branch coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13,
3.13.15, 3.14.7, and 3.15.0rc1 suites each passed 3326 tests, with 3.15 treating
deprecations as errors. Ruff, formatting, strict mypy, full pre-commit,
sdist/wheel build, clean force-install, `pip check`, and installed-wheel
entry-point/round-trip smoke passed.

### P07 — AUTHENTICATION create/drop core — `DONE`

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

**Completion record.** Added atomic typed CREATE/DROP AUTHENTICATION roots and
a structured LOCAL/HOST access child for all eight formal 26.2 methods,
omitted/TLS/NO TLS host matching, ENFORCEMFA, compatible FALLTHROUGH, and
single-target IF EXISTS/CASCADE drops. Addresses remain opaque strings;
existence, grants, priority, address validity, and runtime matching remain
catalog/server concerns. All ALTER SET and unexpected CREATE SET values fail
through a fixed pre-AST sanitizer, so bind passwords, OAuth secrets, keys,
URLs, and unknown parameter values cannot enter an AST or parser diagnostics.
The 26.2 source re-audit found two material documentation contradictions: the
formal CREATE syntax block omits ENFORCEMFA even though its parameter table and
creation guide place it after access, while that guide also contains stale
TYPE LDAP and METHOD password examples absent from the formal METHOD grammar.
This implementation accepts ENFORCEMFA but follows the formal METHOD keyword
and eight-value table rather than those examples. The default CPython 3.12.6
gate passed 3511 tests at 93.57% branch coverage; isolated CPython 3.9.25,
3.10.20, 3.11.15, 3.12.13, 3.13.15, 3.14.7, and 3.15.0rc1 suites each passed
3511 tests, with 3.15 treating deprecations as errors. Ruff, formatting,
strict mypy, full pre-commit, sdist/wheel build, clean force-install, package
compatibility check, and installed-wheel entry-point/round-trip smoke passed.

### P08 — AUTHENTICATION structural ALTER actions — `DONE`

**Outcome.** Add one-action typed ALTER roots without opening parameter/secret
syntax.

**Required work.** After re-auditing the exact 26.2 matrix, support enable/
disable, LOCAL/HOST access, rename, method, nonnegative priority, documented MFA
state, and `[NO] FALLTHROUGH`. Enforce action exclusivity, exact host/TLS order,
lexical huge-number handling, and generator symmetry.

**Explicit exclusions.** ALTER SET and catalog method compatibility.

**Primary source.** [ALTER AUTHENTICATION](https://docs.vertica.com/26.2.x/en/sql-reference/statements/alter-statements/alter-authentication/).

**Completion record.** Added atomic one-action `AlterAuthentication` roots with
typed enable/disable, LOCAL/HOST TLS access, rename, all eight finite methods,
lexically nonnegative priority, Boolean MFA state, and `[NO] FALLTHROUGH`
actions. Action exclusivity, exact clause order, huge priorities, identifiers,
serialization/optimizer/type traversal, strict programmatic ASTs, and foreign
atomicity are covered; ALTER SET remains behind the fixed pre-AST sanitizer.
The 26.2 source re-audit found one material contradiction: the formal syntax
omits ENFORCEMFA while the parameter table documents dynamic enable/disable and
explicit true/false state. This implementation follows the parameter table's
finite `ENFORCEMFA TRUE|FALSE` form and records the boundary rather than
admitting other spellings. Current-method compatibility, address validity,
priority effects, privileges, and runtime behavior remain catalog/server
concerns. The default CPython 3.12.6 gate passed 3679 tests at 93.51% branch
coverage; isolated CPython 3.9.25, 3.10.20, 3.11.15, 3.12.13, 3.13.15,
3.14.7, and 3.15.0rc1 suites each passed 3679 tests, with 3.15 treating
deprecations as errors. Ruff, formatting, strict mypy, full pre-commit,
sdist/wheel build, clean force-install, `pip check`, and installed-wheel
entry-point/ALTER round-trip smoke passed.

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
