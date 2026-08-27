"""Q37 PostgreSQL lowerings for source-compatible Vertica scalar functions."""

from __future__ import annotations

import subprocess
import sys

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify

from sqlglot_vertica import expressions as vexp

ALL_LEVELS = tuple(ErrorLevel)


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize(
    ("source", "expected", "target_type"),
    [
        (
            "SELECT GETDATE()",
            "SELECT CAST(STATEMENT_TIMESTAMP() AS TIMESTAMP)",
            exp.Cast,
        ),
        (
            "SELECT GETUTCDATE()",
            "SELECT CAST(STATEMENT_TIMESTAMP() AT TIME ZONE 'UTC' AS TIMESTAMP)",
            exp.Cast,
        ),
    ],
)
def test_statement_timestamp_report_cases_lower_to_postgres(
    level: ErrorLevel,
    source: str,
    expected: str,
    target_type: type[exp.Expr],
) -> None:
    expression = parse_one(source, read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=level)

    assert target == expected
    reparsed = parse_one(target, read="postgres")
    assert isinstance(reparsed.expressions[0], target_type)
    assert "CURRENT_TIMESTAMP" not in target
    assert "NOW(" not in target


def test_repeated_statement_timestamps_keep_one_statement_clock() -> None:
    expression = parse_one(
        "SELECT GETDATE() = GETDATE(), GETUTCDATE() = GETUTCDATE()",
        read="vertica",
    )
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    assert target.count("STATEMENT_TIMESTAMP()") == 4
    assert target.count("AT TIME ZONE 'UTC'") == 2
    assert target.count("AS TIMESTAMP") == 4
    parse_one(target, read="postgres")


def test_statement_timestamps_preserve_multi_statement_boundaries_and_comments() -> None:
    expressions = parse(
        "SELECT GETDATE() /* local statement time */; SELECT GETUTCDATE() /* utc statement time */",
        read="vertica",
    )
    targets = [
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
        for expression in expressions
    ]

    assert len(targets) == 2
    assert "local statement time" in targets[0]
    assert "utc statement time" in targets[1]
    assert len(parse("; ".join(targets), read="postgres")) == 2


def test_statement_timestamp_target_types_are_timestamp_without_time_zone() -> None:
    expression = parse_one("SELECT GETDATE(), GETUTCDATE()", read="vertica")
    target = parse_one(
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE),
        read="postgres",
    )
    typed = annotate_types(target, dialect="postgres")

    assert [item.type.this for item in typed.expressions] == [
        exp.DType.TIMESTAMP,
        exp.DType.TIMESTAMP,
    ]


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_reported_one_argument_to_char_lowers_to_integral_text_cast(level: ErrorLevel) -> None:
    expression = parse_one("SELECT TO_CHAR(YEAR(CURRENT_DATE) - 2)", read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=level)

    assert target == "SELECT CAST(YEAR(CURRENT_DATE) - 2 AS TEXT)"
    reparsed = annotate_types(parse_one(target, read="postgres"), dialect="postgres")
    assert isinstance(reparsed.expressions[0], exp.Cast)
    assert reparsed.expressions[0].type.this is exp.DType.TEXT


@pytest.mark.parametrize(
    "source",
    [
        "SELECT TO_CHAR(1)",
        "SELECT TO_CHAR(CAST(1 AS SMALLINT))",
        "SELECT TO_CHAR(CAST(1 AS BIGINT))",
        "SELECT TO_CHAR(YEAR(CURRENT_DATE) - 2)",
    ],
)
def test_statically_integral_to_char_inputs_lower(source: str) -> None:
    expression = parse_one(source, read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    assert "CAST(" in target
    assert target.endswith(" AS TEXT)")
    parse_one(target, read="postgres")


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize(
    "source",
    [
        "SELECT TO_CHAR(1.5)",
        "SELECT TO_CHAR(CAST('2026-08-27' AS DATE))",
        "SELECT TO_CHAR(CAST('12:00:00' AS TIME))",
        "SELECT TO_CHAR(CAST('2026-08-27 12:00:00' AS TIMESTAMP))",
        "SELECT TO_CHAR(INTERVAL '1 day')",
        "SELECT TO_CHAR(value) FROM t",
    ],
)
def test_unproven_to_char_input_families_remain_atomic(level: ErrorLevel, source: str) -> None:
    expression = parse_one(source, read="vertica")

    with pytest.raises(ValueError, match="statically integral"):
        expression.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize("modifier", (None, "c"))
@pytest.mark.parametrize("pattern", ("", "a", "plain text", "é"))
def test_literal_regexp_like_subset_lowers_to_position(
    level: ErrorLevel, modifier: str | None, pattern: str
) -> None:
    arguments = f"'abc', '{pattern}'" + (f", '{modifier}'" if modifier else "")
    expression = parse_one(f"SELECT REGEXP_LIKE({arguments})", read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=level)

    assert target == f"SELECT POSITION('{pattern}' IN 'abc') > 0"
    reparsed = parse_one(target, read="postgres")
    assert isinstance(reparsed.expressions[0], exp.GT)
    assert isinstance(reparsed.expressions[0].this, exp.StrPosition)


def test_regexp_like_position_lowering_preserves_null_and_empty_pattern_shape() -> None:
    expression = parse_one("SELECT REGEXP_LIKE(value, '') FROM t", read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)

    assert target == "SELECT POSITION('' IN value) > 0 FROM t"
    reparsed = parse_one(target, read="postgres")
    position = reparsed.find(exp.StrPosition)
    assert position is not None
    assert isinstance(position.this, exp.Column)
    assert position.args["substr"].this == ""


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize("pattern", (".", "^a", "a$", "a*", "a+", "a?", "[a]", "a|b", "(a)", r"\d"))
def test_regex_active_patterns_remain_atomic(level: ErrorLevel, pattern: str) -> None:
    expression = vexp.VerticaRegexpLike(
        this=exp.RegexpLike(
            this=exp.Literal.string("abc"),
            expression=exp.Literal.string(pattern),
        ),
        modifiers=[],
    )

    with pytest.raises(ValueError, match="Perl REGEXP_LIKE metacharacter"):
        expression.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize("modifier", ("b", "i", "m", "n", "x", "C", "cc"))
def test_non_equivalent_regexp_modifiers_remain_atomic(level: ErrorLevel, modifier: str) -> None:
    expression = parse_one(f"SELECT REGEXP_LIKE('abc', 'a', '{modifier}')", read="vertica")

    with pytest.raises(ValueError, match="omitted or 'c' mode"):
        expression.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_dynamic_regexp_pattern_remains_atomic(level: ErrorLevel) -> None:
    expression = parse_one("SELECT REGEXP_LIKE(value, pattern) FROM t", read="vertica")

    with pytest.raises(ValueError, match="literal pattern"):
        expression.sql(dialect="postgres", unsupported_level=level)


def test_invalid_unicode_regexp_pattern_fails_without_encoding_exception() -> None:
    expression = vexp.VerticaRegexpLike(
        this=exp.RegexpLike(
            this=exp.Literal.string("abc"),
            expression=exp.Literal.string("\ud800"),
        ),
        modifiers=[],
    )

    with pytest.raises(ValueError, match="valid UTF-8"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.IGNORE)


def test_scalar_lowerings_survive_tree_operations_and_analysis() -> None:
    expression = parse_one(
        "SELECT GETDATE() AS started, TO_CHAR(YEAR(CURRENT_DATE) - 2) AS prior, "
        "REGEXP_LIKE(name, 'abc') AS matches FROM t",
        read="vertica",
    )
    schema = {"t": {"name": "VARCHAR"}}
    trees = (
        exp.Expr.load(expression.dump()),
        expression.copy(),
        expression.transform(lambda node: node),
        qualify(expression.copy(), dialect="vertica", schema=schema),
        optimize(expression.copy(), dialect="vertica", schema=schema),
    )

    for tree in trees:
        assert tree.find(vexp.StatementTimestamp) is not None
        assert tree.find(vexp.VerticaToChar) is not None
        assert tree.find(vexp.VerticaRegexpLike) is not None
        target = tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
        assert "STATEMENT_TIMESTAMP()" in target
        assert " AS TEXT)" in target
        assert "POSITION('abc' IN" in target
        parse_one(target, read="postgres")


@pytest.mark.parametrize(
    "expression",
    [
        vexp.StatementTimestamp(extra=False),
        vexp.UtcStatementTimestamp(extra=False),
        vexp.VerticaToChar(this=exp.column("x")),
        vexp.VerticaRegexpLike(this=exp.column("x"), modifiers=[]),
    ],
)
def test_malformed_programmatic_wrappers_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(ValueError):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.IGNORE)


@pytest.mark.parametrize("dialect", ("duckdb", "mysql", "sqlite"))
@pytest.mark.parametrize(
    "source",
    [
        "SELECT GETDATE()",
        "SELECT GETUTCDATE()",
        "SELECT TO_CHAR(1)",
        "SELECT REGEXP_LIKE('abc', 'a')",
    ],
)
def test_other_foreign_dialects_remain_atomic(dialect: str, source: str) -> None:
    expression = parse_one(source, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("foreign_first", (False, True))
def test_postgres_scalar_patch_survives_import_order_and_dispatch_cache(
    foreign_first: bool,
) -> None:
    prefix = (
        "from sqlglot import exp; from sqlglot.generators.postgres import PostgresGenerator; "
        "PostgresGenerator().generate(exp.select('x')); "
        if foreign_first
        else ""
    )
    code = prefix + (
        "from sqlglot import ErrorLevel, parse_one; import sqlglot_vertica; "
        "sources=('SELECT GETDATE()', 'SELECT GETUTCDATE()', "
        "'SELECT TO_CHAR(YEAR(CURRENT_DATE) - 2)', "
        "\"SELECT REGEXP_LIKE('abc', 'a')\"); "
        "targets=[parse_one(s, read='vertica').sql(dialect='postgres', "
        "unsupported_level=ErrorLevel.RAISE) for s in sources]; "
        "assert all(parse_one(t, read='postgres') for t in targets)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
