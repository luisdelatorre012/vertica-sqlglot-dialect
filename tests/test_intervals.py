"""Vertica interval literal, qualifier, and datatype regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT INTERVAL '1 year 2 months' YEAR TO MONTH",
            "SELECT INTERVAL '1 year 2 months' YEAR TO MONTH",
        ),
        (
            "SELECT INTERVAL '@ 3 days 4 hours ago' DAY TO SECOND(3)",
            "SELECT INTERVAL '@ 3 days 4 hours ago' DAY TO SECOND(3)",
        ),
        (
            "SELECT INTERVAL '1.234' SECOND(3)",
            "SELECT INTERVAL '1.234' SECOND(3)",
        ),
        (
            "SELECT INTERVAL(4) '2 hours 3.709384766 seconds' DAY TO SECOND(5)",
            "SELECT INTERVAL(4) '2 hours 3.709384766 seconds' DAY TO SECOND(5)",
        ),
        (
            "SELECT INTERVALYM '1 2'",
            "SELECT INTERVAL '1 2' YEAR TO MONTH",
        ),
    ],
)
def test_interval_literal_qualifiers(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    assert expression.find(exp.Interval)


def test_interval_column_type_qualifiers() -> None:
    assert_roundtrip(
        "CREATE TABLE t ("
        "a INTERVAL, "
        "b INTERVAL(4), "
        "c INTERVAL SECOND(3), "
        "d INTERVAL DAY TO SECOND(5), "
        "e INTERVAL YEAR TO MONTH"
        ")",
        "CREATE TABLE t ("
        "a INTERVAL, "
        "b INTERVAL(4), "
        "c INTERVAL SECOND(3), "
        "d INTERVAL DAY TO SECOND(5), "
        "e INTERVAL YEAR TO MONTH"
        ")",
    )


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT INTERVAL '1' SECOND(7)",
        "SELECT INTERVAL '1' SECOND(1.5)",
        "SELECT INTERVAL '1' DAY(2)",
        "SELECT INTERVAL '1' DAY TO MINUTE(2)",
        "SELECT INTERVAL '1' MONTH TO YEAR",
        "SELECT INTERVAL '1' DAY TO YEAR",
        "CREATE TABLE t (duration INTERVAL DAY TO MONTH)",
    ],
)
def test_invalid_interval_qualifiers(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")
