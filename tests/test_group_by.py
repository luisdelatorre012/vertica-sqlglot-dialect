"""Ordered and strict Vertica ``GROUP BY`` regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

FOREIGN_DIALECTS = ["postgres", "duckdb", "mysql", "sqlite"]
ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
ALL_UNSUPPORTED_LEVELS = [ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]


def parse_group(sql: str, expected: str | None = None) -> vexp.VerticaGroup:
    expression = assert_roundtrip(sql, expected)
    group = expression.args.get("group")
    assert isinstance(group, vexp.VerticaGroup)
    return group


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT a, SUM(v) FROM t GROUP BY a",
            "SELECT a, SUM(v) FROM t GROUP BY a",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY a, b",
            "SELECT a, b, SUM(v) FROM t GROUP BY a, b",
        ),
        (
            "SELECT a, SUM(v) FROM t GROUP BY ROLLUP(a)",
            "SELECT a, SUM(v) FROM t GROUP BY ROLLUP (a)",
        ),
        (
            "SELECT a, SUM(v) FROM t GROUP BY CUBE(a)",
            "SELECT a, SUM(v) FROM t GROUP BY CUBE (a)",
        ),
        (
            "SELECT a, SUM(v) FROM t GROUP BY GROUPING SETS(a)",
            "SELECT a, SUM(v) FROM t GROUP BY GROUPING SETS (a)",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY ROLLUP(a), ROLLUP(b)",
            "SELECT a, b, SUM(v) FROM t GROUP BY ROLLUP (a), ROLLUP (b)",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY CUBE(a), CUBE(b)",
            "SELECT a, b, SUM(v) FROM t GROUP BY CUBE (a), CUBE (b)",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS(a), GROUPING SETS(b)",
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS (a), GROUPING SETS (b)",
        ),
        (
            "SELECT a, b, c, SUM(v) FROM t GROUP BY ROLLUP(a), CUBE(b), GROUPING SETS(c)",
            "SELECT a, b, c, SUM(v) FROM t GROUP BY ROLLUP (a), CUBE (b), GROUPING SETS (c)",
        ),
        (
            "SELECT a, b, c, SUM(v) FROM t GROUP BY CUBE(a), c, ROLLUP(b)",
            "SELECT a, b, c, SUM(v) FROM t GROUP BY CUBE (a), c, ROLLUP (b)",
        ),
        (
            "SELECT a, b, c, SUM(v) FROM t GROUP BY a, ROLLUP(b), c, CUBE(a)",
            "SELECT a, b, c, SUM(v) FROM t GROUP BY a, ROLLUP (b), c, CUBE (a)",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS((a, b), (a), ())",
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS ((a, b), (a), ())",
        ),
        (
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS(ROLLUP(a, b), CUBE(a))",
            "SELECT a, b, SUM(v) FROM t GROUP BY GROUPING SETS (ROLLUP (a, b), CUBE (a))",
        ),
        (
            "SELECT (a + b) AS total, SUM(v) FROM t GROUP BY (a + b)",
            "SELECT (a + b) AS total, SUM(v) FROM t GROUP BY (a + b)",
        ),
        (
            "SELECT a AS alias_a, SUM(v) FROM t GROUP BY alias_a, 1",
            "SELECT a AS alias_a, SUM(v) FROM t GROUP BY alias_a, 1",
        ),
        (
            "SELECT a, SUM(v), GROUPING_ID() FROM t GROUP BY ROLLUP(a)",
            "SELECT a, SUM(v), GROUPING_ID() FROM t GROUP BY ROLLUP (a)",
        ),
        (
            "SELECT a, b, SUM(v), GROUPING_ID(a, b) FROM t GROUP BY CUBE(a, b)",
            "SELECT a, b, SUM(v), GROUPING_ID(a, b) FROM t GROUP BY CUBE (a, b)",
        ),
        (
            "SELECT a, SUM(v) FROM t GROUP BY /*+GBYTYPE(HASH)*/ a",
            "SELECT a, SUM(v) FROM t GROUP BY /*+GBYTYPE(HASH)*/ a",
        ),
        (
            "SELECT a, SUM(v) FROM t GROUP BY /*+GBYTYPE(PIPE)*/ a",
            "SELECT a, SUM(v) FROM t GROUP BY /*+GBYTYPE(PIPE)*/ a",
        ),
    ],
)
def test_documented_group_items_round_trip_in_source_order(sql: str, expected: str) -> None:
    parse_group(sql, expected)


def test_ordered_ast_shape_and_parent_metadata() -> None:
    group = parse_group(
        "SELECT a, b, c, SUM(v) FROM t GROUP BY CUBE(a), c, ROLLUP(b), GROUPING SETS(())"
    )
    assert [type(item) for item in group.expressions] == [
        exp.Cube,
        exp.Column,
        exp.Rollup,
        exp.GroupingSets,
    ]
    assert not any(key in group.args for key in ("cube", "rollup", "grouping_sets"))
    for index, item in enumerate(group.expressions):
        assert item.parent is group
        assert item.arg_key == "expressions"
        assert item.index == index


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT x FROM (SELECT a AS x, SUM(v) FROM t GROUP BY CUBE(a), ROLLUP(a)) AS q",
        "WITH q AS (SELECT a, SUM(v) FROM t GROUP BY ROLLUP(a), CUBE(a)) SELECT * FROM q",
        "SELECT a, SUM(v) FROM t GROUP BY CUBE(a), ROLLUP(a) "
        "UNION SELECT a, SUM(v) FROM u GROUP BY ROLLUP(a), CUBE(a)",
    ],
)
def test_nested_cte_and_set_operation_positions(sql: str) -> None:
    expression = assert_roundtrip(sql)
    groups = list(expression.find_all(vexp.VerticaGroup))
    assert groups
    assert all(
        not any(key in group.args for key in ("cube", "rollup", "grouping_sets"))
        for group in groups
    )


def test_comments_and_group_hint_keep_their_boundaries() -> None:
    expression = assert_roundtrip(
        "SELECT a, SUM(v) FROM t GROUP BY /*+GBYTYPE(HASH)*/ a /* item */"
    )
    generated = expression.sql(dialect="vertica")
    assert "/*+GBYTYPE(HASH)*/" in generated
    assert "item" in generated


def test_copy_and_transform_preserve_order_and_parents() -> None:
    expression = parse_one(
        "SELECT a, b, SUM(v) FROM t GROUP BY CUBE(a), b, ROLLUP(a)", read="vertica"
    )
    copied = expression.copy()
    transformed = copied.transform(
        lambda node: (
            exp.column("renamed") if isinstance(node, exp.Column) and node.name == "b" else node
        )
    )
    group = transformed.args["group"]
    assert isinstance(group, vexp.VerticaGroup)
    assert [type(item) for item in group.expressions] == [exp.Cube, exp.Column, exp.Rollup]
    assert group.expressions[1].name == "renamed"
    assert all(item.parent is group for item in group.expressions)


def test_qualification_optimization_scope_and_lineage_preserve_ordered_group() -> None:
    sql = "SELECT a, b, SUM(v) AS total FROM t GROUP BY CUBE(a), b, ROLLUP(a)"
    schema = {"t": {"a": "INT", "b": "INT", "v": "INT"}}

    qualified = qualify(parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    optimized = optimize(parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    for expression in (qualified, optimized):
        group = expression.args.get("group")
        assert isinstance(group, vexp.VerticaGroup)
        assert [type(item) for item in group.expressions] == [exp.Cube, exp.Column, exp.Rollup]
        assert not any(key in group.args for key in ("cube", "rollup", "grouping_sets"))
        assert list(traverse_scope(expression))
        assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression

    node = lineage("total", parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    assert any(downstream.name == "t.v" for downstream in node.walk())


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t GROUP BY ALL",
        "SELECT a FROM t GROUP BY DISTINCT a",
        "SELECT a FROM t GROUP BY a WITH TOTALS",
        "SELECT a FROM t GROUP BY a TOTALS",
        "SELECT a FROM t GROUP BY a WITH ROLLUP",
        "SELECT a FROM t GROUP BY a WITH CUBE",
        "SELECT a FROM t GROUP BY ROLLUP()",
        "SELECT a FROM t GROUP BY CUBE()",
        "SELECT a FROM t GROUP BY GROUPING SETS()",
        "SELECT a FROM t GROUP BY GROUPING SETS(GROUPING SETS(a))",
        "SELECT a FROM t GROUP BY CUBE(ROLLUP(a))",
        "SELECT a FROM t GROUP BY ROLLUP(CUBE(a))",
        "SELECT a FROM t GROUP BY a,",
        "SELECT a FROM t GROUP BY ROLLUP(a,)",
        "SELECT a FROM t GROUP BY GROUPING SETS(a,)",
        "SELECT a FROM t GROUP BY /*+GBYTYPE(SORT)*/ a",
        "SELECT a FROM t GROUP BY /*+GBYTYPE(HASH)*/ /*+GBYTYPE(PIPE)*/ a",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recognized_invalid_group_by_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "group",
    [
        exp.Group(
            expressions=[exp.column("a")],
            rollup=[exp.Rollup(expressions=[exp.column("b")])],
        ),
        exp.Group(expressions=[exp.column("a")], cube=[]),
        exp.Group(expressions=[exp.column("a")], grouping_sets=[]),
        exp.Group(expressions=[exp.column("a")], all=True),
        exp.Group(expressions=[exp.column("a")], totals=True),
        vexp.VerticaGroup(),
        vexp.VerticaGroup(expressions=[]),
        vexp.VerticaGroup(expressions=[None]),
        vexp.VerticaGroup(expressions=[exp.Tuple()]),
        vexp.VerticaGroup(expressions=[exp.column("a")], algorithm=exp.var("SORT")),
        vexp.VerticaGroup(expressions=[exp.column("a")], totals=False),
        vexp.VerticaGroup(expressions=[exp.Rollup()]),
        vexp.VerticaGroup(expressions=[exp.Cube(expressions=[None])]),
        vexp.VerticaGroup(expressions=[exp.GroupingSets(expressions=[])]),
        vexp.VerticaGroup(
            expressions=[
                exp.GroupingSets(expressions=[exp.GroupingSets(expressions=[exp.column("a")])])
            ]
        ),
    ],
)
def test_programmatic_group_mutations_fail_atomically(group: exp.Group) -> None:
    expression = exp.select("a").from_("t")
    expression.set("group", group)
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_foreign_parsed_ordinary_group_can_generate_vertica() -> None:
    expression = parse_one("SELECT a, SUM(v) FROM t GROUP BY a", read="postgres")
    assert type(expression.args["group"]) is exp.Group
    assert expression.sql(dialect="vertica") == "SELECT a, SUM(v) FROM t GROUP BY a"


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
@pytest.mark.parametrize("nested", [False, True])
def test_ordered_group_fails_atomically_in_foreign_dialects(
    dialect: str, unsupported_level: ErrorLevel, nested: bool
) -> None:
    group = vexp.VerticaGroup(
        expressions=[exp.Cube(expressions=[exp.column("a")]), exp.column("b")]
    )
    expression: exp.Expr
    if nested:
        expression = exp.select("a").from_("t")
        expression.set("group", group)
    else:
        expression = group
    with pytest.raises(ValueError, match="Unsupported expression type VerticaGroup"):
        expression.sql(dialect=dialect, unsupported_level=unsupported_level)
