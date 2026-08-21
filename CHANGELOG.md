# Changelog

## 0.2.0 — unreleased

This is a from-scratch rewrite of the 0.1.x package around SQLGlot's dialect
plugin interface.

- Added entry-point discovery and a bounded SQLGlot 30.13.x compatibility
  contract.
- Added tested CPython 3.14 and 3.15 prerelease compatibility, including
  prerelease-aware CI and installed-wheel smoke coverage for both runtimes.
- Added stable Vertica AST nodes for syntax that cannot be represented by the
  canonical SQLGlot tree without semantic loss.
- Added native ARRAY, SET, ROW, and qualified INTERVAL parsing and generation.
- Added Vertica timestamp, datetime, LISTAGG, and mathematical-operator
  semantics.
- Added ordered generic `USING PARAMETERS`, string character/octet units,
  source-exact collection/regex/conversion functions, in-call analytic NULL
  treatment, and special window partition modes.
- Added TIMESERIES, INTERPOLATE, MATCH, and partitioned LIMIT query clauses.
- Added source-ordered multilevel `GROUP BY` ASTs that preserve arbitrary
  interleaving and repetition of ordinary expressions, `ROLLUP`, `CUBE`, and
  `GROUPING SETS`, plus typed `GBYTYPE(HASH|PIPE)` hints and strict rejection
  of inherited foreign grouping modifiers.
- Enforced Vertica's canonical set-operation contract: `UNION` supports
  default/explicit DISTINCT and `ALL`, while `INTERSECT`, `EXCEPT`, and
  canonicalized `MINUS` reject `ALL` and inherited name-matching modifiers in
  source and programmatic trees.
- Enforced SELECT qualifier and tail grammar: only `ALL`/`DISTINCT`, ordinary
  integer/JDBC-placeholder `LIMIT`/`OFFSET`, deliberate `LIMIT ALL`
  canonicalization, and `FOR UPDATE [OF ...]` survive; TOP, FETCH, foreign row
  options, lock strengths/waits, invalid ordering, and malformed AST fields
  fail atomically.
- Enforced joined-table grammar and strict canonical Join validation:
  documented INNER/outer/NATURAL/CROSS/comma forms preserve ON/USING,
  TABLESAMPLE, and structured hints, while missing/forbidden predicates,
  ASOF/STRAIGHT joins, and foreign programmatic fields fail atomically;
  validated SEMI/ANTI/APPLY inputs retain explicit equivalence lowerings.
- Made SELECT `AT epoch` historical queries directly analyzer-safe with
  concrete SELECT/UNION/INTERSECT/EXCEPT query subclasses, preserving scope,
  qualification, optimization, source expansion, lineage, serialization, and
  atomic foreign-generation contracts without caller-side unwrapping.
- Added exact canonical INSERT, UPDATE, DELETE, MERGE, and TRUNCATE TABLE
  semantics, including both MERGE filter spellings, strict foreign-clause
  rejection, and a lineage-safe UPDATE `FROM DEFAULT` relation.
- Added semantic executable PROFILE wrappers whose SELECT, INSERT, UPDATE,
  DELETE, COPY, and MERGE statement children remain fully traversable, while
  unsupported bodies and foreign generation fail atomically.
- Added structured CREATE PROJECTION and CREATE TABLE physical design.
- Added semantic CTAS, LIKE, global/local temporary tables, historical
  snapshots, inherited privileges, encodings, segmentation, and quotas.
- Added semantic CREATE/ALTER/DROP SEQUENCE plus complete SCHEMA and VIEW
  lifecycles with typed metadata actions, equal-cardinality multi-renames,
  ordered multi-target drops, exact schema dependency policies, and strict view
  dependency-modifier rejection. Compound CREATE SCHEMA bodies remain
  fail-closed and separately planned.
- Added semantic role lifecycle DDL and typed CREATE/ALTER/DROP RESOURCE POOL
  statements with subcluster selectors and parameter-domain validation.
- Added a bounded non-secret USER lifecycle: ordered CREATE/ALTER account-state,
  password-expiry, profile, global/subcluster resource-pool, time/capacity, and
  scoped connection settings; ALTER-only security-algorithm selection; isolated
  ALTER rename and default-role selection; ordered CREATE/ALTER search paths;
  and ordered multi-user DROP with postfix `IF EXISTS` and `CASCADE`.
  Credential-bearing forms fail with clause-aware sanitized errors and secret
  values never enter the AST.
- Added isolated `TOTPSECRET RESET`, typed value-free USER configuration clears,
  and a five-parameter depot-only SET allowlist; unknown and unsafe values are
  rejected by the credential sanitizer before entering an AST.
- Added semantic CREATE/ALTER/DROP PROFILE lifecycle with all 15 ordered
  password-policy metadata settings, lexical numeric domains, `UNLIMITED`,
  ALTER-only `DEFAULT` resets, rename, multi-target drop, and strict foreign
  generation failure. User assignment and catalog effects remain server-side.
- Added semantic non-secret CREATE/DROP AUTHENTICATION with finite method
  validation, structured LOCAL/HOST TLS access, MFA/fallthrough flags,
  single-target cascading drops, and sanitized rejection of excluded ALTER SET
  values before they enter an AST.
- Added one-action semantic ALTER AUTHENTICATION for enable/disable, LOCAL/HOST
  TLS access, rename, finite methods, lexical nonnegative priority, Boolean MFA
  state, and fallthrough state.
- Added ordered typed ALTER AUTHENTICATION SET for the audited finite
  `validate_type` and `jit_enabled` domains. Explicit secrets, arbitrary-string
  parameters, unknown names, and nonstandard literal forms remain behind the
  fixed pre-AST sanitizer.
- Completed structured KEY, LIBRARY, DATA LOADER, and TLS CONFIGURATION GRANT/
  REVOKE targets with exact privilege, target-cardinality, qualification,
  grant-option, EXTEND, cascade, identifier, and foreign-generation contracts;
  existing factory-UDx overload signatures remain typed and unchanged.
- Added semantic CREATE/ALTER/DROP ACCESS POLICY lifecycle statements with
  shared row/column targets, traversable policy expressions, expression/state
  modification and COPY actions, strict qualification and identifier checks,
  and atomic foreign-generation failure.
- Completed documented ordinary column/table constraint grammar: typed
  `ENABLED`/`DISABLED` enforcement on `PRIMARY KEY`/`UNIQUE`/`CHECK` using
  detached Vertica nodes so foreign generators fail atomically instead of
  reinterpreting or dropping the marker; `AUTO_INCREMENT`/`IDENTITY` with
  positional start/increment/cache-size arguments; `SET USING`/`DEFAULT USING`;
  an explicit allowlisted column-constraint grammar in place of the inherited
  Postgres superset; exclusive single-kind table-constraint dispatch;
  column-definition-before-table-constraint ordering; `CONSTRAINT`-name
  eligibility; single-column `REFERENCES`; and same-statement cardinality,
  temporary-table, and single-SELECT restrictions. Also fixed a latent
  `AssertionError` crash (instead of `ParseError`) in the CREATE TABLE
  definition/CTAS/LIKE dispatch at `RAISE`/`WARN`/`IGNORE` error levels.
- Added semantic classic and workload routing-rule lifecycle, every documented
  ALTER action, exact session workload/resource-pool assignment, SHOW workload
  controls, and canonical `ON ROUTING RULE` privilege alias handling.
- Added semantic CREATE/ALTER/DROP LOAD BALANCE GROUP for address, fault-group,
  and subcluster membership, typed filters and selection policies, every ALTER
  action, cascading drops, and atomic foreign-generation failure.
- Added semantic CREATE/ALTER/DROP NETWORK ADDRESS with fixed-order endpoint
  specifications, every documented ALTER action, cascading drops, opaque
  IPv4/IPv6/hostname values, Unicode-aware identifiers, and atomic foreign
  failure while retaining NETWORK INTERFACE as an opaque command family.
- Added semantic CREATE/DROP LIBRARY and shared factory-backed scalar,
  aggregate, analytic, transform, filter, parser, and source UDx catalog DDL,
  including language/fence validation and explicit typed drop signatures.
- Added semantic COMMENT ON statements for aggregate, analytic, scalar, and
  transform functions, columns, constraints, libraries, nodes, projections,
  schemas, sequences, tables, and views, including typed routine/ownership
  targets and `NULL` comment removal.
- Added structured COPY targets, sources, formats, parser pipelines, error
  handling, and validation.
- Added semantic regular external tables backed by targetless COPY definitions,
  keyed ORC/Parquet options, external executable procedure creation, and typed
  procedure drops.
- Added semantic Iceberg external tables with ordered catalog modes and
  constrained metadata type overrides, plus flexible external tables with a
  dedicated narrowed COPY context and mandatory parser validation.
- Hardened COPY and external-procedure dispatch so explicit empty lists fail
  instead of disappearing and quoted `USER` identifiers cannot be mistaken for
  external-procedure clauses.
- Added optimizer-hint placement support.
- Added semantic directed-query SAVE/GET/CREATE/ACTIVATE/DEACTIVATE/DROP
  statements, export metadata, and typed postfix `:c`, `:v(n)`, and
  `IGNORECONST(n)` annotations with non-forgeable tokenizer provenance.
- Added semantic standalone `ALTER TABLE … REORGANIZE` and partition-definition
  changes with optional grouping, active-partition counts, and reorganization;
  unsupported mixed ALTER action lists fail closed.
- Added atomic foreign-generation failures, custom scalar type inference,
  optimizer-safe TIMESERIES slice columns, and materialized-CTE barriers.
- Added a versioned coverage matrix, architecture contract, primary-source
  index, strict typing/linting, multi-version CI, coverage gates, and isolated
  wheel discovery and custom-AST smoke tests.
- Added frozen, cross-platform pre-commit hooks for repository hygiene, syntax
  and secret checks, Ruff, strict mypy, and Conventional Commit messages, with
  matching Linux and Windows CI enforcement and mandatory agent policy.
- Added scoped (`GLOBAL`/`LOCAL`) temporary `CREATE TABLE AS` with exactly the
  unscoped contract: column lists, `ON COMMIT`, hints, parenthesized query
  bodies, and the LOCAL/`DISK_QUOTA` restriction extended from the definition
  form. Recorded a pre-existing, cross-cutting gap where custom Vertica table
  `Property` classes raise `KeyError` rather than `UnsupportedError` in
  foreign generation once embedded in a real `Properties` list.
- Added the documented SELECT `INTO [TABLE]` clause as a typed contract:
  permanent and `[GLOBAL | LOCAL] TEMP[ORARY]` targets with preserved scope,
  `TEMP`/`TEMPORARY` spelling, and `ON COMMIT` state, deliberate
  always-regenerated `TABLE` keyword canonicalization, fail-closed rejection
  of PostgreSQL `STRICT`/`UNLOGGED`/variable-list forms and malformed tails at
  every error level, and atomic foreign generation in place of SQLGlot's
  silent `SUPPORTS_SELECT_INTO` CTAS rewrite.
- Completed the documented `DROP TABLE` grammar: comma-separated multi-target
  lists share prefix `IF EXISTS` and one trailing `CASCADE` through an atomic
  `DropTables` root (SQLGlot's canonical `Drop.expressions` generator renders
  secondary targets in malformed parentheses), single targets stay canonical
  `exp.Drop`, target names share the sibling DROP families' identifier and
  qualification contracts, and undocumented `RESTRICT`, `PURGE`, `TEMPORARY`,
  `MATERIALIZED`, and `ICEBERG` modifiers now fail closed in parsing and
  generation instead of leaking through inherited grammar.
- Backed the Generic `SELECT`/CTE grammar with an official 26.2 example
  corpus covering SELECT core clauses, `FROM`/joined-table forms, `WHERE`,
  `GROUP BY`/`ROLLUP`/`CUBE`/`GROUPING SETS`, `HAVING`, `ORDER BY`,
  `LIMIT`/`OFFSET`, `UNION`/`INTERSECT`/`EXCEPT`/`MINUS`, `WITH` (including
  plain `RECURSIVE`), and subqueries, and expanded the reserved-word
  collision corpus for SELECT-family words. Recorded two named residuals:
  `LIMIT ALL` is discarded at parse time (a pre-existing, non-Vertica-specific
  base-SQLGlot limit), and the SELECT page's own `[ AT epoch ]`
  historical-query prefix does not yet parse.
- Closed the cross-cutting gap recorded above where embedding a custom
  Vertica table `Property` in a real `Properties` list raised raw `KeyError`
  in foreign generation: PostgreSQL, DuckDB, MySQL, and SQLite generators now
  raise `ValueError("Unsupported expression type <Name>")` for every
  Vertica-only property at every `unsupported_level`, matching the atomic
  contract every other custom Vertica root already gives, while canonical
  properties and non-Vertica `Property` subclasses keep today's behavior
  unchanged.
- Closed the residual recorded above where the SELECT statement's own
  `[ AT epoch ]` historical-query prefix did not parse: a typed `AtEpochQuery`
  root now covers `EPOCH LATEST`, `EPOCH <integer>`, and `TIME '<timestamp>'`,
  wrapping the complete top-level query production (an optional `WITH` clause
  and any following `UNION`/`INTERSECT`/`EXCEPT` chain, not one bare
  `SELECT`), independent of the pre-existing, structurally unrelated
  CTAS-only `AtEpochProperty` snapshot property. Malformed forms fail closed
  at every error level through a dedicated guaranteed-raise wrapper, and
  foreign generation fails atomically, matching the `DropViews`/`DropTables`
  custom-root contract.
- Fixed the pre-existing, structurally unrelated CTAS-only `AT EPOCH`/
  `AT TIME` historical-snapshot property (`AtEpochProperty`): its three
  malformed-value branches now route through the CTAS family's existing
  guaranteed-raise wrapper, so a malformed value fails with `ParseError` at
  every error level and CTAS position (permanent, unscoped temporary, scoped
  temporary) instead of, depending on the malformed form and error level,
  silently building a property from an invalid value, raising
  `AssertionError`, or raising `UnboundLocalError`. The property's
  `arg_types`, valid-input parsing, and rendering are unchanged.
- Certified Milestone 1, the analysis parsing surface, with an end-to-end
  workload-corpus test module combining plain, recursive, and
  materialization-hinted CTEs, scoped and unscoped temporary CTAS,
  definition-form temporary tables, `INSERT ... SELECT` and
  `INSERT ... WITH`, `SELECT ... INTO` temporary targets, and multi-target
  `DROP TABLE` cleanup into realistic multi-statement analysis scripts.
  Verified `sqlglot.parse` multi-statement boundaries, compact/pretty
  round-trips, `dump()`/`load()` stability, and optimizer traversal,
  including a column-level `lineage` smoke tracing a `SELECT ... INTO`
  target's column through a temporary CTAS's own CTE down to a
  definition-form temporary table's declared schema. No new grammar was
  introduced.
