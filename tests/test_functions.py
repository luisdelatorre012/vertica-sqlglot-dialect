"""Vertica function normalization and generation regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT TIMESTAMPADD(day, 3, occurred_at) FROM events",
            "SELECT TIMESTAMPADD(DAY, 3, occurred_at) FROM events",
        ),
        (
            "SELECT TIMESTAMPDIFF(hour, started_at, ended_at) FROM events",
            "SELECT DATEDIFF(HOUR, started_at, ended_at) FROM events",
        ),
        (
            "SELECT DATEDIFF(day, started_at, ended_at) FROM events",
            "SELECT DATEDIFF(DAY, started_at, ended_at) FROM events",
        ),
        (
            "SELECT ADD_MONTHS(invoice_date, 2) FROM invoices",
            "SELECT ADD_MONTHS(invoice_date, 2) FROM invoices",
        ),
        (
            "SELECT GETDATE(), GETUTCDATE(), SYSDATE, SYSDATE(), CURRENT_TIMESTAMP(3)",
            "SELECT GETDATE(), GETUTCDATE(), GETDATE(), GETDATE(), CURRENT_TIMESTAMP(3)",
        ),
    ],
)
def test_datetime_functions(sql: str, expected: str) -> None:
    assert_roundtrip(sql, expected)


def test_statement_timestamp_nodes_are_distinct_from_transaction_timestamp() -> None:
    expression = parse_one(
        "SELECT GETDATE(), GETUTCDATE(), SYSDATE, CURRENT_TIMESTAMP", read="vertica"
    )

    assert isinstance(expression.expressions[0], vexp.StatementTimestamp)
    assert not isinstance(expression.expressions[0], vexp.UtcStatementTimestamp)
    assert isinstance(expression.expressions[1], vexp.UtcStatementTimestamp)
    assert isinstance(expression.expressions[2], vexp.StatementTimestamp)
    assert isinstance(expression.expressions[3], exp.CurrentTimestamp)


@pytest.mark.parametrize("name", ["GETDATE", "GETUTCDATE", "SYSDATE"])
def test_statement_timestamp_functions_reject_arguments(name: str) -> None:
    with pytest.raises(ParseError):
        parse_one(f"SELECT {name}(1)", read="vertica")


def test_listagg_within_group_and_parameters() -> None:
    expression = assert_roundtrip(
        "SELECT LISTAGG(city USING PARAMETERS separator=' | ', max_length=4096, "
        "on_overflow='TRUNCATE') WITHIN GROUP (ORDER BY city) FROM places",
        "SELECT LISTAGG(city USING PARAMETERS separator = ' | ', max_length = 4096, "
        "on_overflow = 'TRUNCATE') WITHIN GROUP (ORDER BY city) FROM places",
    )
    listagg = expression.find(vexp.ListAgg)
    assert listagg
    assert [parameter.this.name for parameter in listagg.args["parameters"]] == [
        "separator",
        "max_length",
        "on_overflow",
    ]

    # Keep the conventional two-argument AST mapping available for transpilation.
    legacy = assert_roundtrip(
        "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY ordinal) FROM names",
        "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY ordinal) FROM names",
    )
    assert isinstance(legacy.find(vexp.ListAgg), vexp.ListAgg)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT LISTAGG()",
        "SELECT LISTAGG(city,)",
        "SELECT LISTAGG(city USING PARAMETERS separator)",
        "SELECT LISTAGG(city USING PARAMETERS separator=)",
    ],
)
def test_listagg_rejects_malformed_arguments(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_timeseries_analytic_null_treatment_is_preserved() -> None:
    assert_roundtrip(
        "SELECT TS_FIRST_VALUE(price IGNORE NULLS, 'CONST') FROM ticks",
        "SELECT TS_FIRST_VALUE(price IGNORE NULLS, 'CONST') FROM ticks",
    )


def test_dynamic_datetime_unit_is_not_dropped() -> None:
    assert_roundtrip(
        "SELECT DATEDIFF((CASE WHEN use_days THEN 'day' ELSE 'hour' END), started_at, ended_at)",
        "SELECT DATEDIFF((CASE WHEN use_days THEN 'day' ELSE 'hour' END), started_at, ended_at)",
    )
    assert_roundtrip(
        "SELECT TIMESTAMPADD((unit_name), amount, occurred_at)",
        "SELECT TIMESTAMPADD((unit_name), amount, occurred_at)",
    )


def test_vertica_datetime_function_spellings() -> None:
    assert_roundtrip(
        "SELECT TIME_SLICE(ts, 5, 'MINUTE', 'START'), "
        "DAYOFMONTH(ts), DAYOFWEEK(ts), DAYOFWEEK_ISO(ts), DAYOFYEAR(ts)",
        "SELECT TIME_SLICE(ts, 5, 'MINUTE', 'START'), "
        "DAYOFMONTH(ts), DAYOFWEEK(ts), DAYOFWEEK_ISO(ts), DAYOFYEAR(ts)",
    )
