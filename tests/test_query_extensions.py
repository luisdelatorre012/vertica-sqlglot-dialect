"""Vertica-only query clause regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp
from sqlglot.errors import ParseError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


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
        "SELECT * FROM t WHERE a.ts INTERPOLATE SIDEWAYS VALUE b.ts",
        "SELECT * FROM t WHERE a.ts INTERPOLATE PREVIOUS VALUE",
        "SELECT * FROM t LIMIT 2, 3 OVER (PARTITION BY k ORDER BY ts)",
        "SELECT * FROM t LIMIT 3 OVER PARTITION BY k ORDER BY ts",
        "SELECT * FROM t LIMIT 3 OVER (PARTITION BY k)",
    ],
)
def test_query_extensions_reject_missing_required_components(sql: str) -> None:
    with pytest.raises(ParseError):
        assert_roundtrip(sql)


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
def test_match_rejects_malformed_components(body: str) -> None:
    with pytest.raises(ParseError):
        assert_roundtrip(f"SELECT * FROM events MATCH ({body})")
