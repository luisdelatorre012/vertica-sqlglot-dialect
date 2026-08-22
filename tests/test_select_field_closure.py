"""Strict closure for inherited SELECT, ordering, and relation fields."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, lineage, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = tuple(ErrorLevel)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT * FROM t TABLESAMPLE(25)", "SELECT * FROM t TABLESAMPLE (25)"),
        ("SELECT * FROM t TABLESAMPLE(0.5)", "SELECT * FROM t TABLESAMPLE (0.5)"),
        ("SELECT * FROM t TABLESAMPLE(101)", "SELECT * FROM t TABLESAMPLE (101)"),
        (
            "SELECT * FROM (SELECT a FROM t) q TABLESAMPLE(10)",
            "SELECT * FROM (SELECT a FROM t) AS q TABLESAMPLE (10)",
        ),
        (
            "SELECT * FROM a TABLESAMPLE(25) JOIN b TABLESAMPLE(50) ON a.id=b.id",
            "SELECT * FROM a TABLESAMPLE (25) JOIN b TABLESAMPLE (50) ON a.id = b.id",
        ),
        (
            "SELECT /* sample */ a FROM t TABLESAMPLE(12.5) ORDER BY a DESC",
            "/* sample */ SELECT a FROM t TABLESAMPLE (12.5) ORDER BY a DESC",
        ),
    ],
)
def test_documented_tablesample_and_ordinary_query_forms_roundtrip(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    sample = expression.find(exp.TableSample)
    assert sample is not None
    assert sample.args.get("percent") is not None
    assert all(value is None for key, value in sample.args.items() if key != "percent")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t DISTRIBUTE BY a",
        "SELECT a FROM t SORT BY a",
        "SELECT a FROM t CLUSTER BY a",
        "SELECT a FROM t WINDOW w AS (PARTITION BY a)",
        "SELECT a FROM t CONNECT BY a = PRIOR a",
        "SELECT * FROM t LATERAL VIEW EXPLODE(a) q AS x",
        "SELECT * FROM LATERAL (SELECT 1) q",
        "SELECT * FROM t PIVOT(SUM(x) FOR y IN (1))",
        "SELECT * FROM t UNPIVOT(x FOR y IN (a))",
        "SELECT * FROM ONLY t",
        "SELECT * FROM t AT (TIMESTAMP => '2020-01-01')",
        "SELECT * FROM t TABLESAMPLE SYSTEM (10)",
        "SELECT * FROM t TABLESAMPLE BERNOULLI (10) REPEATABLE (1)",
        "SELECT * FROM t TABLESAMPLE (10 ROWS)",
        "SELECT * FROM t TABLESAMPLE (10 PERCENT)",
        "SELECT * FROM t TABLESAMPLE ()",
        "SELECT * FROM t TABLESAMPLE (a)",
        "SELECT a FROM t ORDER SIBLINGS BY a",
        "SELECT a FROM t ORDER BY a WITH FILL",
        "SELECT a FROM t ORDER BY a NULLS FIRST",
        "SELECT a FROM t ORDER BY a NULLS LAST",
        "SELECT * EXCLUDE (a) FROM t",
        "SELECT * EXCEPT (a) FROM t",
        "SELECT * REPLACE (a AS b) FROM t",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_inherited_query_source_forms_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_invalid_multistatement_query_field_does_not_swallow_following_statement(
    error_level: ErrorLevel,
) -> None:
    with pytest.raises(ParseError):
        parse(
            "SELECT * FROM t PIVOT(SUM(x) FOR y IN (1)); SELECT 2",
            read="vertica",
            error_level=error_level,
        )


@pytest.mark.parametrize(
    "field",
    [
        "exclude",
        "laterals",
        "connect",
        "pivots",
        "prewhere",
        "windows",
        "distribute",
        "sort",
        "cluster",
        "sample",
        "settings",
        "format",
        "for_",
    ],
)
def test_direct_select_inherited_field_mutations_fail_strict_generation(field: str) -> None:
    expression = parse_one("SELECT a FROM t", read="vertica")
    expression.set(field, [exp.var("x")] if field.endswith("s") else exp.var("x"))
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "field",
    [
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
        "sample",
        "settings",
        "format",
        "for_",
    ],
)
def test_set_operation_inherited_field_mutations_fail_strict_generation(field: str) -> None:
    expression = parse_one("SELECT 1 UNION SELECT 2", read="vertica")
    expression.set(field, [exp.var("x")] if field.endswith("s") else exp.var("x"))
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "field",
    [
        "with_",
        "match",
        "laterals",
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
        "settings",
        "format",
        "for_",
    ],
)
def test_subquery_inherited_field_mutations_fail_strict_generation(field: str) -> None:
    expression = parse_one("SELECT * FROM (SELECT 1) q", read="vertica")
    subquery = expression.find(exp.Subquery)
    assert subquery is not None
    subquery.set(field, [exp.var("x")] if field.endswith("s") else exp.var("x"))
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("laterals", []),
        ("pivots", []),
        ("system_time", exp.var("x")),
        ("version", exp.var("x")),
        ("format", exp.var("x")),
        ("pattern", exp.var("x")),
        ("ordinality", False),
        ("when", exp.var("x")),
        ("only", False),
        ("partition", exp.var("x")),
        ("changes", exp.var("x")),
        ("rows_from", []),
        ("indexed", False),
    ],
)
def test_table_inherited_field_mutations_fail_direct_and_nested_generation(
    field: str, value: object
) -> None:
    for nested in (False, True):
        table = exp.to_table("t")
        table.set(field, value)
        expression: exp.Expr = exp.select("*").from_(table) if nested else table
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expressions", []),
        ("method", exp.var("SYSTEM")),
        ("bucket_numerator", exp.Literal.number(1)),
        ("bucket_denominator", exp.Literal.number(2)),
        ("bucket_field", exp.column("a")),
        ("rows", False),
        ("size", exp.Literal.number(10)),
        ("seed", exp.Literal.number(1)),
    ],
)
def test_tablesample_mutations_fail_direct_and_nested_generation(field: str, value: object) -> None:
    for nested in (False, True):
        sample = exp.TableSample(percent=exp.Literal.number(10))
        sample.set(field, value)
        if nested:
            table = exp.to_table("t")
            table.set("sample", sample)
            expression: exp.Expr = exp.select("*").from_(table)
        else:
            expression = sample
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "mutation",
    ["order_siblings", "query_order_owner", "ordered_fill", "star_except", "pivot", "lateral"],
)
def test_order_projection_and_lateral_mutations_fail_atomically(mutation: str) -> None:
    expression = parse_one("SELECT a FROM t ORDER BY a", read="vertica")
    order = expression.args["order"]
    ordered = order.expressions[0]

    if mutation == "order_siblings":
        order.set("siblings", False)
    elif mutation == "query_order_owner":
        order.set("this", exp.column("x"))
    elif mutation == "ordered_fill":
        ordered.set("with_fill", False)
    elif mutation == "star_except":
        expression.set("expressions", [exp.Star(except_=[])])
    elif mutation == "pivot":
        expression.args["from_"].this.set("pivots", [exp.Pivot()])
    else:
        expression.args["from_"].set(
            "this", exp.Lateral(this=exp.select("1").subquery(), view=False, outer=False)
        )

    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_direct_pivot_and_modified_star_fail_strict_generation() -> None:
    for expression in (exp.Pivot(), exp.Star(replace=[])):
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        exp.select("a"),
        exp.union(exp.select("1"), exp.select("2")),
        exp.select("1").subquery(),
        exp.to_table("t"),
        exp.TableSample(percent=exp.Literal.number(10)),
        exp.Order(expressions=[exp.Ordered(this=exp.column("a"), nulls_first=False)]),
        exp.Ordered(this=exp.column("a"), nulls_first=False),
        exp.Star(),
    ],
)
def test_unknown_query_fields_fail_strict_generation(expression: exp.Expr) -> None:
    expression.set("q21_unknown", False)
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_tablesample_preserves_analysis_and_tree_operations() -> None:
    sql = "SELECT t.a FROM t TABLESAMPLE(10) WHERE t.a > 0 ORDER BY t.a"
    expression = parse_one(sql, read="vertica")
    copied = expression.copy()
    transformed = expression.transform(lambda node: node)

    for candidate in (expression, copied, transformed):
        assert candidate.find(exp.TableSample) is not None
        assert candidate.find(exp.TableSample).parent is candidate.args["from_"].this
        assert list(traverse_scope(candidate))

    schema = {"t": {"a": "INT"}}
    qualified = qualify(expression.copy(), schema=schema, dialect="vertica")
    optimized = optimize(expression.copy(), schema=schema, dialect="vertica")
    assert qualified.find(exp.TableSample) is not None
    assert optimized.find(exp.TableSample) is not None
    assert lineage.lineage("a", expression, schema=schema, dialect="vertica").name == "a"


def test_apply_lowerings_remain_the_only_supported_lateral_contract() -> None:
    for sql, expected in (
        (
            "SELECT * FROM a CROSS APPLY (SELECT a.id) q",
            "SELECT * FROM a INNER JOIN LATERAL (SELECT a.id) AS q ON TRUE",
        ),
        (
            "SELECT * FROM a OUTER APPLY (SELECT a.id) q",
            "SELECT * FROM a LEFT JOIN LATERAL (SELECT a.id) AS q ON TRUE",
        ),
    ):
        expression = parse_one(sql, read="vertica")
        assert expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE) == expected
        assert parse_one(expected, read="vertica").sql(dialect="vertica") == expected
