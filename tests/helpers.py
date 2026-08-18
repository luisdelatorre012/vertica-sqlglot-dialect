"""Shared assertions for dialect parser and generator tests."""

from __future__ import annotations

from sqlglot import exp, parse, parse_one


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


def assert_script_roundtrip(script: str, expected_types: list[type[exp.Expr]]) -> list[exp.Expr]:
    """Assert multi-statement parse boundaries and, for each resulting
    statement, the same semantic-parsing and stable-generation contract
    ``assert_roundtrip`` asserts for a single statement."""

    raw_statements = parse(script, read="vertica")
    assert [type(statement) for statement in raw_statements] == expected_types

    statements: list[exp.Expr] = []
    for statement in raw_statements:
        assert statement is not None
        assert not isinstance(statement, exp.Command)

        generated = statement.sql(dialect="vertica")
        reparsed = parse_one(generated, read="vertica")
        assert reparsed == statement
        assert reparsed.sql(dialect="vertica") == generated

        pretty = statement.sql(dialect="vertica", pretty=True)
        pretty_reparsed = parse_one(pretty, read="vertica")
        assert pretty_reparsed == statement

        restored = exp.Expr.load(statement.dump())
        assert restored == statement

        statements.append(statement)

    return statements
