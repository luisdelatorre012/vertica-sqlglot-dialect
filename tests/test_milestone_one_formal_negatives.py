"""Milestone 1 formal-syntax inventory and negative-boundary audit."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError

ALL_PARSE_LEVELS = tuple(ErrorLevel)


@pytest.mark.parametrize(
    ("expression_type", "expected_fields"),
    [
        (
            exp.Select,
            {
                "with_",
                "kind",
                "expressions",
                "hint",
                "distinct",
                "into",
                "from_",
                "operation_modifiers",
                "exclude",
                "match",
                "laterals",
                "joins",
                "connect",
                "pivots",
                "prewhere",
                "where",
                "group",
                "having",
                "qualify",
                "windows",
                "distribute",
                "sort",
                "cluster",
                "order",
                "limit",
                "offset",
                "locks",
                "sample",
                "settings",
                "format",
                "options",
                "for_",
            },
        ),
        (
            exp.SetOperation,
            {
                "with_",
                "this",
                "expression",
                "distinct",
                "by_name",
                "side",
                "kind",
                "on",
                "match",
                "laterals",
                "joins",
                "connect",
                "pivots",
                "prewhere",
                "where",
                "group",
                "having",
                "qualify",
                "windows",
                "distribute",
                "sort",
                "cluster",
                "order",
                "limit",
                "offset",
                "locks",
                "sample",
                "settings",
                "format",
                "options",
                "for_",
            },
        ),
        (
            exp.Join,
            {
                "this",
                "on",
                "side",
                "kind",
                "using",
                "method",
                "global_",
                "hint",
                "match_condition",
                "directed",
                "expressions",
                "pivots",
            },
        ),
        (
            exp.Table,
            {
                "this",
                "alias",
                "db",
                "catalog",
                "laterals",
                "joins",
                "pivots",
                "hints",
                "system_time",
                "version",
                "format",
                "pattern",
                "ordinality",
                "when",
                "only",
                "partition",
                "changes",
                "rows_from",
                "sample",
                "indexed",
            },
        ),
        (
            exp.TableSample,
            {
                "expressions",
                "method",
                "bucket_numerator",
                "bucket_denominator",
                "bucket_field",
                "percent",
                "rows",
                "size",
                "seed",
            },
        ),
        (
            exp.CTE,
            {"this", "alias", "scalar", "materialized", "key_expressions"},
        ),
        (exp.With, {"expressions", "recursive", "search"}),
        (exp.Limit, {"this", "expression", "offset", "limit_options", "expressions"}),
        (exp.Offset, {"this", "expression", "expressions"}),
        (exp.Lock, {"update", "expressions", "wait", "key"}),
        (exp.Order, {"this", "expressions", "siblings"}),
        (exp.Ordered, {"this", "desc", "nulls_first", "with_fill"}),
        (
            exp.Into,
            {"this", "temporary", "unlogged", "bulk_collect", "expressions"},
        ),
        (
            exp.Create,
            {
                "with_",
                "this",
                "kind",
                "expression",
                "exists",
                "properties",
                "replace",
                "refresh",
                "unique",
                "indexes",
                "no_schema_binding",
                "begin",
                "clone",
                "concurrently",
                "clustered",
            },
        ),
        (
            exp.Insert,
            {
                "hint",
                "with_",
                "is_function",
                "this",
                "expression",
                "conflict",
                "returning",
                "overwrite",
                "exists",
                "alternative",
                "where",
                "ignore",
                "by_name",
                "stored",
                "partition",
                "settings",
                "source",
                "default",
            },
        ),
        (
            exp.Drop,
            {
                "this",
                "kind",
                "expressions",
                "exists",
                "temporary",
                "materialized",
                "cascade",
                "restrict",
                "constraints",
                "purge",
                "cluster",
                "concurrently",
                "sync",
                "iceberg",
            },
        ),
    ],
)
def test_sqlglot_30_13_exposed_field_inventory(
    expression_type: type[exp.Expr], expected_fields: set[str]
) -> None:
    """Make upstream field drift an explicit future audit event."""

    assert set(expression_type.arg_types) == expected_fields


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t GROUP BY ALL",
        "SELECT 1 INTERSECT ALL SELECT 2",
        "SELECT DISTINCT ON (a) a FROM t",
        "SELECT a FROM t FETCH FIRST 1 ROW ONLY",
        "SELECT * FROM a LEFT JOIN b",
        "WITH c AS (VALUES (1)) SELECT * FROM c",
        "CREATE LOCAL TABLE t (id INT)",
        "INSERT t VALUES (1)",
        "CREATE TABLE a.b.c.d (id INT)",
        "SELECT a FROM t INTO TABLE u",
        "DROP TABLE t RESTRICT",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_q09_q19_formal_negatives_remain_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    ("sql", "expected", "root_type"),
    [
        ("SELECT ALL a FROM t", "SELECT a FROM t", exp.Select),
        ("SELECT a FROM t LIMIT ALL", "SELECT a FROM t", exp.Select),
        ("SELECT 1 MINUS SELECT 2", "SELECT 1 EXCEPT SELECT 2", exp.Except),
        (
            "SELECT a FROM t QUALIFY ROW_NUMBER() OVER () = 1",
            "SELECT a FROM (SELECT a, ROW_NUMBER() OVER () AS _w FROM t) AS _t WHERE _w = 1",
            exp.Select,
        ),
        (
            "SELECT * FROM a LEFT SEMI JOIN b ON a.id = b.id",
            "SELECT * FROM a WHERE EXISTS(SELECT 1 FROM b WHERE a.id = b.id)",
            exp.Select,
        ),
        (
            "SELECT * FROM a LEFT ANTI JOIN b ON a.id = b.id",
            "SELECT * FROM a WHERE NOT EXISTS(SELECT 1 FROM b WHERE a.id = b.id)",
            exp.Select,
        ),
        (
            "SELECT * FROM a CROSS APPLY (SELECT a.id) AS q",
            "SELECT * FROM a INNER JOIN LATERAL (SELECT a.id) AS q ON TRUE",
            exp.Select,
        ),
        (
            "SELECT * FROM a OUTER APPLY (SELECT a.id) AS q",
            "SELECT * FROM a LEFT JOIN LATERAL (SELECT a.id) AS q ON TRUE",
            exp.Select,
        ),
    ],
)
def test_architecture_approved_canonicalizations_and_lowerings(
    sql: str, expected: str, root_type: type[exp.Expr]
) -> None:
    expression = parse_one(sql, read="vertica")
    assert isinstance(expression, root_type)
    generated = expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert generated == expected
    assert parse_one(generated, read="vertica").sql(dialect="vertica") == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t DISTRIBUTE BY a",
        "SELECT a FROM t SORT BY a",
        "SELECT a FROM t CLUSTER BY a",
        "SELECT a FROM t WINDOW w AS (PARTITION BY a)",
        "SELECT a FROM t CONNECT BY a = PRIOR a",
        "SELECT * FROM t LATERAL VIEW EXPLODE(a) q AS x",
        "SELECT * FROM t PIVOT(SUM(x) FOR y IN (1))",
        "SELECT * FROM ONLY t",
        "SELECT * FROM t AT (TIMESTAMP => '2020-01-01')",
        "SELECT * FROM t TABLESAMPLE SYSTEM (10)",
        "SELECT * FROM t TABLESAMPLE BERNOULLI (10) REPEATABLE (1)",
        "SELECT * FROM t TABLESAMPLE (10 ROWS)",
        "SELECT a FROM t ORDER BY a WITH FILL",
        "SELECT * EXCLUDE (a) FROM t",
        "SELECT * EXCEPT (a) FROM t",
        "SELECT * REPLACE (a AS b) FROM t",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_q21_inherited_select_fields_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    ("sql", "node_type"),
    [
        (
            "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER ()",
            exp.Select,
        ),
        (
            "SELECT * FROM events MATCH (ORDER BY ts PATTERN p AS (A))",
            exp.Select,
        ),
        (
            "SELECT * FROM t WHERE a.ts INTERPOLATE PREVIOUS VALUE",
            exp.Select,
        ),
    ],
)
@pytest.mark.parametrize("error_level", [ErrorLevel.WARN, ErrorLevel.IGNORE])
def test_scheduled_query_extension_guaranteed_raise_gaps_are_reproducible(
    sql: str, node_type: type[exp.Expr], error_level: ErrorLevel
) -> None:
    """Q22 will turn these permissive-level partial ASTs into ParseError."""

    assert isinstance(parse_one(sql, read="vertica", error_level=error_level), node_type)
