# Implementation roadmap

The coverage matrix records the current contract. This roadmap orders the
remaining work so that “comprehensive” stays testable instead of becoming a
single undifferentiated dialect file.

Every phase keeps the same release gate: structured AST assertions, compact
and pretty round trips, dump/load stability, malformed-clause regressions,
optimizer or foreign-generation contracts where relevant, at least 90% branch
coverage, strict typing, linting, and an isolated installed-wheel smoke test.

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
  actions, rename, ordered multi-target DROP, sanitized credential rejection,
  and strict 128-byte identifier validation;
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

- add remaining USER account parameters plus PROFILE and AUTHENTICATION
  lifecycle statements, with a separately reviewed credential-handling policy;
- expand privilege targets for UDx, data loaders, keys, libraries, and TLS
  configurations.

## Phase 4 — maintenance and administration

Implemented catalog P0:

- semantic `CREATE`/`DROP LIBRARY` with dependency, language, and cascade
  clauses;
- a shared semantic factory specification for scalar, aggregate, analytic,
  transform, filter, parser, and source UDx registration;
- explicit empty, named, and typed UDx drop signatures plus documented
  language and fenced-mode validation.
- semantic directed-query SAVE/GET/CREATE/ACTIVATE/DEACTIVATE/DROP statements,
  export metadata, and typed constant annotations with lexical provenance;
- semantic standalone table reorganization and partition-definition changes,
  including the valid metadata-only form without a `REORGANIZE` suffix.

Remaining:

- partition move/swap/archive operations and mixed comma-separated ALTER action
  lists (top-level maintenance SELECT functions are already canonical);
- Flex-table and map-specific DDL;
- stored procedures, SQL-expression functions, and ALTER UDx/library lifecycle;
- cluster, node, fault-group, Eon, and storage-location administration.

Administrative families are promoted from opaque preservation only when an
analysis use case justifies a stable AST. Catalog-aware validity remains a
server concern and is recorded as server-negative coverage rather than guessed
by the parser.
