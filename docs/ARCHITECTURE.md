# Dialect architecture

This package targets OpenText Analytics Database (Vertica) 26.2 and a single
tested SQLGlot minor release at a time. SQLGlot's public plugin entry point is
stable, but parser and generator subclass APIs can change between minor
versions; the runtime dependency is therefore bounded to `>=30.13.0,<30.14.0`.

## AST policy

The parser uses SQLGlot's canonical expressions whenever they represent the
same semantics. This keeps optimizers, lineage, qualification, and
cross-dialect generation useful. A Vertica-specific expression is introduced
only when mapping to a canonical node would discard syntax or change meaning.

Custom nodes should subclass the closest canonical expression when one exists.
For example, a partitioned top-k clause is still a kind of `exp.Limit`, and a
Vertica bulk load is still a kind of `exp.Copy`. This makes generic tree
visitors and optimizer checks see the node.

That rule has one safety exception: a canonical subclass is not used when its
generic generator fallback would invent valid-looking but nonexistent SQL.
`SetLiteral` and the statement-timestamp nodes therefore use plain custom
expressions. `ListAgg` wraps a canonical `exp.GroupConcat` child, preserving
aggregate discovery and column traversal without allowing a foreign generator
to emit a fictitious `LIST_AGG` call.

That exception is not limited to what a foreign dialect's ordinary per-node
renderer would produce. Some dialect generators structurally rewrite a
canonical class by `isinstance` before per-node dispatch ever runs: SQLite's
CREATE TABLE generator detects a single-column `exp.PrimaryKey` table
constraint and folds it into the column definition, rebuilding a fresh
canonical `PrimaryKeyColumnConstraint` in the process. A Vertica subclass of
`exp.PrimaryKey` is still an `exp.PrimaryKey` for that `isinstance` check, so
its Vertica-only fields would be silently discarded instead of failing
atomically. The standard "every custom expression fails explicitly in
postgres" sweep does not catch this, because it only instantiates bare
`vexp.*` classes with no arguments; it never constructs a canonical class
carrying a new Vertica-only field value. The ordinary-constraint enforcement
markers (`VerticaPrimaryKeyColumnConstraint`, `VerticaUniqueColumnConstraint`,
`VerticaPrimaryKey`, `VerticaCheckColumnConstraint`) are therefore plain,
detached custom expressions rather than canonical subclasses, even though
their shape otherwise matches the canonical node exactly. Before reusing a
canonical class to carry a new Vertica-specific field value, check whether any
supported foreign dialect performs this kind of pre-dispatch structural
rewrite on that class, not just what its ordinary per-node renderer emits.

The standard bare-instantiation sweep also misses a second, unrelated gap in
the opposite direction: a detached custom `exp.Property` subclass that is
never wrapped in a real `exp.Properties`/`exp.Create` tree does not exercise
the code path SQLGlot's base `Generator.create_sql` actually uses in
production. `vexp.LocalProperty().sql(dialect="postgres")` raises a clean
`UnsupportedError`, because rendering a detached expression goes straight to
per-node dispatch and `self.unsupported(...)`. But every Vertica table
property is always rendered inside a real `exp.Properties` list, and
`Generator.locate_properties` looks up each property's class in
`self.PROPERTIES_LOCATION` with a plain dict index before any per-node
dispatch runs; a foreign dialect that had never heard of a Vertica-only
`Property` subclass used to raise a raw `KeyError` from that lookup instead
of an intended, atomic failure. This reproduced for every pre-existing
Vertica-only table `Property` class once it was exercised inside a real
`CREATE TABLE`/`CREATE TABLE AS` statement — confirmed for `LocalProperty`,
`KsafeProperty`, `TableSegmentationProperty`, `TablePartitionProperty`,
`DiskQuotaProperty`/`CtasDiskQuotaProperty`, and `InheritedPrivilegesProperty`
against PostgreSQL, DuckDB, MySQL, and SQLite, and predated scoped temporary
CTAS: `CREATE TABLE t INCLUDE PRIVILEGES AS SELECT 1 AS id` already raised
`KeyError` against `postgres` before scoped CTAS existed. Foreign generation
still failed atomically in the sense that matters most (no dialect silently
emitted SQL with the clause dropped), but the exception was `KeyError` rather
than an intended one, and no regression caught it because the generic sweep
only instantiates bare `vexp.*` classes outside any `Properties` container —
treat any *new* custom `Property` subclass's foreign behavior as unproven
until it is tested inside a real `Properties` list, not just bare, since nothing
about constructing it bare would reveal a regression here.

Task Q05 closed this gap with a dict-based registration mirroring the
established custom-node contract rather than the alternative, weaker
upstream `Properties.Location.UNSUPPORTED` semantics (`UnsupportedError` at
`RAISE` only, silent/warned drop at `WARN`/`IGNORE` — rejected because it
would have silently dropped the clause at two of four error levels, the exact
failure mode this policy prohibits). `src/sqlglot_vertica/foreign_properties.py`
gives PostgreSQL's, DuckDB's, MySQL's, and SQLite's generator classes —
the four release-gate foreign dialects — a `PROPERTIES_LOCATION` whose
`__missing__` hook raises `ValueError(f"Unsupported expression type
{key.__name__}")` for any class introspected from `sqlglot_vertica.expressions`
as an `exp.Property` subclass, exactly the message and exception
`vexp.DropViews` already raises as an unregistered custom root, at every
`unsupported_level` including `WARN` and `IGNORE`; any other missing key
still raises the original plain `KeyError`, so non-Vertica trees and
dialects outside this release-gate set are unaffected. Because the
registered set is introspected from `vexp` rather than hand-maintained, a
newly added `Property` subclass is covered automatically the moment it is
embedded and generated abroad — `tests/test_foreign_property_atomicity.py`
pins this with an exhaustive sweep over every `vexp` `Property` subclass,
every release-gate foreign dialect, and every `unsupported_level`, plus a
frozen-set assertion that fails loudly if the enumeration itself drifts.
One property, `vexp.ResourcePoolParameter`, is deliberately excluded from
that sweep and carries no `PROPERTIES_LOCATION` entry, native or foreign: it
is only ever embedded inside `vexp.CreateResourcePool`/`AlterResourcePool`,
custom `exp.Create`/`exp.Alter` roots that already fail atomically on their
own unregistered class name before `locate_properties` ever runs, so it never
reaches this mechanism at all. The registration reaches its target generator
classes under either import order — Vertica-first or foreign-first — because
`patch_foreign_properties_location` imports the four target generator
modules directly rather than relying on `sqlglot.dialects`' lazy
`__getattr__` loader, which forces those four (lightweight, generator-only)
submodules to load as a side effect of importing the Vertica dialect even if
the host program never generates to them; this trade-off is deliberate and
verified under both orders in a fresh interpreter by
`tests/test_foreign_property_atomicity.py`.

Function syntax follows the same wrapper pattern. `UsingParameters` and
`StringUnit` retain the parsed function as `this` and store ordered parameter
or unit children separately. Source-sensitive calls such as Vertica `EXPLODE`,
one-argument `ARRAY_LENGTH`, extended `INSTR`, modifier-bearing `REGEXP_LIKE`,
and one-argument `TO_CHAR` wrap their closest canonical child. Optimizers can
still discover operands, predicates, lambdas, and aggregates, while foreign
generators fail on the outer Vertica node instead of silently changing a call's
meaning. Special execution partitions similarly use `VerticaWindow`, an
`exp.Window` subclass whose `partition_mode` is explicit and serialized.

The following invariants apply to every custom node:

1. Every semantic argument is declared in `arg_types`.
2. The Vertica generator has an explicit transform.
3. Parse/generate/reparse produces an equivalent tree.
4. Unsupported cross-dialect generation raises instead of silently deleting
   the construct, unless an explicit semantic lowering is documented and
   tested.
5. Public class names are treated as serialized-AST compatibility surface.

Ordered multilevel grouping is one case where a close canonical subclass is
necessary. SQLGlot 30.13's canonical `exp.Group` stores ordinary expressions,
`GROUPING SETS`, `CUBE`, and `ROLLUP` in four separate fields, and its generic
generator emits those buckets in the fixed order ordinary expressions,
grouping sets, cubes, then rollups. Vertica permits all four item kinds to be
interleaved and repeated, so parser-produced clauses use
`VerticaGroup(exp.Group)` with one source-ordered `expressions` list. The
subclass keeps scope traversal, qualification, optimization, lineage, ordinal
expansion, and `isinstance(exp.Group)` checks working while its explicit
Vertica transform renders that list without rebucketing it. The same node has
an optional typed `algorithm` child for the documented
`/*+GBYTYPE(HASH|PIPE)*/` clause hint. Canonical `exp.Group` trees remain
accepted for ordinary-only foreign/programmatic interoperability, but their
bucket, `all`, and `totals` fields are rejected rather than rendered in a
potentially reordered or foreign form. The custom root fails atomically in
foreign dialects, directly or nested in a SELECT.

Set operations stay fully canonical because SQLGlot's `Union`, `Intersect`,
and `Except` nodes preserve Vertica's operator and duplicate semantics without
an additional AST type. The parser records omitted and explicit `DISTINCT` as
`distinct=True`, records `UNION ALL` as `distinct=False`, and canonicalizes
the documented `MINUS` synonym to `Except`. Vertica's `INTERSECT`, `EXCEPT`,
and `MINUS` are DISTINCT-only, so their inherited `ALL` form fails through a
dedicated guaranteed-raise path at every parser error level. The same path
rejects SQLGlot's name-matching/correspondence fields (`by_name`, `on`,
`side`, and `kind`) for every operator. Generation validates those fields,
the Boolean duplicate mode, both query operands, and every nested operation
before returning SQL; invalid programmatic or foreign trees therefore cannot
emit `INTERSECT ALL`, `EXCEPT ALL`, `BY NAME`, or `CORRESPONDING` syntax.
Canonical nesting retains SQLGlot's left-associated tree, parentheses,
branch-local modifiers, whole-compound tails, scope traversal, qualification,
optimization, and lineage behavior.

Ordinary SELECT qualifiers and tails also stay canonical, but are now a
closed Vertica contract. Omitted/explicit `ALL` both use the canonical absence
of `Select.args["distinct"]`; plain `DISTINCT` uses `exp.Distinct`, while
`DISTINCT ON`, SELECT kinds/operation modifiers, and recognized `TOP` forms
fail through the SELECT family's guaranteed-raise path. Ordinary `LIMIT` and
`OFFSET` retain canonical `exp.Limit`/`exp.Offset` children whose value is an
unsigned integer literal (validated lexically, including arbitrarily large
digits) or the canonical anonymous JDBC placeholder. `LIMIT ALL` is a
deliberate semantic-no-op canonicalization to clause absence, rather than an
untracked parser loss; an internal parse-only marker lets following OFFSET and
lock clauses parse before the marker is removed. The independent
`PartitionedLimit` extension requires a positive literal plus nonempty
`PARTITION BY` and `ORDER BY` children. FETCH, comma-form LIMIT, PERCENT,
ROW/ROWS, WITH TIES, LIMIT BY, and non-row-count values fail closed.

`FOR UPDATE [OF table[, ...]]` remains one canonical `exp.Lock`; every other
strength and wait option is rejected. SQLGlot attaches a trailing lock to the
right SELECT branch before promoting ORDER/LIMIT/OFFSET to an enclosing set
operation, so the Vertica parser promotes that lock as well. This makes the
documented tail own the entire compound query and prevents generation such as
`right_branch FOR UPDATE ORDER BY ...`. Strict generation validates every
canonical qualifier/limit/offset/lock field, including falsey programmatic
extras, before returning SQL. The 26.2 pages conflict editorially on two
points: the current LIMIT syntax block omits the ordinary numeric alternative
that its own prose and `LIMIT 10` example exercise, and SELECT places OFFSET
before LIMIT while official set-operation syntax/examples use LIMIT before
OFFSET. Both relative LIMIT/OFFSET source orders are therefore accepted and
canonicalized to stable `LIMIT ... OFFSET ...`; ORDER must precede either and
FOR UPDATE must follow both.

Joined tables likewise retain canonical `exp.Join` nodes, but parsing and
generation enforce the 26.2 operator/predicate matrix. Default/explicit INNER
and LEFT/RIGHT/FULL `[OUTER]` joins require exactly one `ON` or `USING`
predicate; CROSS and NATURAL joins reject both. NATURAL outer joins retain the
formal `NATURAL {LEFT|RIGHT|FULL} OUTER JOIN` spelling, including the required
`OUTER` keyword, while comma joins remain canonical predicate-free `Join`
nodes. The canonical AST cannot distinguish a comma join from a programmatic
predicate-free default join once source tokens are gone, so the parser rejects
the latter at every error level and strict generation treats the identical
fieldless node as the documented comma form. ASOF, STRAIGHT_JOIN, positional,
global, match-condition, directed, pivot, and secondary-relation fields are
rejected rather than emitted or dropped. Structured JTYPE/DISTRIB hints remain
attached to an explicit documented join and render immediately after JOIN.

Two inherited input lowerings remain deliberate and are validated before the
PostgreSQL generator preprocessing that implements them. A SELECT-owned LEFT
SEMI/ANTI join with one ON predicate becomes an equivalent correlated
`[NOT] EXISTS` predicate; right/full variants, USING, detached join fragments,
and hinted forms fail instead of emitting foreign syntax or losing metadata.
CROSS/OUTER APPLY retains SQLGlot's canonical `Lateral` representation and
generates respectively as `INNER JOIN LATERAL ... ON TRUE` or
`LEFT JOIN LATERAL ... ON TRUE`. Q20 revalidated all four lowerings against
the installed generator and pins their exact Vertica output alongside
QUALIFY's established derived-table lowering. These are the complete
architecture-approved inherited query lowerings; Q12 does not broaden them.

Q20 froze the installed SQLGlot 30.13 field inventory for `Select`,
`SetOperation`, `Join`, `Table`, `TableSample`, `With`/`CTE`, row tails,
ordering, `Into`, `Create`, `Insert`, and `Drop`. The audit classifies each
field as documented Vertica syntax, one of the explicit canonicalizations or
lowerings above, or a fail-closed boundary. Q21 completed the ordinary query
closure: parser-produced SELECT, set-operation, subquery, table-reference,
TABLESAMPLE, ORDER/Ordered, Lateral, Pivot, and Star nodes are checked before
they can escape the query parser, and the same whole-tree preflight runs before
PostgreSQL's SELECT preprocessing can lower or discard a field. Named WINDOW,
CONNECT BY, LATERAL VIEW, PIVOT/UNPIVOT, DISTRIBUTE/SORT/CLUSTER BY, star
EXCLUDE/EXCEPT/REPLACE, ORDER SIBLINGS BY/WITH FILL and explicit NULLS
ordering, table ONLY/historical `AT (...)`, and method/ROWS/PERCENT/REPEATABLE
TABLESAMPLE variants now raise `ParseError` at every parser error level.
Strict direct and nested generation rejects those fields, falsey mutations,
unknown fields, and malformed child shapes with `UnsupportedError` before an
inherited renderer can emit foreign SQL or silently drop them. The documented
bare numeric `TABLESAMPLE(percent)` form remains canonical on tables and named
subqueries; numeric range and sampling behavior remain server checks. LATERAL
remains admitted only as the canonical output of the approved CROSS/OUTER
APPLY lowerings (INNER/LEFT LATERAL JOIN with `ON TRUE`), so those outputs
still reparse while free-standing LATERAL syntax fails closed.

One independent gap remains before recertification: several pre-existing
custom query-extension parsers still call level-dependent error paths.
Malformed TIMESERIES, MATCH, and INTERPOLATE inputs raise at
`IMMEDIATE`/`RAISE` but can return partial custom ASTs at `WARN`/`IGNORE`.
Q22 owns their guaranteed-raise and strict-generation closure. This gap is not
an approved lowering or canonicalization and is not waived by the historical
Q08 positive gate.

A clause that scopes an entire top-level query rather than one `exp.Select`
must still expose the concrete query shape to SQLGlot analysis. The SELECT
statement's `[ AT epoch ]` prefix precedes an optional `WITH` clause and any
following `UNION`/`INTERSECT`/`EXCEPT` chain, so Q13 represents it with four
parallel roots: `AtEpochSelect`, `AtEpochUnion`, `AtEpochIntersect`, and
`AtEpochExcept`. Each subclasses its corresponding canonical query class and
adds typed `at_epoch_kind`/`at_epoch_value` fields. This lets
`traverse_scope`, `qualify`, `optimize`, source expansion, and `lineage`
operate directly on the public parsed root with the same sources, columns,
CTEs, and scopes as the unprefixed query; callers never unwrap `.this`.

The four-class shape is deliberate. A single wrapper cannot be both a real
`Select` and every set-operation kind, while putting untyped prefix fields on
an exact canonical root would let foreign generators silently ignore them.
Each custom subclass is registered only in the Vertica generator, so direct
and nested PostgreSQL, DuckDB, MySQL, and SQLite generation still fails on the
custom class before Select-specific rewrites can discard the prefix. Vertica
generation validates the prefix and ordinary query fields, then delegates to
the existing strict SELECT or set-operation contract. SQLGlot's base
set-operation renderer uses exact root classes for its dialect lookup, so the
generator copies an analyzer-safe set root to the corresponding canonical
operator only after validation and only for rendering; the public AST remains
the custom query subclass. The original Q06 `AtEpochQuery` wrapper remains a
public legacy load/generation class so serialized dumps created before Q13
continue to load and emit identical Vertica SQL, but new parsing never emits
it.

The pre-existing, structurally unrelated CTAS-only `AtEpochProperty` snapshot
property (`_parse_at_epoch_property`, wired only into the CTAS
`AS [hint] [AT EPOCH|AT TIME] query` position) shares the same `EPOCH
LATEST`/`EPOCH <integer>`/`TIME '<timestamp>'` value grammar as the historical
query roots but not their parsing method, node classes, or guaranteed-raise
wrapper. Task Q07
found and fixed a latent defect in that method's three malformed-value
branches, the same shape P15 already fixed once for the CREATE TABLE
definition/CTAS/LIKE dispatch (see the column-constraint discussion below):
each branch called plain, level-dependent `self.raise_error(...)` and then
fell through to `kind`/`value` usage, so at `RAISE`, `WARN`, and `IGNORE` a
malformed value did not reliably become `ParseError` — depending on which
branch, the method instead silently returned an `AtEpochProperty` built from
an invalid value (`AT EPOCH 1.5` at `WARN`/`IGNORE`, since `value` stayed
bound to the non-integer literal), raised `AssertionError` (`AT TIME` with an
unquoted value, since `_parse_string()` left `value` bound to `None`), or
raised `UnboundLocalError` (a missing `EPOCH`/`TIME` keyword, since neither
`kind` nor `value` was assigned at all in that branch). All three call sites
now route through the CTAS family's own `_raise_create_table_error`
guaranteed-raise wrapper, matching the established pattern: control never
returns to the fall-through code once a malformed value is recognized, so
every branch fails with `ParseError` at every error level regardless of
whether `value` would otherwise have been bound, `None`, or unbound.
`AtEpochProperty`'s `arg_types`, valid-input parsing, and rendering are
unchanged, and the historical query family's own, separate guaranteed-raise
wrapper (`_raise_at_epoch_query_error`) was untouched.

WITH and CTE parsing has its own fail-closed query-expression boundary. While
SQLGlot parses a CTE body, `VerticaParser._parse_statement` switches to a
restricted path that admits only a nonempty SELECT, a supported
UNION/INTERSECT/EXCEPT tree whose branches satisfy the same rule, and a
subordinate WITH attached to one of those queries. This prevents the ordinary
top-level dispatcher from admitting PROFILE, EXPLAIN, directed-query, DML,
DDL, or administrative roots. It also deliberately rejects inherited VALUES
and bare-FROM query shorthands, SELECT INTO side effects, and an `AT epoch`
prefix: the 26.2 WITH production places `[ subordinate-WITH-clause ]
query-expression` inside each CTE, whereas `AT epoch` is a statement-level
prefix in the separate SELECT production. The WITH page's statement-level
restriction says WITH supports SELECT and INSERT, and its official INSERT
example uses the target-following form `INSERT INTO target WITH ... SELECT`;
that form remains valid while a leading WITH before INSERT or any other
nonquery statement fails through the CTE family's guaranteed-raise wrapper.

The same parser boundary rejects PostgreSQL per-CTE `AS [NOT] MATERIALIZED`,
USING KEY, and recursive SEARCH/CYCLE extensions; Vertica's one clause-level
`ENABLE_WITH_CLAUSE_MATERIALIZATION` hint, ordinary/multiple/subordinate CTEs,
and documented UNION/UNION ALL recursion remain supported. Strict generation
validates With/CTE root placement, nonempty typed CTE lists, aliases and column
lists, recursive state, body roots, modifiers, and unknown fields before
rendering. A CTE list arriving before the historical prefix (`WITH cte AS
(...) AT EPOCH ...`) still fails, while the documented `AT epoch WITH ...
SELECT` order remains analyzer-safe through Q13's query subclasses.

The same distinction applies to external loading. Executable `COPY` remains an
`exp.Copy` subclass, while the reusable body inside `CREATE EXTERNAL TABLE` is
an `ExternalCopyDefinition`: a targetless node that shares structured source,
format, column, and parameter children without pretending to be an executable
statement missing its target. External-table parsing applies a narrower
context allowlist, so `LOCAL`, `STDIN`, stream/load modes, rejected-data tables,
collection options, and `NO COMMIT` cannot leak through COPY grammar reuse.
`FlexibleCopyDefinition` narrows that context again: file and UDL inputs must
carry a parser, built-in formats are excluded, and an explicit COPY column
list must preserve `__raw__`. Iceberg tables do not reuse COPY at all; an
`IcebergExternalTableSpec` models their location, mutually exclusive catalog
modes, authentication payload, and metadata-bound type overrides.

Role lifecycle DDL stays canonical where the SQLGlot tree is lossless:
`CREATE ROLE`, rename, and single-target `DROP ROLE` use `exp.Create`,
`exp.Alter`, and `exp.Drop`. A comma-separated role drop uses `DropRoles` so a
foreign generator cannot silently emit only one target. Resource-pool roots
subclass their corresponding canonical statement classes, but retain explicit
Vertica transforms because ordered typed parameters and subcluster selectors
have no lossless canonical property representation.

USER lifecycle deliberately has a narrower security boundary. `CreateUser`,
`AlterUser`, and `DropUsers` retain ordinary identifier and rename children,
but explicit Vertica transforms validate the bounded non-secret grammar and
prevent foreign generators from silently discarding account state or secondary
drop targets. Ordered CREATE/ALTER parameter lists combine existing
`UserAction` account lock/unlock and password-expiry markers with typed
`UserParameter` profile and resource-pool assignments, including an optional
subcluster identifier, plus deterministic time/capacity settings. Interval
strings are checked lexically against the documented 20-day or one-year
ceilings; memory and temporary-space strings have finite percentage/unit
shapes; and `MAXCONNECTIONS` retains its explicit database/node scope.
ALTER-only `SECURITY_ALGORITHM` retains one canonical reviewed enum string. No
password, TOTP secret, or other credential value has an AST slot. Names share
the connection-policy lexical rules, additionally
enforce Vertica's 128-byte UTF-8 limit, and use the active Vertica tokenizer's
identifier-token domain rather than a frozen reserved-word list. Profile and
pool existence, pool grants, and assignment effects remain catalog/server
checks. `UserSearchPath` retains either the exact DEFAULT sentinel or an ordered,
nonempty schema list whose entries can carry one namespace qualifier;
`UserDefaultRoles` retains NONE, ALL, an ordered role list, or ALL EXCEPT with
an ordered role list. DEFAULT ROLE remains an isolated ALTER action, and role
names remain unqualified. `UserConfiguration` contains ordered typed parameters
for an isolated SET or CLEAR action. CLEAR is value-free and keeps safe unquoted
ASCII configuration names; SET is restricted to the five depot parameters that
26.2 documents at USER level. Four take only numeric `0` or `1`, while
`DepotOperationsForQuery` takes `ALL`, `FETCHES`, or `NONE`. The optional
`PARAMETER` noise word and quoted/unquoted depot-operation values normalize to
`SET PARAMETER name = value`.

Tokenizable credential-bearing USER clauses are rejected before ordinary
parser errors can retain or log their values, with a fixed sanitized error at
every `ErrorLevel`. This is defense in depth, not a secret-handling API:
SQLGlot tokenization happens before parser hooks, and an upstream tokenizer
error (for example, an unterminated credential string) can include raw input.
Callers must never submit real credentials to this dialect. Literal admission
is clause-aware so documented USER limit strings and the reviewed finite depot
enum can enter the AST while credential literals in `IDENTIFIED BY`, `SALT`,
`REPLACE`, and unreviewed SET paths still fail before ordinary parser
diagnostics. For the reviewed boundary, `UseDepotForReads=0` and
`DepotOperationsForQuery='Fetches'` are accepted and the latter emits
`DepotOperationsForQuery = FETCHES`; Boolean `2`, unknown parameter names, and
unknown/string values are rejected. Arbitrary value-bearing USER configuration
parameters stay outside the semantic contract and fail closed when recognized.

PROFILE lifecycle uses `CreateProfile`, `AlterProfile`, and `DropProfiles`
roots plus ordered `ProfileLimit` and `ProfileParameter` children. The values
are password-policy metadata—unsigned numeric settings or explicit policy
sentinels—not passwords or other credential material. Parser and generator
validate documented deterministic ranges lexically, including arbitrarily
large source digits, and reject only same-statement minimum/maximum conflicts
that can be decided without catalog state. Profile assignment, inherited
effects, ownership, and effects on current passwords remain server concerns.

AUTHENTICATION lifecycle uses atomic `CreateAuthentication`,
`AlterAuthentication`, and `DropAuthentication` roots. `AuthenticationAccess`
retains LOCAL versus HOST, the opaque HOST address string, and the three
distinct TLS states (omitted, TLS, and NO TLS). CREATE flags and every ALTER
structural change remain typed; ALTER accepts exactly one enable/disable,
access, rename, finite method, lexical nonnegative priority, Boolean MFA, or
fallthrough action. METHOD is restricted to the eight 26.2 spellings and
remains a standard string literal. The parser rejects CREATE method/fallthrough
combinations that the primary source declares incompatible; ALTER compatibility
depends on the record's catalog method and remains server-side. Address
validity, grants, priority effects, and runtime matching also remain server
concerns. `AuthenticationSet` owns an ordered nonempty list of typed
`AuthenticationParameter` children, but its static allowlist contains only two
OAuth settings whose complete values are closed by the 26.2 sources:
`validate_type` accepts standard strings `IDP` or `JWT`, and `jit_enabled`
accepts standard strings `yes` or `no`. Input casing normalizes to those exact
spellings; quoted alternatives outside the finite sets, unquoted values,
duplicates, unknown names, and nonstandard literal tokens are rejected.

The parameter audit classifies `bind_password` and `client_secret` as explicit
secrets. LDAP/Ident/Kerberos parameters (`host`, `ldap_continue`, `starttls`,
`binddn_prefix`, `binddn_suffix`, `domain_prefix`, `email_suffix`, `basedn`,
`binddn`, `search_attribute`, `system_users`, and `realm`) and the remaining
OAuth parameters (`groups_claim_name`, `oauth2_jit_authorized_roles`,
`role_group_suffix`, `roles_claim_name`, `client_id`, `discovery_url`,
`introspect_url`, `auth_url`, `token_url`, `scope`, `validate_hostname`,
`jwt_rsa_public_key`, `jwt_ec_public_key`, `jwt_jwks_url`, `jwt_issuer`,
`jwt_user_mapping`, `jwt_accepted_audience_list`, and
`jwt_accepted_scope_list`) accept arbitrary or incompletely documented strings;
they are therefore catalog/unknown for this AST security boundary even when
their intended content is not itself secret. Unknown future names receive the
same classification. A fixed pre-AST sanitizer rejects every excluded name and
every out-of-domain allowlisted value before ordinary parser diagnostics can
retain the payload. For example, `validate_type='JWT'` and
`jit_enabled='no'` are accepted and canonical; `validate_type='OIDC'`,
`validate_hostname='true'`, `client_secret='sentinel'`, and any unknown name
fail with the same sanitized error. This remains defense in depth: callers must
never submit real credentials because tokenization precedes parser hooks.

Executable `PROFILE` uses a separate atomic `ProfileStatement` wrapper whose
required `this` child is the complete profiled statement. SELECT/set-operation
queries and the documented INSERT, UPDATE, DELETE, COPY, and MERGE families
remain canonical or existing Vertica-specific children, so hints, comments,
column/table traversal, optimization, and serialization do not depend on
recovering SQL from opaque text. The wrapper owns only its one batch statement;
DDL, transaction control, VALUES-only queries, and nested PROFILE fail closed.
Foreign dialects reject the wrapper atomically because dropping PROFILE would
change execution behavior.

Workload-routing lifecycle roots likewise subclass canonical CREATE, ALTER,
and DROP nodes while keeping their route specification, name/workload target,
and single ALTER action explicit. Session controls retain a canonical
`SetItem(EQ(Column, value))` child inside `SetSessionRouting`; this keeps the
assignment traversable while preserving Vertica's distinct `WORKLOAD TO` and
`RESOURCE_POOL =` operators. The optimizer may quote the internal left-hand
marker, so generation validates its one-part semantic name rather than its
quoting metadata. `ShowWorkload` is atomic because SQLGlot 30.13 tokenizes SHOW
payloads as opaque command text. Workload privilege targets remain canonical
GRANT/REVOKE roots, but `ON ROUTING RULE` normalizes to the documented
`ON WORKLOAD` target and receives exact USAGE/target/principal validation.

Administrative KEY, LIBRARY, DATA LOADER, and TLS CONFIGURATION privileges use
canonical `exp.Grant`/`exp.Revoke` roots with a `VerticaPrivilegeTarget` child,
even for one target. That structured child makes the object kind, ordered
targets, qualification, and foreign-generation boundary explicit. The parser
and generator share direction-specific privilege domains: DATA LOADER grants
and revokes accept ALTER/DROP/EXECUTE or ALL and exactly one target; KEY accepts
USAGE/ALTER/DROP or ALL, with EXTEND only on grants; LIBRARY grants accept
USAGE/DROP or ALL with optional EXTEND while revokes accept only USAGE or ALL;
and TLS CONFIGURATION grants accept USAGE/ALTER/DROP while revokes additionally
accept ALL. DATA LOADER and LIBRARY alone accept cascading revocation. KEY and
TLS names are unqualified, DATA LOADER allows one schema qualifier, and LIBRARY
allows database plus schema. Principal and target components share the strict
128-byte identifier contract. Catalog ownership, object existence, and whether
a named principal is a user or role remain server checks. Existing typed UDx
routine signatures and their empty, named, and typed argument forms are
unchanged.

Access-policy lifecycle statements use atomic `CreateAccessPolicy`,
`AlterAccessPolicy`, and `DropAccessPolicy` roots around a shared
`AccessPolicyTarget`. The target preserves the table plus the exclusive row or
column selector, while CREATE and expression-replacing ALTER actions retain the
policy expression as a traversable child. ALTER also distinguishes policy
modification from `COPY TO TABLE`, and each root validates exact qualification,
state, `GRANT TRUSTED`, and modifier contracts during parsing and generation.
The formal 26.2 ALTER grammar is authoritative where its prose examples omit
`GRANT TRUSTED`; likewise, the formal COPY and DROP productions restrict their
destination or source table to one part. Policy target existence and type,
expression volatility and user-defined transform behavior, ownership,
permissions, and runtime evaluation remain catalog or server concerns.

Load-balance-group roots follow the same atomic statement policy. A
`LoadBalanceGroupSpec` keeps its ADDRESS, FAULT GROUP, or SUBCLUSTER members,
optional policy, and required branch-specific filter traversable; a separate
`LoadBalanceGroupAction` represents SET/ADD/DROP without conflating group
membership with routing-rule destinations. Rename stays canonical as
`AlterRename`. Parser and generator share neutral connection-policy identifier
rules, while member existence, current group type, CIDR validity, and dependent
routing rules remain catalog concerns.

Network-address roots complete the connection-policy lifecycle without
conflating it with the deprecated NETWORK INTERFACE family. A
`NetworkAddressSpec` retains the node, opaque address/hostname string, optional
port, and explicitly supplied enabled state; omission remains omission rather
than synthesizing server defaults. `NetworkAddressAction` represents endpoint
replacement and state changes, while rename stays canonical as `AlterRename`.
Identifiers follow Vertica's ASCII-first, Unicode-letter-continuation rules,
and ports are validated lexically as unsigned integers without guessing a
server range or converting arbitrarily large digit strings to Python integers.
Node existence, endpoint ownership, address-family validity, reachability, and
load-balance-group dependency effects remain catalog or server concerns.

Factory-backed UDxs use a shared `CreateUserDefinedExtension` root and
`UDxFactorySpec`: the catalog name remains canonical, while language, factory,
library, and fenced mode remain an ordered atomic unit that cannot leak as a
foreign `Command`. UDx drops reuse the neutral `RoutineSignature` child already
used by privilege targets, but `DropUserDefinedExtension` alone validates the
family-specific empty/named/typed signature rules. This keeps security grants
and external-procedure signatures unchanged. Library lifecycle uses separate
CREATE/DROP roots for the same foreign-generation guarantee.

The documented COMMENT ON family uses one atomic `CommentOn` root. Qualified
catalog objects and columns remain canonical table/column children, routine
targets reuse `RoutineSignature`, and `CommentConstraintTarget` keeps the
constraint name and owning table separate. The comment value is exactly one
standard string literal or `NULL`; the latter preserves comment removal rather
than conflating it with an absent AST child. Catalog ownership/existence and
the server's documented 8192-character truncation remain server concerns.
Foreign dialects reject both the root and the detached constraint target.

Persistent views retain canonical `exp.Create` nodes because SQLGlot preserves
their target, optional columns, query, replacement flag, and inherited-
privilege property exactly. `AlterView` and `DropViews` are atomic roots around
qualified table-shaped names: ALTER owns exactly one typed owner, schema,
privilege, or ordered rename action, while DROP owns an ordered nonempty target
list and postfix `IF EXISTS`. Multi-view rename source and unqualified target
lists have equal cardinality. The 26.2 DROP grammar has no dependency modifier,
so `CASCADE` and `RESTRICT` fail closed rather than inheriting generic SQLGlot
behavior. Ownership, existence, name uniqueness, current-database resolution,
and dependency effects remain catalog/server checks. Local temporary CREATE
VIEW syntax and TABLE lifecycle dispatch remain separate.

Schema creation likewise remains canonical because the existing `exp.Create`
tree preserves authorization, default inherited privileges, namespace/database
qualification, and quota properties. `AlterSchema` and `DropSchemas` are atomic
roots around SQLGlot's database-reference-shaped schema names. ALTER owns
exactly one typed default-privilege, owner (with optional object cascade), disk-
quota, or ordered rename action. Quotas use the documented quoted unsigned-
integer plus K/M/G/T grammar, normalize the unit to uppercase, and preserve
arbitrarily large digit strings without integer conversion; `SET NULL` remains
a distinct typed reset. Multi-schema rename lists have equal cardinality and
retain every explicitly supplied source namespace. DROP owns an ordered
nonempty target list, prefix `IF EXISTS`, and at most one postfix `CASCADE` or
explicit `RESTRICT`. Compound CREATE SCHEMA bodies remain fail-closed and
separately planned. Namespace mode, current-database resolution, ownership,
object dependencies, and quota relationships remain catalog/server checks.

Milestone 1 table targets share one lexical and structural contract across
CREATE TABLE definition/LIKE/CTAS, INSERT, SELECT INTO, and DROP TABLE. A
target is an `exp.Table` containing exactly one table identifier, an optional
schema, and an optional namespace/database qualifier; the outer qualifier is
invalid without the schema, and a fourth part cannot hide in an `exp.Dot`.
Every component is nonempty valid UTF-8 and at most 128 bytes. Unquoted names
start with an ASCII letter or underscore and continue with ASCII letters,
digits, underscore, dollar, or Unicode letters; quoted names retain arbitrary
valid payloads and source case, including reserved words. Parser validation
runs through the owning statement family's guaranteed-raise boundary, while
one shared generator validator rejects malformed canonical/programmatic
`Table`/`Identifier` children, including wrong types and falsey extra fields,
before any SQL is returned. This boundary is intentionally target-specific;
source-relation, column, and alias identifiers retain their own contracts.

Canonical `CREATE TABLE` generation has a separate whole-tree preflight that
runs before SQLGlot locates, sorts, or renders any property. It first
classifies the root as definition, LIKE, or CTAS from the target and query
shape, then validates the exact property domain for that form, every property
container and typed child, scope/temporary/ON COMMIT combinations, duplicate
and mutually exclusive properties, `NO PROJECTION` conflicts, LOCAL quota
prohibition, CTAS column-list/`ENCODED BY` exclusivity, and every canonical
`Create` field. Unknown fields are rejected even when falsey. The four false
modifier fields and empty/`None` fields that PostgreSQL's parser always
materializes on an otherwise portable plain CREATE TABLE are accepted only as
their semantic-absence defaults; meaningful values still fail. Validation
uses no recursive SQL generation, so malformed direct or nested trees report
an atomic `UnsupportedError` at `RAISE` before property ordering or text
emission. Valid parser-produced property lists are copied and sorted for
canonical output without mutating the public tree, and Q05's embedded-property
foreign-dialect boundary remains unchanged.

Table drops complete the same lifecycle pattern with a split representation.
Single-target `DROP TABLE` remains canonical `exp.Drop` because SQLGlot
preserves `IF EXISTS`, up-to-three-part qualification, and `CASCADE` exactly,
while a comma-separated list uses the atomic `DropTables` root because the
canonical `Drop.expressions` generator renders secondary targets in malformed
parentheses. The 26.2 grammar documents only prefix `IF EXISTS` (scoped over
the whole list) and one trailing `CASCADE`, so `RESTRICT`, `PURGE`,
`TEMPORARY`, `MATERIALIZED`, and `ICEBERG` fail closed at parse time, and the
Vertica generator rejects the same foreign modifier fields on canonical trees
with `UnsupportedError` instead of emitting undocumented Vertica. Target
names share the sibling DROP families' component validation (128-byte UTF-8
limits and unquoted-ASCII keyword provenance for `CASCADE`/`RESTRICT`);
catalog existence, dependency effects, and temporary-table auto-drop
semantics remain server concerns.

Ordinary column- and table-constraint grammar is rebuilt as an explicit
allowlist rather than inherited wholesale from Postgres: `CONSTRAINT_PARSERS`
lists only the keywords the 26.2 column-constraint and table-constraint pages
document, so an omitted keyword (Postgres `MATCH`, `DEFERRABLE`, `INCLUDE`,
`GENERATED ... AS IDENTITY`, `CHARACTER SET`, `EXCLUDE`, `PERIOD`, and similar)
fails through a natural leftover-token `ParseError` instead of silently
parsing. `AUTO_INCREMENT`/`IDENTITY` use a dedicated `VerticaIdentityColumnConstraint`
for their positional `(start, increment, cache-size)` arguments and exact
spelling, because the canonical `AutoIncrementColumnConstraint`/
`GeneratedAsIdentityColumnConstraint` pair has no slot for cache size and
generates Postgres's unrelated `GENERATED ... AS IDENTITY` syntax.
`SetUsingColumnConstraint` and `DefaultUsingColumnConstraint` model
`SET USING expr` and `DEFAULT USING expr`, which have no canonical equivalent.
`PRIMARY KEY`/`UNIQUE`/`CHECK` reuse their canonical nodes when no `ENABLED`/
`DISABLED` marker is written, keeping bare constraints portable to other
dialects; once a marker is present, parsing switches to a detached
`VerticaPrimaryKeyColumnConstraint`/`VerticaUniqueColumnConstraint`/
`VerticaPrimaryKey`/`VerticaCheckColumnConstraint`, per the canonical-subclass
foreign-dispatch hazard described under AST policy above: `exp.CheckColumnConstraint.enforced`
already means MySQL `[NOT] ENFORCED`, and SQLite's structural `isinstance`
rewrite of `exp.PrimaryKey` is the concrete case that proved detachment was
necessary rather than hypothetical. Table-level `PRIMARY KEY`/`FOREIGN KEY`/
`UNIQUE`/`CHECK` dispatch (bare or `CONSTRAINT`-named) is a single custom
`_parse_constraint` override that accepts exactly one of the four kinds, so a
named constraint can no longer bundle multiple kinds under one name the way
the inherited generic dispatch allowed. Column-level `CONSTRAINT name` is
accepted only before `CHECK`, `PRIMARY KEY`, `REFERENCES`, or `UNIQUE`, per the
documented naming rule; column-level `REFERENCES` cannot exceed one referenced
column, distinguishing it from table-level `FOREIGN KEY`'s multi-column form
that reuses the same reference-clause parser. A same-statement structural pass
enforces that column definitions precede table constraints, at most one
`PRIMARY KEY` and one `AUTO_INCREMENT`/`IDENTITY` column exist per table,
`AUTO_INCREMENT`/`IDENTITY` is absent from temporary tables, `DEFAULT`/
`SET USING` are not repeated and `DEFAULT USING` is not combined with either,
and `DEFAULT`/`SET USING`/`DEFAULT USING` expressions contain at most one
top-level SELECT statement with no subquery at all in a temporary table.
Enforcing these same-statement rules at every error level required correcting
a latent defect in the pre-existing CREATE TABLE definition/CTAS/LIKE
dispatch, which called the plain, level-dependent `raise_error` immediately
before an `assert ... is not None`; at `RAISE`,
`WARN`, and `IGNORE` levels this could reach the assert without having raised
and crash with `AssertionError` instead of `ParseError`. Those call sites now
use the same guaranteed-raise wrapper pattern established for other statement
families. The re-opened 26.2 column-constraint page's own formal grammar has
an internal inconsistency: `[ { PRIMARY KEY [ ENABLED | DISABLED ] REFERENCES
table [( column )] } ]` is missing the `|` that separates `PRIMARY KEY` from
`REFERENCES` as alternatives everywhere else in the same production (compare
the table-constraint page's clean `{ A | B | C | D }` alternation); the parser
treats them as separate, independently optional column-constraint pieces,
consistent with the surrounding prose and every worked example, and this
contradiction is recorded rather than silently resolved. Referential
existence, type compatibility (including collection-typed key columns),
same-database name uniqueness, unspecified enforcement state, dependency
effects, and CHECK expression content restrictions (subqueries, aggregates,
window functions, meta-functions, epoch-column and other-table references,
and the Boolean-return requirement, all catalog- or volatility-dependent)
remain catalog/server concerns.

Directed-query statements use atomic custom roots because SQLGlot has no
canonical SAVE/GET/CREATE/activation lifecycle. Their input SELECTs and WHERE
filters remain ordinary traversable query children. `DirectedConstantHint`
similarly wraps the complete annotated value and propagates its child's type;
the directive and optional pairing index are typed children rather than
comment text. Table partition changes and standalone reorganization subclass
`exp.Alter`, retain a real table target and partition-property child, and fail
closed for mixed action lists until SQLGlot has a lossless general multi-action
ALTER representation.

SQLGlot's type-annotation dispatch is exact-class based. Every custom scalar
subclass consequently has an explicit entry in `Vertica.EXPRESSION_METADATA`;
inheriting from a typed canonical node is not enough.

## Optimizer safety

`TIMESERIES` is query-defining rather than a disposable SELECT argument. A
query carrying the clause is represented as `TimeseriesSelect`, an
`exp.Select` subclass. Generic optimizer rules still recognize its query
scope, while a foreign generator that does not know Vertica fails atomically
instead of returning a query with the clause removed. References to the
generated slice column are `TimeseriesSlice` nodes, not source `exp.Column`
nodes; this lets schema qualification succeed when the source table correctly
does not contain the synthetic name and gives the slice an explicit
`TIMESTAMP` type.

The SELECT `INTO [TABLE]` clause uses the same custom-Select-root pattern for
a different structural reason. SQLGlot's base `select_sql` inspects
`SUPPORTS_SELECT_INTO` before per-node dispatch ever runs: a generator with
the flag unset (DuckDB, MySQL, and SQLite among the release-gate dialects)
pops whatever node sits in `Select.args["into"]` and regenerates the whole
statement as `CREATE [TEMPORARY] TABLE … AS …`, reading the popped node's
args directly. Typing only the clause child therefore cannot make foreign
generation atomic — the child is consumed structurally before it is ever
dispatched, silently discarding Vertica's `GLOBAL`/`LOCAL` scope and
`ON COMMIT` semantics. A query carrying the clause is instead promoted to
`SelectInto`, an `exp.Select` subclass that fails atomically abroad before
`select_sql` can run, and the clause itself is `IntoTableClause`, an
`exp.Into` subclass preserving scope, `TEMP`/`TEMPORARY` spelling, and
`ON COMMIT` exactly. The optional `TABLE` noise word is deliberately not
stored: generation always emits the fully spelled documented form. A
`TimeseriesSelect` that also carries an INTO clause keeps `TimeseriesSelect`
as its root — one atomic custom root is sufficient, and the typed clause
child still regenerates through its own transform. Canonical `exp.Into`
nodes arriving from foreign-parsed trees still render because Vertica
accepts the unscoped forms, but the Vertica generator rejects foreign-only
fields such as `UNLOGGED` with `UnsupportedError` instead of emitting
invalid Vertica.

SELECT INTO parsing also owns its complete source-position boundary. The
documented slot is immediately after the SELECT list, and `ON COMMIT` belongs
immediately after a temporary target. After the inherited SELECT/set parser
returns, a narrow remainder check recognizes only leftover `INTO` and
`ON COMMIT` families and routes them through `_raise_select_into_error`; this
closes misplaced and duplicate clauses at `WARN`/`IGNORE` without broadening
the contract into a generic SELECT trailing-token policy. The legal-slot
parser separately rejects explicit, implicit, and quoted target aliases before
they can become a truncated `SelectInto`. Column lists, temporary-only
members, target identifiers, comments, WITH/subquery/TIMESERIES composition,
and every formally admitted set-operation SELECT position retain their
existing typed contract.

`ENABLE_WITH_CLAUSE_MATERIALIZATION` uses a serialized
`MaterializedWithMarker` on each marked CTE query. This is a deliberate
SQLGlot 30.13.x invariant:

- `eliminate_subqueries` can reconstruct the surrounding `exp.With`, but it
  retains the existing CTE query subtree and therefore the marker;
- `merge_subqueries` treats a SELECT with query options as unmergeable, so a
  marked CTE is not inlined;
- the Vertica generator suppresses the internal option and reconstructs the
  single clause-level hint from the marker.

This is why the dependency remains minor-version bounded. Optimizer upgrades
must rerun the marker, scope, serialized-tree, and foreign-generation contract
tests before the SQLGlot bound is advanced.

## Parser policy

Recognized Vertica syntax is parsed structurally. A malformed or unsupported
remainder of a recognized statement raises `ParseError`; it must not silently
degrade the whole statement to `exp.Command`. Opaque command preservation is
reserved for administrative statement families that are explicitly marked
`Preserved` in the coverage matrix.

Contextual words are parsed contextually wherever possible. Vertica uses many
ordinary-looking words as clause starters, so globally reserving them can break
valid column and table names.

CREATE TABLE's definition-form-vs-CTAS-column-list disambiguation is
speculative, and this has a real consequence for error messages inside the
column/constraint grammar. `_parse_create_table` wraps its initial
`_parse_schema(...)` attempt in `_try_parse`, which temporarily forces
`ErrorLevel.IMMEDIATE`, catches any `ParseError` raised anywhere during that
attempt, and retreats to try the CTAS column-name-list grammar instead if it
fails. Any error raised while parsing a column definition or constraint —
including a precise Vertica-specific validation message — is swallowed
whenever the input does not end up looking like a valid column-definition
schema, and the CTAS fallback path's own, more generic error (or a plain
`Expecting )`) surfaces instead. Validation that runs only after the schema
has already been accepted as definition-form (everything inside
`_parse_create_table_definition` and the helpers it calls directly, as opposed
to validation embedded in the column/table-constraint parsers that
`_parse_schema` itself invokes) is not subject to this swallowing, because by
that point the speculative attempt has already committed and the real,
caller-requested `ErrorLevel` is back in effect. A new column/constraint
validation added inside the speculative region should not assume its specific
message will reach the caller; negative tests for such cases should assert
that `ParseError` is raised, not necessarily match the exact message, unless
the case has been confirmed to reach the non-speculative path. This is
inherent to the existing form-disambiguation mechanism, not a defect to fix
per statement.

CREATE TABLE parsing nevertheless fails atomically at every public parser
error level. Its complete definition/LIKE/CTAS parse runs as a narrowly scoped
`ErrorLevel.IMMEDIATE` transaction and restores the caller's configured level
in `finally`. This is necessary because the table family composes inherited
and shared SQLGlot helpers whose plain `raise_error` calls otherwise return at
WARN/IGNORE or aggregate past unsafe control flow at RAISE; malformed ON
COMMIT, CTAS name/encoding, segmentation, quota, ordering, partition, and
privilege clauses previously could be repaired silently, yield partial trees,
or reach assertions/unbound locals. The transaction is confined to CREATE
TABLE, so other CREATE families keep their own error contracts. Front-door
scope and replacement validation still goes through the dedicated table
wrapper, duplicate/contradictory scope and temporary prefixes are rejected
before generic CREATE fallback, and explicit checks close the generic CSV
helper's trailing-comma tolerance for table-definition and CTAS lists.

INSERT parsing uses the same narrowly scoped transaction pattern for a
different inherited grammar. SQLGlot's generic INSERT parser deliberately
accepts omitted `INTO`, bare `VALUES 1`, and trailing commas, and exposes
foreign prefix, target, source, and tail fields before the plugin's structural
validator runs. Vertica first requires `INTO`, then runs the inherited parse at
`ErrorLevel.IMMEDIATE` so malformed table/value helpers cannot return partial
trees at WARN/IGNORE or aggregate past unsafe code at RAISE. The caller's
configured level is restored in `finally`; a dedicated `_raise_insert_error`
wrapper then owns target/source validation, strict list provenance, and any
unconsumed INSERT tail. Consequently every recognized malformed form raises
`ParseError` at all four public error levels rather than inventing `INTO`,
normalizing a list, returning a blank-rendering `Insert`, or relying on strict
generation to reject the tree. Valid `DEFAULT VALUES`, parenthesized multi-row
`VALUES`, SELECT, and target-following WITH sources remain canonical
`exp.Insert` trees. Catalog constraint/default evaluation stays server-side.

The parser performs syntax-level validation, such as mutually exclusive COPY
options and required clause components. Restrictions that require catalog
types, server configuration, or semantic analysis are documented as
server-side restrictions and represented in a separate negative corpus rather
than guessed by the grammar.

SQLGlot 30.13 strips the `/*+` opener before storing a hint comment. Directed
constant annotations therefore use a small pure-Python `TokenizerCore`
subclass that tags real postfix plus-comments with private `str` subclasses.
This preserves unforgeable lexical provenance without changing SQLGlot's
public token/comment shape: ordinary `/*:c*/`, line comments, and even text
that resembles an internal marker remain ordinary comments. A misplaced tag
is rejected before statement parsing can consume or relocate it, and a
statement-level marker-count invariant prevents a supported postfix annotation
from disappearing in a parser path. This internal-core dependency is covered
by the same minor-version bound and must be re-audited when SQLGlot changes.

## Generator policy

Generated SQL is canonical Vertica syntax, not necessarily character-for-
character input preservation. Optional noise words and synonyms may be
normalized, but generation must preserve semantics and Vertica's required
clause order. Pretty and compact output both reparse to the same AST.

## Test policy

Each semantic feature requires:

- at least one positive AST assertion;
- compact generation and reparse equivalence;
- pretty generation and reparse equivalence for statement-level syntax;
- negative cases for required, conflicting, or misordered clauses;
- cross-dialect assertions when a canonical lowering exists;
- an explicit unsupported-generation assertion otherwise.

Package discovery is tested in a fresh interpreter that imports only SQLGlot,
so metaclass self-registration cannot mask a broken entry point. Release
verification also builds a wheel and installs it into an isolated environment.

## Runtime variants

The supported runtime is pure-Python SQLGlot. SQLGlot documents that custom
dialect subclassing may not work with the optional compiled `sqlglot[c]`
runtime, so that variant is not claimed as supported unless its own CI job and
plugin-discovery tests are added.
