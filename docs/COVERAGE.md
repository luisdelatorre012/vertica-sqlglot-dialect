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
| Quoted/unquoted identifiers and three-part names | Generic | Core query, projection, COPY, and table fixtures; reserved-word collision corpus covers MATCH/TIMESERIES/table-property words plus SELECT-family words (`AT`, `EPOCH`, `TIME`, `LATEST`, `ROLLUP`, `CUBE`, `SETS`, `GROUPING`, `OFFSET`) as column, table, and CTE identifiers |
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
| `SELECT`, joins, subqueries, CTEs, set operations | Generic | Canonical SQLGlot AST backed by an official 26.2 example corpus covering SELECT core (`ALL`/`DISTINCT`/`MATCH_COLUMNS`/`FOR UPDATE`), `FROM`/`TABLESAMPLE`/joined-table forms (`INNER`/`LEFT`/`RIGHT`/`FULL [OUTER]`/`NATURAL`/`CROSS`), `WHERE`, `HAVING`, `ORDER BY`, `UNION`/`INTERSECT`/`EXCEPT`/`MINUS`, `WITH` (plain, multiple, and plain `RECURSIVE`), and WHERE/FROM/HAVING subqueries. SELECT qualifiers are closed to omitted/explicit `ALL` and plain `DISTINCT`; `DISTINCT ON`, TOP, foreign kinds/operation modifiers, duplicate qualifiers, unsupported tail permutations, and multiple ORDER/LIMIT/OFFSET/lock clauses fail closed at every error level. `FOR UPDATE [OF table[, ...]]` is the only lock form; foreign strengths/waits fail in parsing and strict generation, and an unparenthesized compound-query lock is promoted from SQLGlot's right-branch placement to the owning set root. Set operations retain canonical left-associated trees: `UNION` supports default/explicit DISTINCT and `ALL`, while `INTERSECT`, `EXCEPT`, and canonicalized `MINUS` are DISTINCT-only; their inherited `ALL` forms and every name-matching/correspondence field fail closed in parsing and strict generation, including nested/programmatic trees, without disturbing parentheses, branch-local tails, whole-compound tails, scope traversal, qualification, optimization, or lineage. `GROUP BY` uses the canonical-compatible `VerticaGroup` subclass with one source-ordered list interleaving ordinary expressions, repeated `ROLLUP`, `CUBE`, and `GROUPING SETS` items without rebucketing; material parentheses and empty grouping sets are retained, `GROUPING_ID()` and explicit arguments remain canonical, and the documented `GBYTYPE(HASH|PIPE)` hint is typed. Inherited `GROUP BY ALL`/`DISTINCT`/`TOTALS`/`WITH ROLLUP` forms fail closed at every error level, malformed/programmatic trees are strictly rejected, and the custom node fails atomically in four foreign dialects while qualification, optimization, scope traversal, and lineage preserve it. The Milestone 1 acceptance-gate workload corpus (Q08, `tests/test_workload_corpus.py`) additionally proves plain, recursive, and materialization-hinted CTEs compose correctly inside realistic multi-statement analysis scripts spanning temporary-table CTAS, `INSERT`, and `SELECT … INTO` |
| SELECT `INTO [TABLE]` targets | Semantic | Typed `SelectInto` root with an `IntoTableClause` target preserves `GLOBAL`/`LOCAL` scope, `TEMP`/`TEMPORARY` spelling, and `ON COMMIT` exactly, and always regenerates the optional `TABLE` keyword; permanent targets accept namespace/database qualification (the two are syntactically identical and resolved server-side); PostgreSQL `STRICT`/`UNLOGGED`/variable-list forms, scope without `TEMP`, permanent `ON COMMIT`, column lists, and over-qualified names fail closed at every error level; foreign generation fails atomically instead of inheriting SQLGlot's silent `SUPPORTS_SELECT_INTO` CTAS rewrite, while foreign-parsed canonical `exp.Into` still renders for the unscoped forms Vertica accepts; the Milestone 1 acceptance-gate workload corpus (Q08) additionally exercises a temporary `INTO` target chained after a scoped temporary CTAS inside a realistic multi-statement script, including a `qualify`/`optimize` and column-level `lineage` smoke through the chain |
| SELECT `[ AT epoch ]` historical-query prefix | Semantic | Typed `AtEpochQuery` wraps the complete top-level query (`exp.Query`: a `Select` or a `UNION`/`INTERSECT`/`EXCEPT` chain, including any `WITH` clause) exactly as parsed, covering `EPOCH LATEST`, `EPOCH <integer>`, and `TIME '<timestamp>'`; independent of the structurally unrelated CTAS-only `AtEpochProperty` snapshot property, whose AST shape and rendering are unchanged (its malformed-value error handling was separately hardened — see the `CREATE TABLE AS`/temporary-tables row); missing/invalid `EPOCH`/`TIME` values and non-query trailing statements fail closed at every error level through a dedicated guaranteed-raise wrapper; foreign generation fails atomically (`ValueError`, matching the `DropViews`/`DropTables` custom-root contract) since the wrapper is never itself an `exp.Select`; `qualify`/`optimize` run without error and preserve the root, but do not fully table-qualify columns through the wrapper (identifier-quoting only) and `lineage` requires calling against `expression.this` — documented residuals, not corruption (already-qualified references are unaffected and no column is ever resolved to the wrong table) |
| Window functions and ordered aggregates | Partial | In-parentheses value-function null treatment and `PARTITION BEST`/`NODES`/`ROW`/`LEFT JOIN` are semantic; Vertica NULL default ordering is type-dependent and cannot be inferred without schema types |
| `TIMESERIES` | Partial | Clause and TS null-treatment syntax are semantic; server-only projection/GROUP/HAVING and interval restrictions remain documented negatives |
| Event-series `INTERPOLATE` joins | Partial | Predicate syntax is semantic; join-location and single-predicate semantic restrictions remain |
| `MATCH` event patterns | Partial | Partition/order/DEFINE/pattern/row mode and regex text are semantic; duplicate/undefined-event and query-shape validation remain |
| Partitioned `LIMIT … OVER` | Semantic | Optimizer-visible `exp.Limit` subclass; `PARTITION BY` and `ORDER BY` required |
| Ordinary `LIMIT`, `OFFSET`, and `FETCH` | Semantic | Canonical `Limit`/`Offset` accept nonnegative integer literals (without bounded integer conversion) and anonymous JDBC placeholders; `LIMIT ALL` deliberately canonicalizes to clause absence while preserving following tails. Both official-source relative LIMIT/OFFSET orders are accepted and canonicalize to `LIMIT … OFFSET …`; ORDER must precede either and FOR UPDATE follows. FETCH, comma-form LIMIT, PERCENT/ROW(S)/WITH TIES/BY options, negative/decimal/string/expression/named-placeholder counts, duplicates, and malformed/programmatic fields fail atomically. The independent partitioned `LIMIT … OVER` contract remains positive-integer-only with required partition and order children |
| `INSERT` | Semantic | Canonical `exp.Insert`; mandatory `INTO`, table/column targets, `DEFAULT VALUES`, multi-row `VALUES`, query and target-following `WITH` sources, labels, and conflicting foreign clauses are validated |
| `UPDATE` | Semantic | Canonical `exp.Update`; aliases, column aliases, `DEFAULT`, joins, `FROM`, and predicates are preserved; SET subqueries and foreign tail clauses are rejected; `FROM DEFAULT … JOIN` uses a non-table relation leaf |
| `DELETE` | Semantic | Canonical `exp.Delete`; labels and subquery predicates are preserved while aliases, joined/`USING` targets, leading `WITH`, `RETURNING`, ordering, and limits are rejected |
| `MERGE` | Semantic | Canonical `exp.Merge` plus the existing hinted subtype; required clauses, table/subquery sources, aliases, branch cardinality/actions, pre-`THEN` and trailing `WHERE` filters, and unqualified target columns are validated |
| Executable `PROFILE` | Semantic | A dedicated wrapper retains one traversable SELECT/set-operation, INSERT, UPDATE, DELETE, COPY, or MERGE child with hints/comments and exact batch boundaries; unsupported bodies and foreign generation fail atomically |
| `TRUNCATE TABLE` | Semantic | Canonical single-target `exp.TruncateTable`; required `TABLE` and exact Vertica grammar are enforced without accepting database, identity, partition, cluster, cascade, or multi-target extensions |

## Data definition and loading

| Feature | Status | Regression surface and remaining work |
| --- | --- | --- |
| `CREATE PROJECTION` / `DROP PROJECTION` | Semantic | Columns, grouped columns, encoding/access rank, query order, segmentation, node sets, offset, K-safety |
| Definition-form `CREATE TABLE` | Semantic | Encoding/access rank, physical order, segmentation, K-safety, partition grouping/count, inherited privileges, quota; embedded properties fail atomically in PostgreSQL/DuckDB/MySQL/SQLite generation instead of raising raw `KeyError` |
| `CREATE TABLE AS`, `LIKE`, temporary tables | Semantic | CTAS hints/snapshots, column lists and encodings, segmentation/quota, projection-copy options, scope (including scoped temporary CTAS), commit behavior, and `NO PROJECTION`; embedded properties fail atomically in PostgreSQL/DuckDB/MySQL/SQLite generation instead of raising raw `KeyError`; the CTAS-only `AT EPOCH`/`AT TIME` historical-snapshot value grammar (`AtEpochProperty`) fails closed with `ParseError` at every error level on a malformed value through the CTAS guaranteed-raise wrapper, instead of raw `UnboundLocalError`/`AssertionError`/silent acceptance; the Milestone 1 acceptance-gate workload corpus (Q08) additionally exercises scoped (`LOCAL`) and unscoped temporary CTAS, each built from a CTE, combined with definition-form temporary tables and `INSERT` in realistic multi-statement analysis scripts |
| `DROP TABLE` | Semantic | Ordered multi-target lists share prefix `IF EXISTS` and one trailing `CASCADE` through an atomic root while single targets stay canonical `exp.Drop`; names share the sibling DROP families' identifier and up-to-three-part qualification contracts; undocumented `RESTRICT`, `PURGE`, `TEMPORARY`, `MATERIALIZED`, and `ICEBERG` modifiers fail closed in parsing and generation; catalog existence, dependency effects, and temporary-table auto-drop semantics remain server concerns; the Milestone 1 acceptance-gate workload corpus (Q08) additionally exercises ordered multi-target cleanup, with and without `IF EXISTS`, as the closing statement of realistic multi-statement analysis scripts |
| Ordinary column/table constraints | Partial | `AUTO_INCREMENT`/`IDENTITY`, `SET USING`, `DEFAULT USING`, and typed `ENABLED`/`DISABLED` enforcement on `PRIMARY KEY`/`UNIQUE`/`CHECK` are semantic; column-definition vs. table-constraint order, `CONSTRAINT`-name eligibility, single-column `REFERENCES`, PRIMARY KEY/AUTO_INCREMENT cardinality, DEFAULT-family exclusivity/single-SELECT limits, and temporary-table restrictions are enforced. CHECK expression content restrictions (no subqueries, aggregates, window functions, meta-functions, epoch/other-table references) remain a server-side residual |
| `COPY` target columns and options | Semantic | Filler columns, transforms, per-column and `COLUMN OPTION` parameters, including duplicate/order/conflict validation |
| `COPY` file/STDIN sources | Semantic | Local/server paths, compression, node selection, partition columns |
| `COPY FROM VERTICA` and UDL pipelines | Semantic | Source/filter/parser functions represented structurally |
| `COPY` formats and error handling | Semantic | Native, native-varchar, fixed-width, keyed ORC/Parquet parameters, file filters/parsers, rejection destinations, collection parameters, and load modes |
| External tables and external procedures | Semantic | Regular and flexible `CREATE EXTERNAL TABLE … AS COPY`, Iceberg-backed external tables, external `CREATE PROCEDURE`, and typed `DROP PROCEDURE` use dedicated ASTs with context-specific validation |
| Libraries and factory-backed UDx catalog DDL | Semantic | `CREATE`/`DROP LIBRARY` and scalar, aggregate, analytic, transform, filter, parser, and source UDx registration use atomic ASTs; ordered factory clauses, explicit drop signatures, and language/fence restrictions are validated |
| Named sequences | Semantic | Ordered CREATE/ALTER behavior options, explicit `NO` forms, restart/rename/schema/owner actions, and multi-object DROP; catalog-dependent numeric consistency remains server validation |
| Schema lifecycle | Semantic | CREATE authorization/default privileges/qualification/quota; typed ALTER privilege, owner/cascade, quota/reset, and equal-cardinality rename actions; ordered multi-target DROP with exact dependency modifiers. Compound CREATE SCHEMA bodies remain separately planned and fail closed. Embedded CREATE properties fail atomically in PostgreSQL/DuckDB/MySQL/SQLite generation instead of raising raw `KeyError` |
| View lifecycle | Semantic | CREATE replacement, columns, privilege inheritance, and query bodies; ALTER owner/schema/inherited-privilege actions and equal-cardinality multi-rename; ordered multi-target DROP with postfix `IF EXISTS` and no dependency modifiers |
| `COMMENT ON` statements | Semantic | Aggregate, analytic, scalar, and transform routine signatures plus column, constraint, library, node, projection, schema, sequence, table, and view targets are typed; standard-string comments and `NULL` removal are preserved |
| Flex tables and map-specific DDL | Planned | Map functions currently parse generically |

## Security, administration, and physical maintenance

| Feature | Status | Notes |
| --- | --- | --- |
| Object `GRANT` / `REVOKE` | Semantic | Canonical roots with structured single/multi-object and all-in-schema targets, exact KEY/LIBRARY/DATA LOADER/TLS CONFIGURATION privilege and qualification domains, direction-specific `EXTEND`/grant-option/cascade rules, typed routine signatures, locations, and resource-pool subclusters |
| Role and authentication `GRANT` / `REVOKE` | Semantic | Compound role/grantee lists, admin-option revocation, cascade, and authentication associations use dedicated AST nodes |
| Role lifecycle | Semantic | Canonical `CREATE`, rename, and single-target `DROP`; atomic custom AST for comma-separated drops; exact unqualified-name and option validation |
| User, profile, and authentication lifecycle | Partial | The non-secret USER core is semantic, including ordered CREATE/ALTER `PROFILE`, global/subcluster `RESOURCE POOL`, grace/idle/runtime intervals, scoped connection limits, memory/temp-space caps, CREATE/ALTER `SEARCH_PATH`, ALTER-only `SECURITY_ALGORITHM`, isolated `DEFAULT ROLE`, `TOTPSECRET RESET`, value-free configuration CLEAR, and a five-parameter depot-only SET allowlist; PROFILE CREATE/ALTER/DROP is semantic with all 15 ordered policy settings, numeric/`UNLIMITED` values, ALTER-only `DEFAULT` resets and rename, and ordered dependency drops. AUTHENTICATION CREATE/ALTER/DROP is semantic for finite methods, LOCAL/HOST TLS matching, enable/disable, rename, lexical nonnegative priority, Boolean MFA state, fallthrough state, single-target dependency drops, and the closed non-secret `validate_type`/`jit_enabled` SET domains; all other SET values remain sanitized |
| Access-policy lifecycle | Semantic | CREATE, expression/state ALTER, COPY, and DROP use atomic roots with a shared row/column target and traversable policy expressions; exact qualification, `GRANT TRUSTED`, state, modifier, identifier, and foreign-generation contracts are enforced |
| Resource-pool lifecycle | Semantic | Ordered typed parameters, `DEFAULT`/`NONE`/`AUTO`/`HOLD` sentinels, named/current subcluster selectors, and CREATE/ALTER/DROP restrictions use dedicated AST roots |
| Load-balance-group lifecycle | Semantic | Address, fault-group, and subcluster member specifications, mandatory filters, selection policies, every ALTER action, and dependency-cascading DROP use typed ASTs with atomic foreign failure |
| Network-address lifecycle | Semantic | Fixed-order node/address/port/state creation, rename/endpoint/state ALTER actions, and postfix `IF EXISTS`/`CASCADE` DROP use typed ASTs; NETWORK INTERFACE remains intentionally opaque and distinct |
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
- Administrative privilege ownership, object existence, principal user/role
  type, and grant-chain effects require catalog state. The dialect enforces the
  documented KEY, LIBRARY, DATA LOADER, and TLS CONFIGURATION syntax, including
  the asymmetric GRANT/REVOKE privilege and cascade domains.
- Iceberg `COLUMN TYPES` compatibility depends on the source metadata, and a
  flexible external table's custom parser compatibility depends on the
  installed UDx catalog. The dialect validates their documented syntax and
  structural restrictions but cannot validate those catalog relationships.
- Physical-design expression validity can depend on volatility and catalog
  metadata.
- Constraint referential existence (`REFERENCES`/`FOREIGN KEY` targets),
  column-type compatibility (for example collection-typed key columns),
  same-name uniqueness across a database, enforcement state left unspecified,
  and dependency effects require catalog state. CHECK expression content
  restrictions (no subqueries, aggregates, window functions, SQL
  meta-functions, epoch-column, or other-table references) and the Boolean
  return-type requirement depend on function volatility and catalog
  typing, so they remain server-side; the dialect validates only the
  documented deterministic grammar, cardinality, and same-statement
  restrictions.
- COMMENT ON target existence/ownership and the server's documented
  8192-character truncation/message behavior require the catalog or execution;
  the dialect validates target shape and string-or-NULL syntax only.
- DML target existence and object kind, privileges, constraints, coercions,
  defaults, projection state, source-row uniqueness, join multiplicity, locks,
  quotas, and transaction effects require catalog data or execution. The
  dialect enforces only deterministic grammar and AST-shape restrictions.
- Routing-rule CIDR validity, workload/group/subcluster existence, priority
  resolution, and session authorization require catalog or server state.
  Load-balance-group CIDR validity, member existence/type compatibility,
  duplicate-node membership, and dependency effects are likewise catalog
  concerns. Network-address node existence, endpoint ownership, hostname/IP
  resolution, listener-port validity, NAT reachability, and dependency effects
  also require server state. The dialect validates exact statement shape,
  documented value domains, and safe identifier representation.
- Resource-pool availability, CPU/memory relationships, built-in-pool
  mutability, subcluster connection state, and secondary-pool dependency cycles
  require server/catalog state. The dialect validates documented value domains,
  required parameter pairs, duplicate parameters, and clause order only.
- USER existence, uniqueness, privilege and own-account restrictions,
  LDAP/external-authentication behavior, dependency effects, and the runtime
  `V_CATALOG.KEYWORDS` reserved-word catalog require server state. The dialect
  enforces the documented 128-byte UTF-8 name limit and parser/generator token
  parity, but does not freeze a version-sensitive reserved-word list. USER
  profile/resource-pool existence, pool grants, LDAP restrictions, privilege
  rules, effective limit interactions, and runtime assignment/expiration
  effects remain server checks. Search-path schema existence/access and
  session precedence, plus default-role existence, grants, and login-time
  activation, also remain server checks. The dialect validates deterministic
  USER interval ceilings, percentage/unit shapes, connection scopes, ordered
  schema/role/configuration lists, reviewed security-algorithm spellings, and
  the finite depot SET values only. Configuration level eligibility and runtime
  effects remain catalog/server checks; unknown value-bearing parameters fail
  through the credential sanitizer.
- PROFILE settings are policy metadata, not passwords. Profile ownership,
  inherited/default effects, current-password effects, and catalog existence
  remain server concerns; only deterministic value domains and explicit
  same-statement numeric maximum conflicts are validated locally.
- AUTHENTICATION address validity, record existence, grants, priority effects,
  access matching, current-method compatibility, and runtime authentication
  effects remain server concerns. CREATE and ALTER validate only
  their finite method/access/state grammar, action exclusivity, and lexical
  nonnegative priority; CREATE also enforces documented fallthrough exclusions.
  ALTER SET accepts only standard-string `validate_type` (`IDP`/`JWT`) and
  `jit_enabled` (`yes`/`no`) values. Explicit secrets, arbitrary-string LDAP,
  Ident, Kerberos, and OAuth parameters, incompletely pinned Boolean values,
  and unknown names remain outside the AST and fail through a fixed sanitizer.
- Directed-query name existence, query compatibility, optimizer-version/date
  provenance, and activation effects require the Vertica catalog. The dialect
  validates statement grammar, target cardinality, nonempty query structure,
  and constant-annotation placement only.
- Access-policy target existence and object type, ownership, permissions,
  expression volatility, user-defined transform behavior, and runtime policy
  evaluation require catalog or server state. The dialect enforces the formal
  26.2 statement grammar, deterministic expression restrictions, qualification,
  and identifier shape only.

These boundaries are tested either with explicit syntax-negative fixtures or a
documented server-negative corpus. The parser does not pretend to perform
catalog-aware validation.
