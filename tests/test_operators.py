"""Vertica mathematical operator and semantic-flag regressions."""

from __future__ import annotations

from sqlglot import Dialect, exp, parse_one

from tests.helpers import assert_roundtrip


def test_vertica_mathematical_operators() -> None:
    expression = assert_roundtrip(
        "SELECT 117.32 // 2.5, !! 5, 4.98!, @ -5.0",
        "SELECT 117.32 // 2.5, 5!, 4.98!, @ -5.0",
    )

    assert isinstance(expression.expressions[0], exp.IntDiv)
    assert isinstance(expression.expressions[1], exp.Factorial)
    assert isinstance(expression.expressions[2], exp.Factorial)
    assert isinstance(expression.expressions[3], exp.Abs)


def test_postfix_factorial_precedence() -> None:
    expression = assert_roundtrip("SELECT -4!, (-4)!, 5! + 1")

    assert isinstance(expression.expressions[0], exp.Neg)
    assert isinstance(expression.expressions[0].this, exp.Factorial)
    assert isinstance(expression.expressions[1], exp.Factorial)
    assert isinstance(expression.expressions[2], exp.Add)
    assert isinstance(expression.expressions[2].this, exp.Factorial)


def test_root_operators_normalize_to_semantic_functions() -> None:
    expression = assert_roundtrip(
        "SELECT |/ 25.0, ||/ 27.0",
        "SELECT SQRT(25.0), CBRT(27.0)",
    )
    assert isinstance(expression.expressions[0], exp.Sqrt)
    assert isinstance(expression.expressions[1], exp.Cbrt)


def test_vertica_division_and_concat_semantics() -> None:
    dialect = Dialect.get_or_raise("vertica")
    assert dialect.TYPED_DIVISION is False
    assert dialect.CONCAT_COALESCE is False

    expression = parse_one("SELECT 4 / 2, CONCAT(a, b)", read="vertica")
    division = expression.expressions[0]
    concat = expression.expressions[1]

    assert isinstance(division, exp.Div)
    assert division.args["typed"] is False
    assert isinstance(concat, exp.Concat)
    assert concat.args["coalesce"] is False
