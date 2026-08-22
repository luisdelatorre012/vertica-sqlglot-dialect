"""Vertica-only query clause regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

ALL_PARSE_LEVELS = tuple(ErrorLevel)


def test_timeseries_clause() -> None:
    expression = assert_roundtrip(
        "SELECT slice_time, TS_FIRST_VALUE(price, 'const') FROM ticks "
        "WHERE venue = 'X' "
        "TIMESERIES slice_time AS '1 minute' "
        "OVER (PARTITION BY symbol ORDER BY ts)",
        "SELECT slice_time, TS_FIRST_VALUE(price, 'const') FROM ticks "
        "WHERE venue = 'X' "
        "TIMESERIES slice_time AS '1 minute' "
        "OVER (PARTITION BY symbol ORDER BY ts)",
    )
    assert isinstance(expression.args["timeseries"], vexp.Timeseries)


def test_timeseries_without_partition_and_with_outer_order() -> None:
    expression = assert_roundtrip(
        "SELECT slice_time, TS_LAST_VALUE(value IGNORE NULLS, 'LINEAR') FROM readings "
        "TIMESERIES slice_time AS '5 minutes' OVER (ORDER BY measured_at) "
        "ORDER BY slice_time",
    )
    assert not expression.args["timeseries"].args.get("partition_by")
    assert expression.args.get("order")


def test_event_series_interpolate_join() -> None:
    expression = assert_roundtrip(
        "SELECT b.symbol, b.ts, a.price FROM bids AS b "
        "LEFT JOIN asks AS a ON b.symbol = a.symbol "
        "AND b.ts INTERPOLATE PREVIOUS VALUE a.ts",
        "SELECT b.symbol, b.ts, a.price FROM bids AS b "
        "LEFT JOIN asks AS a ON b.symbol = a.symbol "
        "AND b.ts INTERPOLATE PREVIOUS VALUE a.ts",
    )
    assert expression.find(vexp.Interpolate)


def test_partitioned_limit() -> None:
    expression = assert_roundtrip(
        "SELECT customer_id, order_id, total FROM orders "
        "LIMIT 3 OVER (PARTITION BY customer_id ORDER BY total DESC)",
        "SELECT customer_id, order_id, total FROM orders "
        "LIMIT 3 OVER (PARTITION BY customer_id ORDER BY total DESC)",
    )
    assert isinstance(expression.args["limit"], vexp.PartitionedLimit)
    assert isinstance(expression.args["limit"], exp.Limit)


def test_partitioned_limit_requires_partition_key() -> None:
    with pytest.raises(ParseError, match="requires PARTITION BY"):
        assert_roundtrip("SELECT * FROM orders LIMIT 3 OVER (ORDER BY total DESC)")


def test_match_event_pattern() -> None:
    expression = assert_roundtrip(
        "SELECT user_id, event_name FROM events "
        "MATCH ("
        "PARTITION BY user_id "
        "ORDER BY event_timestamp "
        "DEFINE start AS event_name = 'start', Any AS TRUE, finish AS event_name = 'finish' "
        "PATTERN conversion AS (start Any* finish) "
        "ROWS MATCH FIRST EVENT"
        ")",
        "SELECT user_id, event_name FROM events "
        "MATCH ("
        "PARTITION BY user_id "
        "ORDER BY event_timestamp "
        "DEFINE start AS event_name = 'start', Any AS TRUE, finish AS event_name = 'finish' "
        "PATTERN conversion AS (start Any* finish) "
        "ROWS MATCH FIRST EVENT"
        ")",
    )
    match = expression.args["match"]
    assert isinstance(match, vexp.Match)
    assert len(match.args["definitions"]) == 3
    assert match.args["pattern"].name == "start Any* finish"


@pytest.mark.parametrize("quantifier", ["??", "*?", "*+", "+", "+?", "++", "?+"])
def test_match_pattern_quantifiers_and_all_events(quantifier: str) -> None:
    expression = assert_roundtrip(
        "SELECT * FROM events MATCH ("
        "ORDER BY event_timestamp "
        "DEFINE A AS event_name = 'a', B AS event_name = 'b' "
        f"PATTERN p AS (A B{quantifier}) ROWS MATCH ALL EVENTS)"
    )
    match = expression.args["match"]
    assert match.args["rows_match"].name == "ALL EVENTS"
    assert match.args["pattern"].name == f"A B{quantifier}"


def test_standard_query_remains_semantic() -> None:
    expression = assert_roundtrip(
        "WITH totals AS ("
        "SELECT customer_id, SUM(amount) AS amount FROM orders GROUP BY customer_id"
        ") "
        "SELECT customer_id, amount, ROW_NUMBER() OVER (ORDER BY amount DESC) AS rank "
        "FROM totals ORDER BY customer_id",
    )
    assert isinstance(expression, exp.Select)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t TIMESERIES slice_time '1 minute' OVER (ORDER BY ts)",
        "SELECT * FROM t TIMESERIES slice_time AS OVER (ORDER BY ts)",
        "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER ORDER BY ts",
        "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER ()",
        "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER (PARTITION BY ORDER BY ts)",
        "SELECT * FROM t WHERE a.ts INTERPOLATE SIDEWAYS VALUE b.ts",
        "SELECT * FROM t WHERE a.ts INTERPOLATE PREVIOUS VALUE",
        "SELECT * FROM t LIMIT 2, 3 OVER (PARTITION BY k ORDER BY ts)",
        "SELECT * FROM t LIMIT 3 OVER PARTITION BY k ORDER BY ts",
        "SELECT * FROM t LIMIT 3 OVER (PARTITION BY k)",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_query_extensions_reject_missing_required_components(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "body",
    [
        "ORDER BY ts PATTERN p AS (A)",
        "ORDER BY ts DEFINE A event = 1 PATTERN p AS (A)",
        "ORDER BY ts DEFINE A AS PATTERN p AS (A)",
        "ORDER BY ts DEFINE A AS TRUE PATTERN AS (A)",
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS A)",
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A",
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A) ROWS FIRST EVENT",
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A) ROWS MATCH LAST EVENT",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_match_rejects_malformed_components(body: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(
            f"SELECT * FROM events MATCH ({body})",
            read="vertica",
            error_level=error_level,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM events MATCH (DEFINE A AS TRUE PATTERN p AS (A))",
        "SELECT * FROM events MATCH (ORDER BY ts PATTERN p AS (A))",
        "SELECT * FROM events MATCH (ORDER BY ts DEFINE A AS TRUE PATTERN p AS ())",
        "SELECT * FROM events MATCH (ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A)",
        "SELECT * FROM events MATCH (PARTITION BY ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A))",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_match_required_components_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def test_query_extension_type_metadata_is_preserved() -> None:
    expression = annotate_types(
        parse_one(
            "SELECT * FROM bids AS b LEFT JOIN asks AS a ON b.ts INTERPOLATE NEXT VALUE a.ts",
            read="vertica",
        ),
        dialect="vertica",
    )

    interpolate = expression.find(vexp.Interpolate)
    assert interpolate is not None
    assert interpolate.is_type(exp.DType.BOOLEAN)


@pytest.mark.parametrize(
    ("sql", "comment"),
    [
        (
            "SELECT slice_time FROM t TIMESERIES /* timeseries boundary */ "
            "slice_time AS '1 minute' OVER (ORDER BY ts)",
            "timeseries boundary",
        ),
        (
            "SELECT * FROM events MATCH /* match boundary */ ("
            "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A))",
            "match boundary",
        ),
        (
            "SELECT * FROM a LEFT JOIN b ON a.ts "
            "INTERPOLATE /* interpolate boundary */ PREVIOUS VALUE b.ts",
            "interpolate boundary",
        ),
    ],
)
def test_query_extension_comments_are_preserved(sql: str, comment: str) -> None:
    expression = assert_roundtrip(sql)

    assert comment in expression.sql(dialect="vertica")


@pytest.mark.parametrize(
    "malformed",
    [
        "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER ()",
        "SELECT * FROM events MATCH (ORDER BY ts PATTERN p AS (A))",
        "SELECT * FROM t WHERE a.ts INTERPOLATE PREVIOUS VALUE",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_malformed_query_extensions_do_not_swallow_following_statements(
    malformed: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse(f"{malformed}; SELECT 1", read="vertica", error_level=error_level)


def test_query_extension_programmatic_nodes_are_strictly_validated() -> None:
    valid_timeseries = parse_one(
        "SELECT slice_time FROM t TIMESERIES slice_time AS '1 minute' OVER (ORDER BY ts)",
        read="vertica",
    )
    valid_match = parse_one(
        "SELECT * FROM events MATCH ("
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A) ROWS MATCH FIRST EVENT)",
        read="vertica",
    )
    valid_interpolate = parse_one(
        "SELECT * FROM a LEFT JOIN b ON a.ts INTERPOLATE PREVIOUS VALUE b.ts",
        read="vertica",
    )

    invalid_nodes: list[exp.Expr] = [
        vexp.Timeseries(),
        vexp.Timeseries(
            this=exp.to_identifier("slice_time"),
            expression=exp.Literal.string("1 minute"),
            partition_by=[],
            order=exp.Order(expressions=[]),
        ),
        vexp.TimeseriesSlice(this=exp.var("slice_time")),
        vexp.Interpolate(this=exp.column("a"), direction=exp.var("SIDEWAYS")),
        vexp.Interpolate(
            this=exp.column("a"), expression=exp.column("b"), direction=exp.var("SIDEWAYS")
        ),
        vexp.MatchDefinition(this=exp.to_identifier("A")),
        vexp.Match(
            order=exp.Order(expressions=[exp.Ordered(this=exp.column("ts"))]),
            definitions=[],
            pattern_name=exp.to_identifier("p"),
            pattern=exp.var("A"),
        ),
        vexp.Match(
            order=exp.Order(expressions=[exp.Ordered(this=exp.column("ts"))]),
            definitions=[vexp.MatchDefinition(this=exp.to_identifier("A"), expression=exp.true())],
            pattern_name=exp.to_identifier("p"),
            pattern=exp.var("A"),
            rows_match=exp.var("LAST EVENT"),
        ),
    ]

    invalid_nested = [valid_timeseries.copy(), valid_match.copy(), valid_interpolate.copy()]
    invalid_nested[0].args["timeseries"].set("order", None)
    invalid_nested[1].args["match"].set("definitions", [])
    nested_interpolate = invalid_nested[2].find(vexp.Interpolate)
    assert isinstance(nested_interpolate, vexp.Interpolate)
    nested_interpolate.set("expression", None)

    for expression in [*invalid_nodes, *invalid_nested]:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "unsupported_level", [ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_query_extensions_remain_atomic_in_foreign_dialects(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    expressions = [
        parse_one(
            "SELECT slice_time FROM t TIMESERIES slice_time AS '1 minute' OVER (ORDER BY ts)",
            read="vertica",
        ),
        parse_one(
            "SELECT * FROM events MATCH (ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A))",
            read="vertica",
        ),
        parse_one(
            "SELECT * FROM a LEFT JOIN b ON a.ts INTERPOLATE PREVIOUS VALUE b.ts",
            read="vertica",
        ),
    ]

    for expression in expressions:
        custom = next(
            node
            for node in expression.walk()
            if isinstance(node, (vexp.Timeseries, vexp.Match, vexp.Interpolate))
        )
        for candidate in (custom, expression):
            with pytest.raises((UnsupportedError, ValueError)):
                candidate.sql(dialect=dialect, unsupported_level=unsupported_level)
