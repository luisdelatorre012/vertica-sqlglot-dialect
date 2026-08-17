# Milestone 2 detailed task specifications (deferred)

This file holds the detailed specifications for the deferred Milestone 2
backlog — P16–P35, administration and remaining DDL. While any Milestone 1
(`Q`-series) task in [AGENT_TASK_PLAN.md](AGENT_TASK_PLAN.md) is not `DONE`,
this file is not part of the mandatory read. The status dashboard, selection
protocol, policies, and release gate remain in
[AGENT_TASK_PLAN.md](AGENT_TASK_PLAN.md); this file carries only per-task
contract text. When a P task is selected, read its entire entry here (tasks
cross-reference their neighbors' exclusions), implement under the main
plan's protocol, and append the completion record here while updating status
in the main dashboard.

Specifications, dependencies, and numbering are intentionally unchanged from
the prior plan revision; completion records and coverage notes reference
these IDs. Do not renumber tasks.

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
