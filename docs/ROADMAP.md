# Implementation roadmap

The coverage matrix records the current contract. This roadmap orders the
remaining work so that “comprehensive” stays testable instead of becoming a
single undifferentiated dialect file.

The executable, one-task-per-agent backlog is maintained in
[`AGENT_TASK_PLAN.md`](AGENT_TASK_PLAN.md). It is the source of truth for task
order, dependencies, acceptance criteria, and completion status.

Every phase keeps the same release gate: structured AST assertions, compact
and pretty round trips, dump/load stability, malformed-clause regressions,
optimizer or foreign-generation contracts where relevant, at least 90% branch
coverage, strict typing, linting, and an isolated installed-wheel smoke test.

## Milestones

As of 2026-08-16 the remaining work is ordered by two major milestones:

- **Milestone 1 — analysis parsing surface.** The first deliverable is
  parsing, analyzing, and regenerating the statement classes an analysis
  workload contains: `SELECT` queries (joins, subqueries, set operations),
  common table expressions, and temporary-table creation and cleanup — no
  database management. The completed phases already deliver most of this
  surface; parser probes verified three remaining gaps, now tasks Q01–Q03
  (scoped temporary CTAS, the `SELECT … INTO [TABLE]` clause including its
  temporary/`ON COMMIT` forms, and multi-target `DROP TABLE`), followed by
  the long-planned official query corpus (Q04), a fix making foreign
  generation of embedded Vertica table properties fail with an intended
  contract instead of raw `KeyError` (Q05, scheduled 2026-08-16 from Q01's
  completion record), the SELECT `[ AT epoch ]` historical-query prefix (Q06,
  scheduled 2026-08-17 from Q04's completion record), a guaranteed-raise fix
  for the pre-existing, structurally unrelated CTAS-only `AT EPOCH`/`AT TIME`
  snapshot property (Q07, scheduled 2026-08-17 from Q06's completion record),
  and an end-to-end acceptance gate with a lineage smoke (Q08, renumbered
  twice — 2026-08-17 from Q06, then again from Q07 — so the gate keeps the
  highest number each time). Q01 is complete: scoped temporary
  CTAS now shares the unscoped contract, including the LOCAL/`DISK_QUOTA`
  restriction extended from the definition form. Q02 is complete: the SELECT
  `INTO [TABLE]` clause is a typed contract for permanent and scoped
  temporary targets with preserved scope/spelling/`ON COMMIT` and atomic
  foreign generation. Q03 is complete: `DROP TABLE` is a deliberate family
  with ordered multi-target lists, list-scoped prefix `IF EXISTS`, one
  trailing `CASCADE`, and fail-closed rejection of undocumented modifiers.
  Q04 is complete: an official 26.2 SELECT/FROM/joined-table/WHERE/GROUP
  BY/HAVING/ORDER BY/set-operation/WITH/subquery example corpus backs the
  Generic query coverage rows, the reserved-word collision corpus was
  expanded for SELECT-family words, and the exercise surfaced two named
  residuals recorded in `COVERAGE.md`: `LIMIT ALL` is dropped at parse time
  (a pre-existing, non-Vertica-specific base-SQLGlot limit) and the SELECT
  page's own `[ AT epoch ]` prefix does not parse (now Q06). Q05 is complete:
  every `vexp` `Property` subclass, embedded in a real `Properties` list and
  generated against PostgreSQL, DuckDB, MySQL, or SQLite, now raises the same
  atomic `ValueError("Unsupported expression type <Name>")` an unregistered
  custom root already raises, at every `unsupported_level`, instead of a raw
  `KeyError`; the registered set is introspected from `sqlglot_vertica.expressions`
  rather than hand-maintained, so a future property is covered automatically.
  Q06 is complete: the SELECT statement's own `[ AT epoch ]` prefix now
  parses through a typed `AtEpochQuery` root that wraps the entire top-level
  query production (a `WITH` clause and any following `UNION`/`INTERSECT`/
  `EXCEPT` chain, not one bare `SELECT`), independent of the pre-existing
  CTAS-only `AtEpochProperty` snapshot property; malformed forms fail closed
  at every error level and foreign generation fails atomically, matching the
  `DropViews`/`DropTables` custom-root contract. That same property's value
  grammar was found, while confirming Q06 must not touch it, to crash with
  raw `UnboundLocalError` instead of `ParseError` at `WARN`/`IGNORE` on
  malformed input, scheduled as Q07. Q07 is complete: the CTAS-only
  `AtEpochProperty` value grammar's three malformed-value branches now route
  through the CTAS family's existing `_raise_create_table_error`
  guaranteed-raise wrapper instead of a plain `self.raise_error(...)` call, so
  a malformed `AT EPOCH`/`AT TIME` value in any CTAS position (permanent,
  unscoped temporary, scoped temporary) fails with `ParseError` at every error
  level; before the fix, non-`IMMEDIATE` levels instead produced three
  different raw-Python failures depending on the malformed form — silent
  acceptance of an invalid value (`AT EPOCH 1.5` at `WARN`/`IGNORE`),
  `AssertionError` (`AT TIME` with an unquoted value), or `UnboundLocalError`
  (a missing `EPOCH`/`TIME` keyword). `AtEpochProperty`'s `arg_types` and
  rendering, and the independent Q06 `AtEpochQuery` statement-level prefix,
  are unchanged. Q08 remains.
- **Milestone 2 — administration and remaining DDL.** Everything listed under
  "Remaining" in Phase 4 — flex tables and map functions, stored procedures
  and SQL-expression functions, partition maintenance, library/UDx
  alterations, and cluster, node, Eon, TLS, and cryptographic administration
  (tasks P16–P35) — is deferred until Milestone 1 is certified.

## Phase 1 — core analytical SQL and physical design

Implemented for the 0.2 rewrite:

- Vertica types, collection constructors, interval qualifiers, operators,
  timestamp semantics, datetime functions, and LISTAGG;
- source-sensitive collection, string, regex, formatting, and analytic-function
  semantics, including ordered `USING` modifiers and special window partitions;
- TIMESERIES, INTERPOLATE, MATCH, partitioned LIMIT, contextual keywords, and
  structured optimizer hints;
- exact canonical INSERT, UPDATE, DELETE, MERGE, and TRUNCATE semantics with
  strict parse/generation validation and a lineage-safe UPDATE `FROM DEFAULT`
  relation;
- semantic executable PROFILE wrappers with traversable SELECT and DML/COPY/
  MERGE children and atomic foreign failure;
- COPY, projections, definition-form tables, CTAS, LIKE, temporary tables,
  sequences, schema extensions, and view extensions;
- optimizer-safe custom ASTs and explicit unsupported foreign generation.

## Phase 2 — external data and procedures

Implemented:

- refactor COPY parsing/generation into a reusable context-aware body;
- add regular `CREATE EXTERNAL TABLE ... AS COPY` with a targetless COPY AST;
- add ordered ORC/Parquet parameter lists and external-only COPY validation;
- add external `CREATE PROCEDURE` and typed `DROP PROCEDURE` signatures;
- add Iceberg-backed external tables, including catalog-mode conflicts and
  constrained `COLUMN TYPES` overrides;
- add flexible external tables and their narrower source/parser grammar;
- protect every family with AST, compact/pretty round-trip, serialization,
  malformed-clause, and atomic foreign-generation regressions.

Catalog-aware and server-negative external-source fixtures remain an ongoing
integration concern: source-type compatibility, installed flexible parsers,
paths, and catalog credentials cannot be proved by a syntax-only dialect.

## Phase 3 — security and workload management

Implemented P0:

- extend GRANT/REVOKE for role, authentication, multi-target, routine,
  location, workload, and resource-pool forms;
- add canonical-safe CREATE/ALTER/single-target DROP ROLE and an atomic custom
  root for multi-role drops;
- add a bounded, non-secret USER lifecycle with typed account/password-expiry
  actions, ordered profile and global/subcluster resource-pool assignments,
  deterministic time/capacity limits, ALTER-only security-algorithm selection,
  ordered CREATE/ALTER search paths, isolated ALTER default-role selection,
  rename, ordered multi-target DROP, TOTP reset, value-free configuration
  clearing, a reviewed five-parameter depot SET allowlist, clause-aware
  sanitized credential rejection, and strict 128-byte identifier validation;
- add semantic PROFILE lifecycle DDL with ordered typed policy settings,
  lexical value-domain validation, ALTER reset/rename actions, and multi-drop;
- add ordered typed CREATE/ALTER/DROP RESOURCE POOL parameters, keyword
  sentinels, subcluster selectors, and syntax-level conflict validation.
- add typed classic and workload routing-rule lifecycle statements, exact
  session workload/resource-pool controls, SHOW workload commands, and the
  documented `ON ROUTING RULE` grant alias.
- add typed address-, fault-group-, and subcluster-backed LOAD BALANCE GROUP
  lifecycle statements, including every documented ALTER action and cascading
  DROP semantics.
- add typed NETWORK ADDRESS lifecycle statements with fixed-order endpoint
  creation, every rename/endpoint/state ALTER action, postfix dependency drops,
  and an explicit boundary from deprecated NETWORK INTERFACE administration.

P1:

- add the non-secret AUTHENTICATION CREATE/ALTER/DROP core with finite methods,
  structured LOCAL/HOST access, one-action enable/disable, rename, lexical
  priority, MFA/fallthrough state, and a parameter-by-parameter ALTER SET audit;
  only the closed non-secret `validate_type` and `jit_enabled` domains enter the
  AST, while credentials, arbitrary strings, and unknown values fail sanitized;
- complete structured KEY, LIBRARY, DATA LOADER, and TLS CONFIGURATION GRANT/
  REVOKE targets with exact privilege, cardinality, qualification, option, and
  cascade domains while retaining typed UDx overload signatures;
- add semantic CREATE/ALTER/DROP ACCESS POLICY lifecycle statements with
  shared row/column targets, traversable expressions, exact state/trust and
  copy/drop qualification rules, and atomic foreign failure.

## Phase 4 — maintenance and administration

Implemented catalog P0:

- semantic COMMENT ON statements for every documented catalog-object and
  routine target, including typed ownership paths and `NULL` removal;
- complete semantic VIEW lifecycle with typed owner, schema, inherited-
  privilege, and equal-cardinality multi-rename ALTER actions plus ordered
  multi-target DROP without undocumented dependency modifiers;
- complete semantic SCHEMA lifecycle with typed default-privilege, cascading
  owner, quota/reset, and equal-cardinality multi-rename ALTER actions plus
  ordered multi-target DROP with exact CASCADE/RESTRICT handling;
- semantic `CREATE`/`DROP LIBRARY` with dependency, language, and cascade
  clauses;
- a shared semantic factory specification for scalar, aggregate, analytic,
  transform, filter, parser, and source UDx registration;
- explicit empty, named, and typed UDx drop signatures plus documented
  language and fenced-mode validation.
- semantic directed-query SAVE/GET/CREATE/ACTIVATE/DEACTIVATE/DROP statements,
  export metadata, and typed constant annotations with lexical provenance;
- semantic standalone table reorganization and partition-definition changes,
  including the valid metadata-only form without a `REORGANIZE` suffix;
- documented ordinary column/table constraint grammar: typed `ENABLED`/
  `DISABLED` enforcement on `PRIMARY KEY`/`UNIQUE`/`CHECK`, `AUTO_INCREMENT`/
  `IDENTITY` with positional arguments, `SET USING`/`DEFAULT USING`,
  column-definition-before-table-constraint ordering, `CONSTRAINT`-name
  eligibility, single-column `REFERENCES`, and same-statement cardinality/
  temporary-table/single-SELECT restrictions, with CHECK expression content
  left as a named server-side residual.

Remaining (all Milestone 2, deferred behind the Milestone 1 analysis-surface
tasks Q01–Q07):

- partition move/swap/archive operations and mixed comma-separated ALTER action
  lists (top-level maintenance SELECT functions are already canonical);
- Flex-table and map-specific DDL;
- stored procedures, SQL-expression functions, and ALTER UDx/library lifecycle;
- cluster, node, fault-group, Eon, and storage-location administration.

Administrative families are promoted from opaque preservation only when an
analysis use case justifies a stable AST. Catalog-aware validity remains a
server concern and is recorded as server-negative coverage rather than guessed
by the parser.
