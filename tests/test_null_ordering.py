"""Lossless explicit NULL-placement contracts for Vertica ordering owners."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = tuple(ErrorLevel)
FOREIGN_DIALECTS = ("postgres", "duckdb", "mysql", "sqlite")


@pytest.mark.parametrize("direction", ("", " ASC", " DESC"))
@pytest.mark.parametrize("placement", ("FIRST", "LAST"))
def test_ordinary_explicit_null_ordering_roundtrips(direction: str, placement: str) -> None:
    sql = f"SELECT a FROM t ORDER BY a{direction} NULLS {placement}"
    expression = assert_roundtrip(sql)
    ordered = expression.args["order"].expressions[0]
    assert isinstance(ordered, vexp.VerticaOrdered)
    assert ordered.args["nulls"].name == placement
    assert ordered.args["nulls_first"] is (placement == "FIRST")


def test_omitted_null_ordering_stays_omitted_and_canonical() -> None:
    expression = assert_roundtrip("SELECT a FROM t ORDER BY a, a DESC")
    assert all(type(item) is exp.Ordered for item in expression.args["order"].expressions)
    assert "NULLS" not in expression.sql(dialect="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t ORDER BY a NULLS FIRST, b DESC NULLS LAST, 1 ASC NULLS FIRST",
        "SELECT * FROM (SELECT a FROM t ORDER BY a NULLS LAST) q",
        "WITH q AS (SELECT a FROM t ORDER BY a NULLS FIRST) SELECT a FROM q",
        "SELECT a FROM t UNION ALL (SELECT a FROM u ORDER BY a NULLS LAST LIMIT 1)",
        "SELECT a FROM t UNION ALL SELECT a FROM u ORDER BY a DESC NULLS FIRST",
        "AT EPOCH LATEST SELECT a FROM t ORDER BY a NULLS LAST",
        "SELECT a /* item */ FROM t ORDER BY a /* null placement */ NULLS FIRST",
    ],
)
def test_explicit_null_ordering_composes_with_query_owners(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert expression.find(vexp.VerticaOrdered) is not None


@pytest.mark.parametrize("placement", ("FIRST", "LAST", "AUTO"))
def test_analytic_window_null_ordering_roundtrips(placement: str) -> None:
    expression = assert_roundtrip(
        f"SELECT ROW_NUMBER() OVER (PARTITION BY k ORDER BY a DESC NULLS {placement}) FROM t"
    )
    ordered = expression.find(vexp.VerticaOrdered)
    assert ordered is not None and ordered.args["nulls"].name == placement
    assert ordered.find_ancestor(exp.Window) is not None


@pytest.mark.parametrize("placement", ("FIRST", "LAST", "AUTO"))
def test_within_group_null_ordering_roundtrips(placement: str) -> None:
    expression = assert_roundtrip(
        f"SELECT LISTAGG(a) WITHIN GROUP (ORDER BY a ASC NULLS {placement}) FROM t"
    )
    ordered = expression.find(vexp.VerticaOrdered)
    assert ordered is not None and ordered.args["nulls"].name == placement
    assert ordered.find_ancestor(exp.WithinGroup) is not None


@pytest.mark.parametrize("placement", ("FIRST", "LAST"))
def test_partitioned_limit_and_top_k_projection_null_ordering_roundtrip(
    placement: str,
) -> None:
    query = f"SELECT a, k FROM t LIMIT 2 OVER (PARTITION BY k ORDER BY a DESC NULLS {placement})"
    expression = assert_roundtrip(query)
    assert isinstance(expression.args["limit"], vexp.PartitionedLimit)

    projection = assert_roundtrip(f"CREATE PROJECTION p AS {query}")
    assert isinstance(projection, vexp.CreateProjection)
    ordered = projection.find(vexp.VerticaOrdered)
    assert ordered is not None
    assert ordered.find_ancestor(vexp.PartitionedLimit) is not None


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT a FROM t ORDER BY a NULLS",
        "SELECT a FROM t ORDER BY a NULLS MIDDLE",
        "SELECT a FROM t ORDER BY a NULLS FIRST NULLS LAST",
        "SELECT a FROM t ORDER BY a NULLS FIRST LAST",
        "SELECT a FROM t ORDER BY a AUTO",
        "SELECT a FROM t ORDER BY a NULLS AUTO",
        "SELECT * FROM t LIMIT 2 OVER (PARTITION BY k ORDER BY a NULLS AUTO)",
        (
            "SELECT * FROM t TIMESERIES slice AS '1 minute' "
            "OVER (PARTITION BY k ORDER BY ts NULLS FIRST)"
        ),
        (
            "SELECT * FROM t MATCH(PARTITION BY k ORDER BY ts NULLS LAST "
            "DEFINE e AS x > 0 PATTERN p AS (e))"
        ),
        "CREATE PROJECTION p AS SELECT a FROM t ORDER BY a NULLS FIRST",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_invalid_null_ordering_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_invalid_null_ordering_does_not_swallow_following_statement(
    error_level: ErrorLevel,
) -> None:
    with pytest.raises(ParseError):
        parse(
            "SELECT a FROM t ORDER BY a NULLS AUTO; SELECT 2",
            read="vertica",
            error_level=error_level,
        )


def test_explicit_null_ordering_survives_analysis_and_tree_operations() -> None:
    expression = parse_one("SELECT a FROM t ORDER BY a NULLS LAST", read="vertica")
    restored = exp.Expr.load(expression.dump())
    copied = expression.copy()
    transformed = expression.transform(lambda node: node)
    for tree in (restored, copied, transformed):
        ordered = tree.find(vexp.VerticaOrdered)
        assert ordered is not None
        assert ordered.parent is tree.args["order"]
        assert ordered.arg_key == "expressions"
        assert ordered.index == 0
        assert tree.sql(dialect="vertica").endswith("ORDER BY a NULLS LAST")

    schema = {"t": {"a": "INT"}}
    for analyzed in (
        qualify(expression.copy(), dialect="vertica", schema=schema),
        optimize(expression.copy(), dialect="vertica", schema=schema),
        annotate_types(expression.copy(), dialect="vertica", schema=schema),
    ):
        ordered = analyzed.find(vexp.VerticaOrdered)
        assert ordered is not None
        assert ordered.args["nulls"].name == "LAST"
        assert "NULLS LAST" in analyzed.sql(dialect="vertica")

    assert list(traverse_scope(expression))
    assert lineage("a", expression, dialect="vertica", schema=schema).name == "a"


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("nested", (False, True))
def test_explicit_null_ordering_fails_atomically_in_foreign_dialects(
    dialect: str, nested: bool
) -> None:
    ordered = vexp.VerticaOrdered(
        this=exp.column("a"),
        desc=False,
        nulls_first=False,
        nulls=exp.var("LAST"),
    )
    expression: exp.Expr = (
        exp.select("a").from_("t").order_by(ordered, copy=False) if nested else ordered
    )
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("this", None),
        ("desc", "DESC"),
        ("nulls_first", None),
        ("nulls", exp.var("MIDDLE")),
        ("with_fill", False),
        ("unknown", False),
    ],
)
def test_malformed_explicit_ordered_ast_fails_strict_generation(field: str, value: object) -> None:
    expression = parse_one("SELECT a FROM t ORDER BY a NULLS FIRST", read="vertica")
    ordered = expression.find(vexp.VerticaOrdered)
    assert ordered is not None
    ordered.set(field, value)
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_auto_requires_documented_owner() -> None:
    ordered = vexp.VerticaOrdered(
        this=exp.column("a"),
        desc=None,
        nulls_first=False,
        nulls=exp.var("AUTO"),
    )
    with pytest.raises(UnsupportedError):
        ordered.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
