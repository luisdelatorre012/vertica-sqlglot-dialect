"""Strict Vertica set-operation modifier regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]


@pytest.mark.parametrize(
    ("sql", "expected", "operation", "distinct"),
    [
        ("SELECT 1 UNION SELECT 2", "SELECT 1 UNION SELECT 2", exp.Union, True),
        ("SELECT 1 UNION DISTINCT SELECT 2", "SELECT 1 UNION SELECT 2", exp.Union, True),
        ("SELECT 1 UNION ALL SELECT 2", "SELECT 1 UNION ALL SELECT 2", exp.Union, False),
        ("SELECT 1 INTERSECT SELECT 2", "SELECT 1 INTERSECT SELECT 2", exp.Intersect, True),
        (
            "SELECT 1 INTERSECT DISTINCT SELECT 2",
            "SELECT 1 INTERSECT SELECT 2",
            exp.Intersect,
            True,
        ),
        ("SELECT 1 EXCEPT SELECT 2", "SELECT 1 EXCEPT SELECT 2", exp.Except, True),
        (
            "SELECT 1 EXCEPT DISTINCT SELECT 2",
            "SELECT 1 EXCEPT SELECT 2",
            exp.Except,
            True,
        ),
        ("SELECT 1 MINUS SELECT 2", "SELECT 1 EXCEPT SELECT 2", exp.Except, True),
        (
            "SELECT 1 MINUS DISTINCT SELECT 2",
            "SELECT 1 EXCEPT SELECT 2",
            exp.Except,
            True,
        ),
    ],
)
def test_documented_duplicate_modes_round_trip(
    sql: str,
    expected: str,
    operation: type[exp.SetOperation],
    distinct: bool,
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert type(expression) is operation
    assert expression.args["distinct"] is distinct
    assert all(expression.args.get(key) is None for key in ("by_name", "on", "side", "kind"))


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 UNION ALL SELECT 2 INTERSECT SELECT 3",
        "SELECT 1 INTERSECT SELECT 2 UNION ALL SELECT 3",
        "SELECT 1 EXCEPT SELECT 2 EXCEPT SELECT 3",
        "SELECT 1 MINUS SELECT 2 MINUS SELECT 3",
        "SELECT 1 UNION SELECT 2 EXCEPT SELECT 3 INTERSECT SELECT 4",
    ],
)
def test_chains_preserve_left_to_right_tree_ownership(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, exp.SetOperation)
    assert isinstance(expression.this, exp.SetOperation)
    assert expression.this.parent is expression
    assert expression.this.arg_key == "this"


def test_each_chain_node_owns_its_duplicate_mode() -> None:
    expression = assert_roundtrip(
        "SELECT 1 UNION ALL SELECT 2 INTERSECT DISTINCT SELECT 3 UNION SELECT 4"
    )
    assert isinstance(expression, exp.Union)
    assert expression.args["distinct"] is True
    assert isinstance(expression.this, exp.Intersect)
    assert expression.this.args["distinct"] is True
    assert isinstance(expression.this.this, exp.Union)
    assert expression.this.this.args["distinct"] is False


@pytest.mark.parametrize(
    "sql",
    [
        "(SELECT a FROM t ORDER BY a LIMIT 2 OFFSET 1) UNION ALL "
        "(SELECT a FROM u ORDER BY a DESC LIMIT 3)",
        "WITH q AS (SELECT a FROM t UNION SELECT a FROM u) SELECT a FROM q EXCEPT SELECT a FROM v",
        "SELECT * FROM (SELECT a FROM t INTERSECT SELECT a FROM u) AS q",
        "SELECT a FROM t UNION ALL SELECT a FROM u ORDER BY a LIMIT 4 OFFSET 2",
        "SELECT a /* left */ FROM t UNION ALL /* right */ SELECT a FROM u",
    ],
)
def test_nested_cte_subquery_comments_and_branch_tails_round_trip(sql: str) -> None:
    assert_roundtrip(sql)


def test_dump_copy_transform_and_parent_metadata() -> None:
    expression = assert_roundtrip("SELECT a FROM t UNION ALL SELECT a FROM u")
    transformed = expression.copy().transform(
        lambda node: exp.column("b") if isinstance(node, exp.Column) and node.name == "a" else node
    )
    assert transformed.sql(dialect="vertica") == "SELECT b FROM t UNION ALL SELECT b FROM u"
    assert isinstance(transformed, exp.Union)
    assert transformed.this.parent is transformed
    assert transformed.this.arg_key == "this"
    assert transformed.expression.parent is transformed
    assert transformed.expression.arg_key == "expression"


def test_scope_qualification_optimization_and_lineage_remain_canonical() -> None:
    sql = "SELECT a FROM t UNION ALL SELECT a FROM u"
    schema = {"t": {"a": "INT"}, "u": {"a": "INT"}}
    for expression in (
        qualify(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
        optimize(parse_one(sql, read="vertica"), schema=schema, dialect="vertica"),
    ):
        assert isinstance(expression, exp.Union)
        assert expression.args["distinct"] is False
        assert list(traverse_scope(expression))
        assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression

    node = lineage("a", parse_one(sql, read="vertica"), schema=schema, dialect="vertica")
    names = {downstream.name for downstream in node.walk()}
    assert "t.a" in names
    assert "u.a" in names


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1 INTERSECT ALL SELECT 2",
        "SELECT 1 EXCEPT ALL SELECT 2",
        "SELECT 1 MINUS ALL SELECT 2",
        "SELECT a FROM t UNION BY NAME SELECT a FROM u",
        "SELECT a FROM t UNION BY NAME ON (a) SELECT a FROM u",
        "SELECT a FROM t UNION CORRESPONDING SELECT a FROM u",
        "SELECT a FROM t UNION CORRESPONDING BY (a) SELECT a FROM u",
        "SELECT a FROM t INTERSECT BY NAME SELECT a FROM u",
        "SELECT a FROM t EXCEPT CORRESPONDING SELECT a FROM u",
        "SELECT a FROM t LEFT UNION SELECT a FROM u",
        "SELECT a FROM t INNER UNION SELECT a FROM u",
        "SELECT a FROM t FULL OUTER UNION SELECT a FROM u",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recognized_invalid_set_modifiers_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def valid_set_operation(operation: type[exp.SetOperation] = exp.Union) -> exp.SetOperation:
    return operation(
        this=exp.select(exp.Literal.number(1)),
        expression=exp.select(exp.Literal.number(2)),
        distinct=True,
    )


def mutated_set_operation(
    key: str,
    value: object,
    operation: type[exp.SetOperation] = exp.Union,
) -> exp.SetOperation:
    expression = valid_set_operation(operation)
    expression.set(key, value)
    return expression


@pytest.mark.parametrize(
    "expression",
    [
        mutated_set_operation("distinct", False, exp.Intersect),
        mutated_set_operation("distinct", False, exp.Except),
        mutated_set_operation("distinct", None),
        mutated_set_operation("distinct", 1),
        mutated_set_operation("by_name", True),
        mutated_set_operation("by_name", False),
        mutated_set_operation("on", [exp.column("a")]),
        mutated_set_operation("on", []),
        mutated_set_operation("side", "LEFT"),
        mutated_set_operation("side", ""),
        mutated_set_operation("kind", "INNER"),
        mutated_set_operation("kind", ""),
        mutated_set_operation("this", exp.column("a")),
        mutated_set_operation("expression", None),
    ],
)
def test_programmatic_set_mutations_fail_atomically(expression: exp.SetOperation) -> None:
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_invalid_nested_set_node_fails_before_returning_sql() -> None:
    inner = mutated_set_operation("distinct", False, exp.Intersect)
    outer = exp.Union(
        this=inner,
        expression=exp.select(exp.Literal.number(3)),
        distinct=False,
    )
    with pytest.raises(UnsupportedError):
        outer.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_foreign_parsed_valid_set_tree_generates_vertica() -> None:
    expression = parse_one("SELECT 1 UNION ALL SELECT 2", read="postgres")
    assert expression.sql(dialect="vertica") == "SELECT 1 UNION ALL SELECT 2"
