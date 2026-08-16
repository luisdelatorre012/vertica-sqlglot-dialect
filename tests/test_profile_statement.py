"""Semantic executable Vertica PROFILE statement regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

MERGE_SQL = (
    "MERGE INTO target AS t USING source AS s ON t.id=s.id "
    "WHEN MATCHED THEN UPDATE SET value=s.value"
)


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize(
    ("sql", "body_type"),
    [
        ("PROFILE SELECT 1", exp.Select),
        ("PROFILE WITH x AS (SELECT 1) SELECT * FROM x", exp.Select),
        ("PROFILE SELECT 1 UNION ALL SELECT 2", exp.Union),
        ("PROFILE INSERT INTO target VALUES (1)", exp.Insert),
        ("PROFILE UPDATE target SET value=1 WHERE id=2", exp.Update),
        ("PROFILE DELETE FROM target WHERE id=2", exp.Delete),
        ("PROFILE COPY target FROM STDIN", vexp.VerticaCopy),
        (f"PROFILE {MERGE_SQL}", exp.Merge),
    ],
)
def test_documented_profile_statement_roots_are_traversable(
    sql: str, body_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.ProfileStatement)
    assert isinstance(expression.this, body_type)
    assert expression.this.parent is expression
    assert expression.this.arg_key == "this"
    assert expression.this.index is None
    _assert_parent_links(expression)


def test_profile_retains_body_hints_and_ordinary_comments() -> None:
    select = assert_roundtrip("/* lead */ PROFILE SELECT /*+ LABEL(prof) */ 1 /* tail */")
    copy = assert_roundtrip("PROFILE COPY /*+ LABEL(load) */ target FROM STDIN")
    merge = assert_roundtrip(f"PROFILE MERGE /*+ LABEL(m) */ {MERGE_SQL[6:]}")

    assert isinstance(select.this.args.get("hint"), exp.Hint)
    assert isinstance(copy.this.args.get("hint"), exp.Hint)
    assert isinstance(merge.this, vexp.VerticaMerge)
    assert isinstance(merge.this.args.get("hint"), exp.Hint)
    select_sql = _strict(select)
    assert select_sql.count("lead") == 1
    assert select_sql.count("tail") == 1


def test_semicolon_ownership_and_multi_statement_boundaries_are_exact() -> None:
    statements = parse(
        "PROFILE SELECT 1; UPDATE target SET value=2; PROFILE DELETE FROM target WHERE id=3;",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.ProfileStatement,
        exp.Update,
        vexp.ProfileStatement,
    ]
    assert isinstance(statements[0].this, exp.Select)
    assert isinstance(statements[2].this, exp.Delete)


def test_serialization_copy_transform_optimizer_and_types_traverse_body() -> None:
    expression = parse_one("PROFILE SELECT value FROM source WHERE id=1", read="vertica")
    copied = expression.copy()
    assert copied == expression
    assert copied is not expression
    _assert_parent_links(copied)

    restored = exp.Expr.load(expression.dump())
    assert restored == expression
    assert isinstance(restored, vexp.ProfileStatement)
    _assert_parent_links(restored)

    transformed = expression.transform(
        lambda node: (
            exp.column("amount") if isinstance(node, exp.Column) and node.name == "value" else node
        )
    )
    assert _strict(transformed) == "PROFILE SELECT amount FROM source WHERE id = 1"

    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.ProfileStatement)
    assert isinstance(optimized.this, exp.Select)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    _assert_parent_links(optimized)

    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.type == exp.DType.UNKNOWN.into_expr()
    assert annotated.this.find(exp.Column) is not None
    assert _strict(annotated).startswith("PROFILE SELECT")


@pytest.mark.parametrize(
    "sql",
    [
        "PROFILE",
        "PROFILE PROFILE SELECT 1",
        "PROFILE VALUES (1)",
        "PROFILE VALUES (1) UNION ALL VALUES (2)",
        "PROFILE CREATE TABLE t (id INT)",
        "PROFILE ALTER TABLE t ADD COLUMN value INT",
        "PROFILE DROP TABLE t",
        "PROFILE TRUNCATE TABLE t",
        "PROFILE CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 8",
        "PROFILE ALTER PROFILE p RENAME TO p2",
        "PROFILE DROP PROFILE p",
        "PROFILE BEGIN",
        "PROFILE START TRANSACTION",
        "PROFILE COMMIT",
        "PROFILE ROLLBACK",
        "PROFILE GRANT SELECT ON t TO u",
        "PROFILE EXPLAIN SELECT 1",
        "PROFILE CALL f()",
        "PROFILE SELECT",
        "PROFILE INSERT INTO target",
        "PROFILE UPDATE target SET",
        "PROFILE DELETE FROM",
        "PROFILE COPY target FROM",
        "PROFILE MERGE INTO target",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_invalid_or_unsupported_profile_bodies_fail_closed(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError) as caught:
        parse_one(sql, read="vertica", error_level=error_level)
    assert "Command" not in str(caught.value)


@pytest.mark.parametrize(
    "sql",
    [
        '"PROFILE" SELECT 1',
        "'PROFILE' SELECT 1",
        "PROFıLE SELECT 1",  # noqa: RUF001 - intentional confusable keyword
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_profile_statement_keyword_requires_exact_unquoted_ascii_provenance(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def test_profile_statement_does_not_collide_with_lifecycle_or_identifiers() -> None:
    lifecycle = [
        parse_one("CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 8", read="vertica"),
        parse_one("ALTER PROFILE p RENAME TO p2", read="vertica"),
        parse_one("DROP PROFILE p2", read="vertica"),
    ]
    assert [type(item) for item in lifecycle] == [
        vexp.CreateProfile,
        vexp.AlterProfile,
        vexp.DropProfiles,
    ]
    query = parse_one("SELECT profile FROM profile", read="vertica")
    assert isinstance(query, exp.Select)
    assert not isinstance(query, vexp.ProfileStatement)


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_profile_statement_fails_atomically_in_foreign_dialects(dialect: str) -> None:
    expression = parse_one("PROFILE SELECT 1", read="vertica")
    nested = exp.Subquery(this=expression.copy())
    for candidate in (expression, nested):
        with pytest.raises((UnsupportedError, ValueError)):
            candidate.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.ProfileStatement(),
        vexp.ProfileStatement(this=[]),
        vexp.ProfileStatement(this=exp.Literal.number("1")),
        vexp.ProfileStatement(this=exp.Values(expressions=[exp.Tuple(expressions=[])])),
        vexp.ProfileStatement(
            this=exp.Union(
                this=exp.select("1"),
                expression=exp.Values(expressions=[exp.Tuple(expressions=[])]),
            )
        ),
        vexp.ProfileStatement(this=exp.Create(this=exp.to_table("t"), kind="TABLE")),
        vexp.ProfileStatement(this=exp.Command(this="VACUUM", expression="t")),
        vexp.ProfileStatement(this=vexp.ProfileStatement(this=exp.select("1"))),
        _set_arg(vexp.ProfileStatement(this=exp.select("1")), "bogus", False),
        _set_arg(vexp.ProfileStatement(this=exp.select("1")), "bogus", []),
        _set_arg(vexp.ProfileStatement(this=exp.select("1")), "bogus", {}),
    ],
)
def test_malformed_programmatic_profile_statements_fail_atomically(
    expression: exp.Expr,
) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)
