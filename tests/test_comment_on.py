"""Semantic COMMENT ON statements."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "kind", "target_type"),
    [
        (
            "COMMENT ON AGGREGATE FUNCTION db.s.total(x INT) IS 'aggregate'",
            "AGGREGATE FUNCTION",
            vexp.RoutineSignature,
        ),
        (
            "COMMENT ON ANALYTIC FUNCTION s.ranker() IS 'analytic'",
            "ANALYTIC FUNCTION",
            vexp.RoutineSignature,
        ),
        ("COMMENT ON FUNCTION s.clean(VARCHAR(20)) IS 'scalar'", "FUNCTION", vexp.RoutineSignature),
        (
            "COMMENT ON TRANSFORM FUNCTION s.explode_map(m MAP) IS 'transform'",
            "TRANSFORM FUNCTION",
            vexp.RoutineSignature,
        ),
        ("COMMENT ON COLUMN db.s.t.c IS 'owner''s column'", "COLUMN", exp.Column),
        (
            "COMMENT ON CONSTRAINT pk_orders ON db.s.orders IS 'primary key'",
            "CONSTRAINT",
            vexp.CommentConstraintTarget,
        ),
        ("COMMENT ON LIBRARY s.analytics IS 'library'", "LIBRARY", exp.Table),
        ("COMMENT ON NODE v_node0001 IS 'node'", "NODE", exp.Table),
        ("COMMENT ON PROJECTION db.s.orders_super IS 'projection'", "PROJECTION", exp.Table),
        ("COMMENT ON SCHEMA db.analytics IS 'schema'", "SCHEMA", exp.Table),
        ("COMMENT ON SEQUENCE db.s.order_id_seq IS 'sequence'", "SEQUENCE", exp.Table),
        ("COMMENT ON TABLE db.s.orders IS 'table'", "TABLE", exp.Table),
        ("COMMENT ON VIEW db.s.active_orders IS 'view'", "VIEW", exp.Table),
    ],
)
def test_comment_on_target_matrix(sql: str, kind: str, target_type: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CommentOn)
    assert isinstance(expression, exp.Comment)
    assert expression.args["kind"] == kind
    target = expression.args["this"]
    assert isinstance(target, target_type)
    assert target.parent is expression
    assert target.arg_key == "this"
    value = expression.args["expression"]
    assert isinstance(value, exp.Literal) and value.is_string
    assert value.parent is expression
    assert value.arg_key == "expression"


@pytest.mark.parametrize(
    "sql",
    [
        "COMMENT ON AGGREGATE FUNCTION f() IS NULL",
        "COMMENT ON ANALYTIC FUNCTION f(INT) IS NULL",
        "COMMENT ON FUNCTION f(x INT, y NUMERIC(10, 2)) IS NULL",
        "COMMENT ON TRANSFORM FUNCTION f(x ARRAY[INT]) IS NULL",
        "COMMENT ON COLUMN s.t.c IS NULL",
        "COMMENT ON CONSTRAINT c ON s.t IS NULL",
        "COMMENT ON LIBRARY l IS NULL",
        "COMMENT ON NODE n IS NULL",
        "COMMENT ON PROJECTION p IS NULL",
        "COMMENT ON SCHEMA s IS NULL",
        "COMMENT ON SEQUENCE q IS NULL",
        "COMMENT ON TABLE t IS NULL",
        "COMMENT ON VIEW v IS NULL",
    ],
)
def test_comment_on_null_removal(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.CommentOn)
    assert isinstance(expression.args["expression"], exp.Null)


def test_comment_on_constraint_and_column_ownership_is_structured() -> None:
    constraint = parse_one("COMMENT ON CONSTRAINT pk ON db.s.t IS 'x'", read="vertica")
    assert isinstance(constraint, vexp.CommentOn)
    target = constraint.this
    assert isinstance(target, vexp.CommentConstraintTarget)
    assert isinstance(target.this, exp.Identifier)
    assert isinstance(target.expression, exp.Table)
    assert target.expression.parent is target
    assert target.expression.arg_key == "expression"

    column = parse_one("COMMENT ON COLUMN db.s.t.c IS 'x'", read="vertica")
    assert isinstance(column, vexp.CommentOn)
    assert isinstance(column.this, exp.Column)
    assert [column.this.catalog, column.this.db, column.this.table, column.this.name] == [
        "db",
        "s",
        "t",
        "c",
    ]


def test_comment_on_copy_transform_optimizer_and_batch_boundaries() -> None:
    expression = parse_one("COMMENT ON TABLE s.t IS 'x'", read="vertica")
    copied = expression.copy()
    assert copied == expression
    transformed = expression.transform(
        lambda node: (
            exp.to_identifier("renamed")
            if isinstance(node, exp.Identifier) and node.name == "t"
            else node
        )
    )
    assert transformed.sql(dialect="vertica") == "COMMENT ON TABLE s.renamed IS 'x'"
    optimized = optimize(expression.copy())
    assert isinstance(optimized, vexp.CommentOn)
    assert isinstance(parse_one(optimized.sql(dialect="vertica"), read="vertica"), vexp.CommentOn)

    statements = parse(
        "/* before */ COMMENT ON TABLE t IS 'x'; COMMENT ON VIEW v IS NULL; SELECT 1",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CommentOn,
        vexp.CommentOn,
        exp.Select,
    ]
    assert statements[0].comments == [" before "]


@pytest.mark.parametrize(
    "sql",
    [
        "COMMENT TABLE t IS 'x'",
        "COMMENT IF EXISTS ON TABLE t IS 'x'",
        "COMMENT ON MATERIALIZED VIEW v IS 'x'",
        "COMMENT ON DATABASE d IS 'x'",
        "COMMENT ON TABLE IS 'x'",
        "COMMENT ON TABLE db.s.extra.t IS 'x'",
        "COMMENT ON COLUMN c IS 'x'",
        "COMMENT ON COLUMN db.s.extra.t.c IS 'x'",
        "COMMENT ON CONSTRAINT s.pk ON t IS 'x'",
        "COMMENT ON CONSTRAINT pk t IS 'x'",
        "COMMENT ON CONSTRAINT pk ON IS 'x'",
        "COMMENT ON NODE s.n IS 'x'",
        "COMMENT ON SCHEMA catalog.db.s IS 'x'",
        "COMMENT ON FUNCTION f IS 'x'",
        "COMMENT ON FUNCTION f(x INT extra) IS 'x'",
        "COMMENT ON FUNCTION f(INT,) IS 'x'",
        "COMMENT ON FUNCTION f(INT IS 'x'",
        "COMMENT ON TABLE t 'x'",
        "COMMENT ON TABLE t IS",
        "COMMENT ON TABLE t IS 1",
        "COMMENT ON TABLE t IS TRUE",
        "COMMENT ON TABLE t IS E'x'",
        "COMMENT ON TABLE t IS 'x' CASCADE",
        "COMMENT ON \"TABLE\" t IS 'x'",
        "COMMENT ON TΑBLE t IS 'x'",  # noqa: RUF001 - intentional confusable keyword
    ],
)
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_malformed_comment_on_fails_atomically(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def test_comment_on_strict_programmatic_ast_validation() -> None:
    valid = parse_one("COMMENT ON TABLE s.t IS 'x'", read="vertica")
    assert isinstance(valid, vexp.CommentOn)
    malformed = (
        vexp.CommentOn(this=exp.to_table("t"), kind="DATABASE", expression=exp.Literal.string("x")),
        vexp.CommentOn(this=exp.to_table("t"), kind="TABLE", expression=exp.Literal.number("1")),
        vexp.CommentOn(this=exp.to_identifier("t"), kind="TABLE", expression=exp.Null()),
        vexp.CommentOn(this=exp.to_table("s.n"), kind="NODE", expression=exp.Null()),
        vexp.CommentOn(this=exp.to_table("d.s.x"), kind="SCHEMA", expression=exp.Null()),
        vexp.CommentOn(this=exp.column("c"), kind="COLUMN", expression=exp.Null()),
        vexp.CommentOn(this=exp.to_table("t"), kind="CONSTRAINT", expression=exp.Null()),
        vexp.CommentOn(this=exp.to_table("f"), kind="FUNCTION", expression=exp.Null()),
        vexp.CommentOn(
            this=vexp.RoutineSignature(
                this=exp.to_table("f"), expressions=[exp.Literal.string("INT")]
            ),
            kind="FUNCTION",
            expression=exp.Null(),
        ),
        vexp.CommentOn(
            this=exp.to_table("t"),
            kind="TABLE",
            expression=exp.Null(),
            exists=True,
        ),
    )
    for expression in malformed:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_comment_on_foreign_generation_is_atomic() -> None:
    roots = (
        parse_one("COMMENT ON TABLE s.t IS 'x'", read="vertica"),
        parse_one("COMMENT ON FUNCTION s.f(INT) IS NULL", read="vertica"),
        parse_one("COMMENT ON CONSTRAINT pk ON s.t IS NULL", read="vertica"),
    )
    for expression in roots:
        for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
            with pytest.raises((UnsupportedError, ValueError)):
                expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)

    leaf = vexp.CommentConstraintTarget(
        this=exp.to_identifier("pk"), expression=exp.to_table("s.t")
    )
    for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
        with pytest.raises((UnsupportedError, ValueError)):
            leaf.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
