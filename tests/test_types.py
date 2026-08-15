"""Vertica scalar and complex data type regressions."""

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
            "CREATE TABLE t (a INT, b INTEGER, c SMALLINT, d TINYINT, e REAL)",
            "CREATE TABLE t (a BIGINT, b BIGINT, c BIGINT, d BIGINT, e DOUBLE PRECISION)",
        ),
        (
            "CREATE TABLE t (a LONG VARCHAR, b LONG VARBINARY, c BINARY VARYING(32))",
            "CREATE TABLE t (a LONG VARCHAR, b LONG VARBINARY, c VARBINARY(32))",
        ),
        (
            "CREATE TABLE t (a TIMESTAMP, b TIMESTAMPTZ, c TIME, d TIMETZ)",
            "CREATE TABLE t (a TIMESTAMP, b TIMESTAMPTZ, c TIME, d TIMETZ)",
        ),
    ],
)
def test_scalar_type_roundtrips(sql: str, expected: str) -> None:
    assert_roundtrip(sql, expected)


def test_native_complex_type_roundtrip() -> None:
    expression = assert_roundtrip(
        "CREATE TABLE t ("
        "a ARRAY[VARCHAR(50), 5], "
        "b SET[VARCHAR], "
        "c ROW(x INT, y ARRAY[DATE], z SET[ROW(k UUID), 20])"
        ")",
        "CREATE TABLE t ("
        "a ARRAY[VARCHAR(50), 5], "
        "b SET[VARCHAR], "
        "c ROW(x BIGINT, y ARRAY[DATE], z SET[ROW(k UUID), 20])"
        ")",
    )

    kinds = [column.args["kind"] for column in expression.this.expressions]
    assert [kind.this for kind in kinds] == [
        exp.DType.ARRAY,
        exp.DType.SET,
        exp.DType.STRUCT,
    ]


def test_collection_binary_size_roundtrip() -> None:
    assert_roundtrip(
        "CREATE TABLE t (a ARRAY[INT](32000), b SET[VARCHAR(50)](64000))",
        "CREATE TABLE t (a ARRAY[BIGINT](32000), b SET[VARCHAR(50)](64000))",
    )


def test_collection_and_row_value_constructors() -> None:
    expression = assert_roundtrip(
        "SELECT ARRAY[1, 2], SET[1, 2], ROW(1, 'x')",
        "SELECT ARRAY[1, 2], SET[1, 2], ROW(1, 'x')",
    )
    assert expression.find(vexp.SetLiteral)


def test_row_literal_field_names() -> None:
    expression = assert_roundtrip(
        "SELECT ROW('Amy' AS name, 2 AS id, FALSE AS current) AS student",
        "SELECT ROW('Amy' AS name, 2 AS id, FALSE AS current) AS student",
    )
    row = expression.find(exp.Struct)
    assert row
    assert [field.name for field in row.expressions] == ["name", "id", "current"]


def test_row_literal_outer_field_alias_list() -> None:
    expression = assert_roundtrip(
        "SELECT ROW('Amy', 2, FALSE) AS student(name, id, current)",
        "SELECT ROW('Amy', 2, FALSE) AS student(name, id, current)",
    )
    assert expression.find(vexp.RowAlias)


def test_zero_based_array_access_and_exclusive_slice() -> None:
    assert_roundtrip(
        "SELECT values[0], values[1:3] FROM measurements",
        "SELECT values[0], values[1:3] FROM measurements",
    )


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (a ARRAY[])",
        "CREATE TABLE t (a ARRAY[INT,])",
        "CREATE TABLE t (a ARRAY[INT)",
        "CREATE TABLE t (a ARRAY[INT]())",
        "CREATE TABLE t (a ROW())",
    ],
)
def test_complex_types_reject_incomplete_declarations(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")
