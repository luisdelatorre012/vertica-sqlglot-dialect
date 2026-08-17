"""Vertica DROP TABLE grammar regressions."""

from __future__ import annotations

import contextlib

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for arg_key, value in parent.args.items():
            if isinstance(value, exp.Expr):
                assert value.parent is parent
                assert value.arg_key == arg_key
                assert value.index is None
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    if isinstance(child, exp.Expr):
                        assert child.parent is parent
                        assert child.arg_key == arg_key
                        assert child.index == index


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE t",
        "DROP TABLE IF EXISTS t",
        "DROP TABLE s.t",
        "DROP TABLE db.s.t",
        "DROP TABLE t CASCADE",
        "DROP TABLE IF EXISTS db.s.t CASCADE",
    ],
)
def test_single_target_drop_table_stays_canonical(sql: str) -> None:
    expression = assert_roundtrip(sql, sql)
    assert type(expression) is exp.Drop
    assert expression.kind == "TABLE"
    assert expression.args.get("expressions") is None
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE t1, t2",
        "DROP TABLE IF EXISTS t1, t2",
        "DROP TABLE session_scratch, s.daily_stage, db.s.results",
        "DROP TABLE IF EXISTS db.s.t1, s.t2, t3 CASCADE",
        'DROP TABLE t, "CASCADE"',
        'DROP TABLE "SELECT", s."VIEW"',
    ],
)
def test_multi_target_drop_table_is_ordered_typed_and_roundtrips(sql: str) -> None:
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression, vexp.DropTables)
    assert expression.kind == "TABLE"
    _assert_parent_links(expression)


def test_drop_table_preserves_target_order_and_qualification() -> None:
    expression = parse_one("DROP TABLE IF EXISTS db.s.a, s.b, c CASCADE", read="vertica")
    assert isinstance(expression, vexp.DropTables)
    targets = [expression.this, *expression.args["expressions"]]
    assert [target.sql(dialect="vertica") for target in targets] == ["db.s.a", "s.b", "c"]
    assert expression.args["exists"] is True
    assert expression.args["cascade"] is True


def test_drop_table_contextual_names_remain_names() -> None:
    named_cascade = assert_roundtrip("DROP TABLE cascade", "DROP TABLE cascade")
    assert type(named_cascade) is exp.Drop
    assert named_cascade.this.name == "cascade"
    assert named_cascade.args.get("cascade") is False

    named_and_modifier = assert_roundtrip(
        "DROP TABLE cascade CASCADE", "DROP TABLE cascade CASCADE"
    )
    assert named_and_modifier.this.name == "cascade"
    assert named_and_modifier.args.get("cascade") is True

    named_local = assert_roundtrip("DROP TABLE local", "DROP TABLE local")
    assert named_local.this.name == "local"


def test_drop_table_serialization_transform_optimizer_types_and_boundaries() -> None:
    expression = parse_one("DROP TABLE IF EXISTS s.a, s.b CASCADE", read="vertica")
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression
    transformed = expression.transform(
        lambda node: (
            exp.to_identifier("c")
            if isinstance(node, exp.Identifier) and node.name == "b"
            else node
        )
    )
    assert _strict(transformed) == "DROP TABLE IF EXISTS s.a, s.c CASCADE"
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.DropTables)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert isinstance(annotated, vexp.DropTables)
    assert_roundtrip("/* lead */ DROP TABLE t1, t2 /* tail */")

    statements = parse(
        "CREATE TABLE t1 (id INT); DROP TABLE t1; DROP TABLE IF EXISTS t2, old_t2 CASCADE",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        exp.Create,
        exp.Drop,
        vexp.DropTables,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE",
        "DROP TABLE t,",
        "DROP TABLE ,t",
        "DROP IF EXISTS TABLE t",
        "DROP TABLE IF EXISTS",
        "DROP TABLE t IF EXISTS",
        "DROP TABLE t RESTRICT",
        "DROP TABLE t1, t2 RESTRICT",
        "DROP TABLE t CASCADE RESTRICT",
        "DROP TABLE t RESTRICT CASCADE",
        "DROP TABLE t CASCADE, t2",
        "DROP TABLE t CASCADE CASCADE",
        "DROP TABLE t PURGE",
        "DROP TABLE t SYNC",
        "DROP TEMPORARY TABLE t",
        "DROP TEMP TABLE t",
        "DROP MATERIALIZED TABLE t",
        "DROP ICEBERG TABLE t",
        "DROP TABLE a.b.c.d",
        "DROP TABLE t ON CLUSTER c",
        "DROP TABLE t (x)",
        "DROP TABLE SELECT",
        'DROP TABLE t "CASCADE"',
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_recognized_invalid_drop_table_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'DROP "TABLE" t',
        'DROP TABLE "IF" EXISTS t',
        "DROP TABLE t restrict",
        'DROP TABLE t "RESTRICT"',
    ],
)
def test_drop_table_keyword_provenance_and_collisions(sql: str) -> None:
    expression: exp.Expr | None = None
    with contextlib.suppress(ParseError):
        expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, vexp.DropTables)
    assert not (isinstance(expression, exp.Drop) and expression.kind == "TABLE")

    lowercase_cascade = parse_one("DROP TABLE t1, t2 cascade", read="vertica")
    assert isinstance(lowercase_cascade, vexp.DropTables)
    assert lowercase_cascade.args["cascade"] is True
    assert _strict(lowercase_cascade) == "DROP TABLE t1, t2 CASCADE"


def test_drop_table_dispatch_neighbors_are_unchanged() -> None:
    view = parse_one("DROP VIEW v, w", read="vertica")
    assert isinstance(view, vexp.DropViews)
    schema = parse_one("DROP SCHEMA s1, s2 CASCADE", read="vertica")
    assert isinstance(schema, vexp.DropSchemas)
    projection = parse_one("DROP PROJECTION p CASCADE", read="vertica")
    assert type(projection) is exp.Drop
    assert projection.kind == "PROJECTION"
    sequence = parse_one("DROP SEQUENCE s1, s2", read="vertica")
    assert type(sequence) is exp.Drop
    assert sequence.kind == "SEQUENCE"
    table_named_view = parse_one("DROP TABLE view_backup", read="vertica")
    assert type(table_named_view) is exp.Drop
    assert table_named_view.kind == "TABLE"


def test_programmatic_drop_table_generates_exact_sql() -> None:
    single = exp.Drop(this=exp.to_table("db.s.a"), kind="TABLE", exists=True, cascade=True)
    assert _strict(single) == "DROP TABLE IF EXISTS db.s.a CASCADE"

    multiple = vexp.DropTables(
        this=exp.to_table("s.a"),
        expressions=[exp.to_table("s.b"), exp.to_table("c")],
        kind="TABLE",
        exists=True,
        cascade=True,
    )
    assert _strict(multiple) == "DROP TABLE IF EXISTS s.a, s.b, c CASCADE"

    bare = vexp.DropTables(
        this=exp.to_table("a"),
        expressions=[exp.to_table("b")],
        kind="TABLE",
    )
    assert _strict(bare) == "DROP TABLE a, b"


def test_drop_table_identifiers_share_utf8_and_tokenizer_contract() -> None:
    exact = f"a{'é' * 63}b"
    assert len(exact.encode()) == 128
    assert_roundtrip(f"DROP TABLE {exact}, other")
    boundary = f"a{'é' * 62}bc"
    assert len(boundary.encode()) == 127
    assert_roundtrip(f"DROP TABLE {boundary}")
    with pytest.raises(ParseError):
        parse_one(f"DROP TABLE {exact}é", read="vertica")
    with pytest.raises(ParseError):
        parse_one(f"DROP TABLE ok, {exact}é", read="vertica")

    surrogate = chr(0xD800)
    with pytest.raises(UnsupportedError):
        _strict(
            vexp.DropTables(
                this=exp.Table(this=exp.to_identifier(surrogate, quoted=True)),
                expressions=[exp.to_table("b")],
                kind="TABLE",
            )
        )


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE a, b",
        "DROP TABLE IF EXISTS db.s.a, s.b CASCADE",
    ],
)
def test_drop_table_root_fails_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    expression = parse_one(sql, read="vertica")
    for unsupported_level in (ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE):
        with pytest.raises((UnsupportedError, ValueError)):
            expression.sql(dialect=dialect, unsupported_level=unsupported_level)


def test_single_target_drop_table_interoperates_with_canonical_dialects() -> None:
    assert (
        parse_one("DROP TABLE IF EXISTS s.t CASCADE", read="vertica").sql(dialect="postgres")
        == "DROP TABLE IF EXISTS s.t CASCADE"
    )
    foreign = parse_one("DROP TABLE IF EXISTS a CASCADE", read="postgres")
    assert foreign.sql(dialect="vertica") == "DROP TABLE IF EXISTS a CASCADE"

    restricted = parse_one("DROP TABLE a RESTRICT", read="postgres")
    with pytest.raises(UnsupportedError):
        _strict(restricted)
    temporary = parse_one("DROP TEMPORARY TABLE t", read="mysql")
    with pytest.raises(UnsupportedError):
        _strict(temporary)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.DropTables(kind="TABLE"),
        vexp.DropTables(this=exp.to_table("a"), kind="TABLE"),
        vexp.DropTables(this=exp.to_table("a"), expressions={}, kind="TABLE"),
        vexp.DropTables(this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="VIEW"),
        vexp.DropTables(this=exp.to_identifier("a"), expressions=[exp.to_table("b")], kind="TABLE"),
        vexp.DropTables(
            this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="TABLE", exists="yes"
        ),
        vexp.DropTables(
            this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="TABLE", cascade="yes"
        ),
        vexp.DropTables(
            this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="TABLE", restrict=True
        ),
        vexp.DropTables(
            this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="TABLE", purge=True
        ),
        exp.Drop(this=exp.to_table("a"), expressions=[exp.to_table("b")], kind="TABLE"),
        exp.Drop(this=exp.to_table("a"), kind="TABLE", restrict=True),
        exp.Drop(this=exp.to_table("a"), kind="TABLE", purge=True),
        exp.Drop(this=exp.to_table("a"), kind="TABLE", temporary=True),
        exp.Drop(this=exp.to_table("a"), kind="TABLE", materialized=True),
        exp.Drop(
            this=exp.Table(this=exp.to_identifier("t"), catalog=exp.to_identifier("ns")),
            kind="TABLE",
        ),
    ],
)
def test_malformed_programmatic_drop_table_asts_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)
