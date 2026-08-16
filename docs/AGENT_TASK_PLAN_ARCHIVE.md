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
