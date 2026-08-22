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
  are unchanged. Q08 is complete, certifying Milestone 1 on 2026-08-17: a
  workload-corpus test module (`tests/test_workload_corpus.py`) combines the
  statement families Q01–Q07 delivered into two realistic multi-statement
  analysis scripts — a staging pipeline (a definition-form temporary table,
  `INSERT ... SELECT`, a scoped `LOCAL` temporary CTAS built from a plain CTE,
  a `SELECT ... INTO` temporary target, and ordered multi-target `DROP TABLE`
  cleanup) and a recursive-archive pipeline (two unscoped temporary CTAS
  statements, one from a plain CTE and one from a `RECURSIVE` CTE, an
  archival `INSERT ... WITH` carrying a materialization hint, and
  `DROP TABLE ... IF EXISTS` cleanup) — and proves `sqlglot.parse`
  multi-statement boundaries, compact/pretty round-trips, `dump()`/`load()`
  stability, a comment surviving a multi-statement script boundary, and
  optimizer traversal: `qualify`/`optimize` stability plus a column-level
  `lineage` smoke that traces a `SELECT ... INTO` target's column through a
  temporary CTAS's own CTE down to a definition-form temporary table's
  declared schema. No new grammar was introduced; `docs/COVERAGE.md`'s
  SELECT/CTE, INTO TABLE, `CREATE TABLE AS`/temporary-tables, and DROP TABLE
  rows were updated with this corpus evidence, and the LIMIT/OFFSET/FETCH,
  identifier, Q05 foreign-generation, and Q06 `AtEpochQuery` rows were
  re-reviewed and left unchanged because the corpus does not exercise
  `LIMIT`/`OFFSET`/`FETCH`, new identifiers, additional foreign-dialect
  surface, or the `AT epoch` query prefix (deliberately outside this task's
  documented statement-family list). A source-backed audit on 2026-08-21
  superseded Q08's certification conclusion while preserving that positive
  corpus as historical evidence. The audit found uncovered formal-negative,
  losslessness, fail-closed, and direct-analysis blockers and scheduled
  Q09–Q25 in `AGENT_TASK_PLAN.md`; Milestone 1 is reopened until its current
  Q25 recertification gate and every preceding Q task are `DONE`. Q09 is
  complete: parser-produced `GROUP BY` clauses now use a canonical-compatible
  ordered Group subclass so ordinary expressions and repeated/interleaved
  `ROLLUP`, `CUBE`, and `GROUPING SETS` constructs regenerate in source order;
  material grouping parentheses and empty sets are retained, the documented
  `GBYTYPE(HASH|PIPE)` hint is typed, inherited foreign modifiers fail closed,
  and qualification, optimization, scope traversal, and lineage preserve the
  ordered shape. Q10 is complete: canonical set-operation trees now enforce
  Vertica's operator-specific duplicate contract (`UNION` default/DISTINCT or
  `ALL`; `INTERSECT`, `EXCEPT`, and canonicalized `MINUS` DISTINCT-only),
  reject inherited name-matching/correspondence modifiers at every parser
  error level, and validate nested/programmatic trees before generation while
  preserving left association, branch tails, analysis traversal, and lineage.
  Q11 is complete: ordinary SELECT qualifiers are restricted to omitted or
  explicit `ALL` and plain `DISTINCT`; numeric/JDBC-placeholder LIMIT and
  OFFSET tails, deliberate `LIMIT ALL` no-op canonicalization, and the sole
  `FOR UPDATE [OF ...]` lock form are validated in parsing and generation.
  TOP, FETCH, foreign limit options/lock strengths/waits, duplicate or
  misordered tails, and malformed programmatic fields fail atomically, while
  compound-query locks own the set root rather than SQLGlot's right SELECT
  branch. Q12 is complete: canonical joined-table nodes now enforce the
  documented INNER/default, LEFT/RIGHT/FULL `[OUTER]`, NATURAL (including
  formal NATURAL outer spelling), CROSS, comma, ON/USING, TABLESAMPLE, and
  structured-hint contract. Missing or forbidden predicates and inherited
  ASOF/STRAIGHT forms fail at every parser error level, strict generation
  validates every canonical Join field before preprocessing, and the bounded
  SEMI/ANTI/APPLY equivalence lowerings are explicitly classified. Q13 is
  complete: parser-emitted historical queries now use analyzer-visible
  `AtEpochSelect`/`AtEpochUnion`/`AtEpochIntersect`/`AtEpochExcept` roots, so
  ordinary scope traversal, qualification, optimization, source expansion,
  and lineage work directly on the public prefixed root with parity to the
  unprefixed query. Prefix/value, placement, serialization, and foreign-
  atomicity contracts remain strict; the old Q06 `AtEpochQuery` wrapper stays
  loadable and renderable only as a serialized-AST compatibility path. Q14 is
  complete: CTE bodies now use a SELECT/query-expression-only parser boundary
  instead of re-entering the top-level statement dispatcher; side-effecting,
  DML/DDL/admin, VALUES/bare-FROM, and AT-prefixed bodies fail at every error
  level, as do invalid outer-WITH placements and inherited per-CTE
  MATERIALIZED/USING KEY/SEARCH/CYCLE modifiers. Plain, multiple, subordinate,
  recursive, clause-materialization-hinted, set-operation, and documented
  target-following INSERT forms remain analyzable, and strict generation owns
  the complete With/CTE shape. Q15 is complete: definition, LIKE, and CTAS
  parsing now run as one CREATE TABLE-scoped fail-closed transaction, so every
  recognized malformed table clause raises `ParseError` at IMMEDIATE, RAISE,
  WARN, and IGNORE instead of normalizing, truncating, falling back to
  `Command`, or reaching a raw Python failure. Duplicate/contradictory scope
  and temporary prefixes plus trailing definition/CTAS-list commas are also
  rejected, while all valid permanent and temporary forms remain unchanged.
  Q16 is complete: INSERT now has its own guaranteed-raise parser boundary and
  an inherited-helper transaction, so missing INTO/targets/sources, malformed
  target and VALUES lists, conflicting sources, target partitions, foreign
  prefixes/tails, and leftover clauses raise `ParseError` at IMMEDIATE, RAISE,
  WARN, and IGNORE rather than normalizing input or returning a blank partial
  AST. Valid DEFAULT VALUES, multi-row VALUES, INSERT-SELECT, and the Q14
  target-following WITH form remain canonical and analyzable. Q17 is complete:
  CREATE TABLE definition/LIKE/CTAS, INSERT, permanent/temporary SELECT INTO,
  and DROP TABLE now share one source-backed one-/two-/three-part target
  contract with schema-required outer qualification, documented quoted and
  unquoted lexical rules, valid UTF-8, a 128-byte limit per component, and
  strict programmatic-AST validation before generation. Boundary tests cover
  127/128/129-byte ASCII and multibyte names, Unicode/reserved payloads,
  unpaired surrogates, empty/missing/four-part shapes, source casing, comments,
  aliases in neighboring legal positions, and all parser error levels. Q18 is
  complete: SELECT INTO now owns its documented post-select-list slot and the
  temporary target's immediate ON COMMIT tail, so misplaced/duplicate clauses,
  target aliases, permanent temporary members, and recognized incomplete
  variants fail atomically at every parser error level without returning a
  truncated plain SELECT or SelectInto. Legal WITH, nested, TIMESERIES,
  parenthesized, and set-operation compositions remain typed and analyzable.
  Q19 is complete: canonical CREATE TABLE roots are classified as definition,
  LIKE, or CTAS and structurally validated before property location, sorting,
  or text emission. The validator owns every admitted property/container,
  duplicate and mutual-exclusion rule, temporary scope/commit/quota state,
  CTAS-only and definition-only fields, and installed canonical CREATE extras;
  malformed direct and nested programmatic trees now fail atomically with
  `UnsupportedError`, while valid property ordering, foreign-parsed plain
  CREATE TABLE interoperability, target validation, query analysis, and Q05's
  embedded-property foreign contract remain stable. Q20 is complete: its
  formal-negative audit froze the installed SQLGlot field inventory,
  consolidated the Q09–Q19
  all-level negative contract, and revalidated the deliberate `ALL`/`LIMIT
  ALL`/`MINUS`, QUALIFY, SEMI/ANTI, and APPLY canonicalizations or lowerings.
  It found two distinct product gaps without changing production code. Q21 is
  complete: SELECT, set-operation, subquery, table-reference, TABLESAMPLE,
  ordering, Lateral, Pivot, and Star fields now have a whole-tree parser and
  pre-preprocessing generator closure. Undocumented WINDOW/CONNECT/LATERAL
  VIEW/PIVOT, distribution/sort/cluster, star modifiers, ordering extensions,
  table ONLY/historical-AT, and foreign sampling forms fail atomically, while
  bare numeric TABLESAMPLE and the approved APPLY lowerings remain stable.
  Q22 is complete: TIMESERIES, MATCH, and INTERPOLATE now have family-specific
  guaranteed-raise boundaries at every parser error level plus strict direct
  and nested AST validation before generation. Required interval/order,
  DEFINE/pattern/row-mode, and operand failures no longer return partial ASTs
  at `WARN`/`IGNORE`; valid comments, serialization, optimizer/type behavior,
  and foreign atomicity remain stable. The first recertification attempt on
  2026-08-22 expanded the end-to-end workload module from 8 to 68 tests and exposed
  two documented-composition blockers without changing production code. Q23
  is complete: parser-produced `FOR UPDATE OF` targets now use canonical
  identifier paths rather than selectable `Table` nodes, so scope traversal,
  qualification, optimization, and lineage no longer misclassify them as
  duplicate FROM sources across aliases, joins, subqueries/CTEs, compound
  queries, or AT-prefixed roots; lock rendering, serialization, strict
  generation, and foreign behavior remain stable. Q24 is complete:
  AT-prefixed plain/subordinate/materialization-hinted WITH queries now compose
  with parenthesized UNION/INTERSECT/EXCEPT branches carrying branch-local and
  whole-compound tails; the outer-WITH validator recognizes only true wrapper
  subqueries, and historical-root comments render from one stable owner at the
  `AT` prefix across compact and pretty cycles. Q25 is complete: the 68-test
  recertification corpus proves the Q09–Q24 surface end to end across realistic
  temporary-table workloads, including public-root qualification,
  optimization, scope traversal, raw-source lineage, all-level negative-script
  atomicity, strict AST validation, and direct/nested foreign failure. The full
  release gate passed on every supported CPython minor. Milestone 1 is
  recertified as of 2026-08-22.
- **Milestone 2 — administration and remaining DDL.** Everything listed under
  "Remaining" in Phase 4 — flex tables and map functions, stored procedures
  and SQL-expression functions, partition maintenance, library/UDx
  alterations, and cluster, node, Eon, TLS, and cryptographic administration
  (tasks P16–P35) — is now eligible after Milestone 1 recertification; P16 is
  the next task.

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

Remaining (all Milestone 2; eligible after Milestone 1 recertification):

- partition move/swap/archive operations and mixed comma-separated ALTER action
  lists (top-level maintenance SELECT functions are already canonical);
- Flex-table and map-specific DDL;
- stored procedures, SQL-expression functions, and ALTER UDx/library lifecycle;
- cluster, node, fault-group, Eon, and storage-location administration.

Administrative families are promoted from opaque preservation only when an
analysis use case justifies a stable AST. Catalog-aware validity remains a
server concern and is recorded as server-negative coverage rather than guessed
by the parser.
