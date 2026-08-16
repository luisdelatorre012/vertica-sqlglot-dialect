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
- Added exact canonical INSERT, UPDATE, DELETE, MERGE, and TRUNCATE TABLE
  semantics, including both MERGE filter spellings, strict foreign-clause
  rejection, and a lineage-safe UPDATE `FROM DEFAULT` relation.
- Added structured CREATE PROJECTION and CREATE TABLE physical design.
- Added semantic CTAS, LIKE, global/local temporary tables, historical
  snapshots, inherited privileges, encodings, segmentation, and quotas.
- Added semantic CREATE/ALTER/DROP SEQUENCE, CREATE SCHEMA extensions, and
  CREATE VIEW extensions with ordered and conflicting-clause validation.
- Added semantic role lifecycle DDL and typed CREATE/ALTER/DROP RESOURCE POOL
  statements with subcluster selectors and parameter-domain validation.
- Added a bounded non-secret USER lifecycle: CREATE account lock/unlock or
  password expiry, one-action ALTER rename/account/expiry, and ordered
  multi-user DROP with postfix `IF EXISTS` and `CASCADE`. Credential-bearing
  forms fail with sanitized errors and secret values never enter the AST.
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
