"""Shared assertions for dialect parser and generator tests."""

from __future__ import annotations

from sqlglot import exp, parse_one


def assert_roundtrip(sql: str, expected: str | None = None) -> exp.Expr:
    """Assert semantic parsing and stable Vertica generation."""

    expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, exp.Command)

    generated = expression.sql(dialect="vertica")
    if expected is not None:
        assert generated == expected

    reparsed = parse_one(generated, read="vertica")
    assert reparsed == expression
    assert reparsed.sql(dialect="vertica") == generated

    pretty = expression.sql(dialect="vertica", pretty=True)
    pretty_reparsed = parse_one(pretty, read="vertica")
    assert pretty_reparsed == expression

    restored = exp.Expr.load(expression.dump())
    assert restored == expression
    return expression
