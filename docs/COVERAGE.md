# Vertica SQL coverage matrix

This matrix is the definition of “comprehensive” for the project. It targets
the [OpenText Analytics Database 26.2 SQL reference](https://docs.vertica.com/26.2.x/en/sql-reference/)
and SQLGlot 30.13.x. A status is advanced only with AST and round-trip
regressions.

Status meanings:

- **Semantic** — parsed into traversable canonical or plugin AST nodes and
  generated as valid Vertica SQL.
- **Generic** — inherited SQLGlot behavior is suitable and protected by
  Vertica-specific regressions.
- **Partial** — the major grammar is semantic, with named gaps below.
- **Preserved** — retained as an opaque command; clauses are not traversable.
- **Planned** — no supported contract yet.

## Lexical and expression surface

| Feature | Status | Regression surface and remaining work |
| --- | --- | --- |
| Quoted/unquoted identifiers and three-part names | Generic | Core query, projection, COPY, and table fixtures; reserved-word collision corpus is being expanded |
| Comments and optimizer hints | Partial | SELECT, WITH, table, JOIN, EXPLAIN, INSERT/UPDATE/DELETE/MERGE, and COPY hints are structured with exact-placement regressions; directed-query constant annotations are typed postfix wrappers with tokenizer provenance and fail-closed placement checks; ordinary comments remain best-effort |
| String, numeric, Boolean, NULL, binary, and heredoc literals | Generic | COPY additionally covers `E'…'` record terminators |
| Numeric, comparison, Boolean, bitwise, and concatenation operators | Semantic | Includes numeric `/`, integer `//`, prefix/postfix factorial, `@`, `|/`, and `||/` |
| Scalar and temporal types | Semantic | Vertica aliases, `TIMETZ`, `TIMESTAMPTZ`, long character/binary values |
| `ARRAY`, `SET`, and `ROW` types | Semantic | Nested types, bounds, binary-size limits, anonymous and named ROW fields |
| `ARRAY`, `SET`, and `ROW` constructors | Semantic | Inner and outer ROW field aliases and zero-based array access |
| Interval literals and datatypes | Semantic | Unit spans, SECOND precision, keyword precision, and `INTERVALYM` |
| Standard casts and PostgreSQL-style `::` casts | Generic | Vertica type mappings applied during generation |
| Statement and transaction timestamps | Semantic | `GETDATE`, `GETUTCDATE`, and `SYSDATE` are distinct from `CURRENT_TIMESTAMP` |
| Date delta and slicing functions | Semantic | Dynamic date-part expressions, `DATEDIFF`, `TIMESTAMPADD`, `TIME_SLICE`, day functions |
| Function-call modifiers | Semantic | Ordered and parameter-only `USING PARAMETERS`; trailing `USING CHARACTERS` / `USING OCTETS`; malformed structure is rejected while parameter names and server semantics remain catalog-validated |
| Collections, strings, regex, and conversion functions | Semantic | Distinct `EXPLODE`/`UNNEST`, one-argument `ARRAY_LENGTH`, exact `FILTER`, modifier-preserving `REGEXP_LIKE`, extended `INSTR`, Vertica `TO_HEX`/`SHA1`/`INSERT`, one-argument `TO_CHAR`/`TO_NUMBER`, and NULL-propagating `GREATEST`/`LEAST` |
| `LISTAGG` | Semantic | Documented `USING PARAMETERS` plus conventional two-argument AST interoperability |
| Other scalar, aggregate, and analytic functions | Generic | Unknown calls remain traversable `exp.Anonymous` nodes; named semantic differences are promoted as discovered |

## Query and DML statements

| Feature | Status | Regression surface and remaining work |
| --- | --- | --- |
| `SELECT`, joins, subqueries, CTEs, set operations | Generic | Canonical SQLGlot AST; additional official-example corpus planned |
| Window functions and ordered aggregates | Partial | In-parentheses value-function null treatment and `PARTITION BEST`/`NODES`/`ROW`/`LEFT JOIN` are semantic; Vertica NULL default ordering is type-dependent and cannot be inferred without schema types |
| `TIMESERIES` | Partial | Clause and TS null-treatment syntax are semantic; server-only projection/GROUP/HAVING and interval restrictions remain documented negatives |
| Event-series `INTERPOLATE` joins | Partial | Predicate syntax is semantic; join-location and single-predicate semantic restrictions remain |
| `MATCH` event patterns | Partial | Partition/order/DEFINE/pattern/row mode and regex text are semantic; duplicate/undefined-event and query-shape validation remain |
| Partitioned `LIMIT … OVER` | Semantic | Optimizer-visible `exp.Limit` subclass; `PARTITION BY` and `ORDER BY` required |
| Ordinary `LIMIT`, `OFFSET`, and `FETCH` | Generic | `LIMIT ALL` spelling is not guaranteed to be lossless |
| `INSERT` | Semantic | Canonical `exp.Insert`; mandatory `INTO`, table/column targets, `DEFAULT VALUES`, multi-row `VALUES`, query and target-following `WITH` sources, labels, and conflicting foreign clauses are validated |
| `UPDATE` | Semantic | Canonical `exp.Update`; aliases, column aliases, `DEFAULT`, joins, `FROM`, and predicates are preserved; SET subqueries and foreign tail clauses are rejected; `FROM DEFAULT … JOIN` uses a non-table relation leaf |
| `DELETE` | Semantic | Canonical `exp.Delete`; labels and subquery predicates are preserved while aliases, joined/`USING` targets, leading `WITH`, `RETURNING`, ordering, and limits are rejected |
| `MERGE` | Semantic | Canonical `exp.Merge` plus the existing hinted subtype; required clauses, table/subquery sources, aliases, branch cardinality/actions, pre-`THEN` and trailing `WHERE` filters, and unqualified target columns are validated |
| `TRUNCATE TABLE` | Semantic | Canonical single-target `exp.TruncateTable`; required `TABLE` and exact Vertica grammar are enforced without accepting database, identity, partition, cluster, cascade, or multi-target extensions |

## Data definition and loading

| Feature | Status | Regression surface and remaining work |
| --- | --- | --- |
| `CREATE PROJECTION` / `DROP PROJECTION` | Semantic | Columns, grouped columns, encoding/access rank, query order, segmentation, node sets, offset, K-safety |
| Definition-form `CREATE TABLE` | Semantic | Encoding/access rank, physical order, segmentation, K-safety, partition grouping/count, inherited privileges, quota |
| `CREATE TABLE AS`, `LIKE`, temporary tables | Semantic | CTAS hints/snapshots, column lists and encodings, segmentation/quota, projection-copy options, scope, commit behavior, and `NO PROJECTION` |
| Ordinary column/table constraints | Generic | Vertica-specific constraint restrictions need a larger negative corpus |
| `COPY` target columns and options | Semantic | Filler columns, transforms, per-column and `COLUMN OPTION` parameters, including duplicate/order/conflict validation |
| `COPY` file/STDIN sources | Semantic | Local/server paths, compression, node selection, partition columns |
| `COPY FROM VERTICA` and UDL pipelines | Semantic | Source/filter/parser functions represented structurally |
| `COPY` formats and error handling | Semantic | Native, native-varchar, fixed-width, keyed ORC/Parquet parameters, file filters/parsers, rejection destinations, collection parameters, and load modes |
| External tables and external procedures | Semantic | Regular and flexible `CREATE EXTERNAL TABLE … AS COPY`, Iceberg-backed external tables, external `CREATE PROCEDURE`, and typed `DROP PROCEDURE` use dedicated ASTs with context-specific validation |
| Libraries and factory-backed UDx catalog DDL | Semantic | `CREATE`/`DROP LIBRARY` and scalar, aggregate, analytic, transform, filter, parser, and source UDx registration use atomic ASTs; ordered factory clauses, explicit drop signatures, and language/fence restrictions are validated |
| Named sequences | Semantic | Ordered CREATE/ALTER behavior options, explicit `NO` forms, restart/rename/schema/owner actions, and multi-object DROP; catalog-dependent numeric consistency remains server validation |
| `CREATE SCHEMA` | Partial | Authorization, default privilege inheritance, namespace-qualified names, and quota are semantic; compound schema transactions containing embedded DDL/GRANT sub-statements remain planned |
| `CREATE VIEW` | Semantic | Replacement, explicit column names, schema-qualified names, inherited privileges, and query bodies |
| Flex tables and map-specific DDL | Planned | Map functions currently parse generically |

## Security, administration, and physical maintenance

| Feature | Status | Notes |
| --- | --- | --- |
| Object `GRANT` / `REVOKE` | Semantic | Canonical single-target grants, multi-object and all-in-schema targets, `EXTEND`, routine signatures, locations, resource-pool subclusters, grant options, and cascade semantics |
| Role and authentication `GRANT` / `REVOKE` | Semantic | Compound role/grantee lists, admin-option revocation, cascade, and authentication associations use dedicated AST nodes |
| Role lifecycle | Semantic | Canonical `CREATE`, rename, and single-target `DROP`; atomic custom AST for comma-separated drops; exact unqualified-name and option validation |
| User, profile, and authentication lifecycle | Planned | Security assignment is semantic; lifecycle `CREATE`/`ALTER`/`DROP` dispatch remains a separate phase |
| Resource-pool lifecycle | Semantic | Ordered typed parameters, `DEFAULT`/`NONE`/`AUTO`/`HOLD` sentinels, named/current subcluster selectors, and CREATE/ALTER/DROP restrictions use dedicated AST roots |
| Workload routing | Semantic | Classic address/group and workload/subcluster `CREATE ROUTING RULE`, every documented ALTER action, named/workload DROP targets, exact session workload/resource-pool assignment, both SHOW workload forms, and `ON ROUTING RULE` privilege alias normalization use typed ASTs with atomic foreign failure |
| Partition maintenance and tuple mover commands | Partial | Standalone `ALTER TABLE … REORGANIZE` and partition-definition changes with optional `GROUP BY`, `SET ACTIVEPARTITIONCOUNT`, and `REORGANIZE` use typed ASTs; mixed comma-separated ALTER action lists fail closed; move/swap/archive operations remain planned, while documented top-level management functions stay canonical SELECT calls |
| Directed queries | Semantic | `SAVE QUERY`, `GET DIRECTED QUERY`, and OPT/OPTIMIZER/CUSTOM creation (including export metadata) use traversable ASTs; ACTIVATE accepts name/WHERE, DEACTIVATE accepts name/query/WHERE, and DROP accepts name/WHERE; `:c`, `:v(n)`, and `IGNORECONST(n)` annotations preserve exact postfix ownership and fail atomically outside Vertica |
| Cluster, node, fault-group, and Eon administration | Preserved | Opaque preservation is intentional until an analysis use case is defined |
| Stored procedures and SQL-expression functions | Planned | Bodyless factory UDxs are semantic; PL/vSQL bodies and SQL-function `BEGIN RETURN …; END` need delimiter- and statement-boundary-aware parsing |

## Known semantic boundaries

Some rules require information that a syntax-only dialect does not have:

- Vertica's default NULL ordering depends on the expression datatype.
- TIMESERIES, MATCH, and INTERPOLATE impose query-shape restrictions that are
  partly server semantic rather than lexical grammar.
- COPY accessibility, parser parameters, storage paths, and node names depend
  on server configuration and installed extensions.
- Library paths, dependency loading, SDK compatibility, factory availability,
  exported UDx signatures, and schema/library privileges require catalog and
  host state. The dialect validates only deterministic registration grammar.
- Iceberg `COLUMN TYPES` compatibility depends on the source metadata, and a
  flexible external table's custom parser compatibility depends on the
  installed UDx catalog. The dialect validates their documented syntax and
  structural restrictions but cannot validate those catalog relationships.
- Physical-design expression validity can depend on volatility and catalog
  metadata.
- DML target existence and object kind, privileges, constraints, coercions,
  defaults, projection state, source-row uniqueness, join multiplicity, locks,
  quotas, and transaction effects require catalog data or execution. The
  dialect enforces only deterministic grammar and AST-shape restrictions.
- Routing-rule CIDR validity, workload/group/subcluster existence, priority
  resolution, and session authorization require catalog or server state. The
  dialect validates exact statement shape and safe identifier representation.
- Resource-pool availability, CPU/memory relationships, built-in-pool
  mutability, subcluster connection state, and secondary-pool dependency cycles
  require server/catalog state. The dialect validates documented value domains,
  required parameter pairs, duplicate parameters, and clause order only.
- Directed-query name existence, query compatibility, optimizer-version/date
  provenance, and activation effects require the Vertica catalog. The dialect
  validates statement grammar, target cardinality, nonempty query structure,
  and constant-annotation placement only.

These boundaries are tested either with explicit syntax-negative fixtures or a
documented server-negative corpus. The parser does not pretend to perform
catalog-aware validation.
