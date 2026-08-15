"""Vertica named-sequence DDL regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_create_sequence_full_behavior() -> None:
    sql = (
        "CREATE SEQUENCE IF NOT EXISTS db.analytics.order_ids "
        "INCREMENT BY -5 MINVALUE -100 MAXVALUE 100 "
        "START WITH 10 CACHE 20 CYCLE"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert expression.kind == "SEQUENCE"
    assert expression.args["exists"] is True
    assert isinstance(expression.this, exp.Table)
    assert [part.name for part in expression.this.parts] == ["db", "analytics", "order_ids"]

    options = expression.find(exp.SequenceProperties)
    assert isinstance(options, exp.SequenceProperties)
    assert options.args["increment"].to_py() == -5
    assert options.args["minvalue"].to_py() == -100
    assert options.args["maxvalue"].to_py() == 100
    assert options.args["start"].to_py() == 10
    assert options.args["cache"].to_py() == 20
    assert [option.name for option in options.args["options"]] == ["CYCLE"]


def test_create_sequence_all_no_forms() -> None:
    sql = "CREATE SEQUENCE ids NO MINVALUE NO MAXVALUE NO CACHE NO CYCLE"
    expression = assert_roundtrip(sql, sql)

    options = expression.find(exp.SequenceProperties)
    assert isinstance(options, exp.SequenceProperties)
    assert options.args.get("minvalue") is None
    assert options.args.get("maxvalue") is None
    assert options.args.get("cache") is None
    assert [option.name for option in options.args["options"]] == [
        "NO MINVALUE",
        "NO MAXVALUE",
        "NO CACHE",
        "NO CYCLE",
    ]


def test_create_sequence_integer_boundaries() -> None:
    sql = (
        "CREATE SEQUENCE limits "
        "INCREMENT BY -9223372036854775808 "
        "MINVALUE -9223372036854775808 "
        "MAXVALUE 9223372036854775807 "
        "START WITH 0 CACHE 0 NO CYCLE"
    )
    assert_roundtrip(sql, sql)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "CREATE SEQUENCE ids INCREMENT -2 START 10",
            "CREATE SEQUENCE ids INCREMENT BY -2 START WITH 10",
        ),
        (
            "CREATE SEQUENCE ids INCREMENT +2 START +10",
            "CREATE SEQUENCE ids INCREMENT BY 2 START WITH 10",
        ),
        ("CREATE SEQUENCE ids", "CREATE SEQUENCE ids"),
    ],
)
def test_create_sequence_optional_keywords_are_canonicalized(sql: str, expected: str) -> None:
    assert_roundtrip(sql, expected)


def test_alter_sequence_full_behavior() -> None:
    sql = (
        "ALTER SEQUENCE db.analytics.order_ids "
        "INCREMENT BY -2 MINVALUE -100 MAXVALUE 100 "
        "RESTART WITH 5 CACHE 25 CYCLE"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Alter)
    assert expression.kind == "SEQUENCE"
    assert len(expression.actions) == 1
    options = expression.actions[0]
    assert isinstance(options, exp.SequenceProperties)
    assert options.args["start"].to_py() == 5


def test_alter_sequence_all_no_forms() -> None:
    sql = (
        "ALTER SEQUENCE analytics.order_ids "
        "NO MINVALUE NO MAXVALUE RESTART WITH -5 NO CACHE NO CYCLE"
    )
    expression = assert_roundtrip(sql, sql)

    options = expression.actions[0]
    assert isinstance(options, exp.SequenceProperties)
    assert [option.name for option in options.args["options"]] == [
        "NO MINVALUE",
        "NO MAXVALUE",
        "NO CACHE",
        "NO CYCLE",
    ]


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "ALTER SEQUENCE ids INCREMENT -2 RESTART 10",
            "ALTER SEQUENCE ids INCREMENT BY -2 RESTART WITH 10",
        ),
        ("ALTER SEQUENCE ids RENAME TO new_ids", "ALTER SEQUENCE ids RENAME TO new_ids"),
        (
            "ALTER SEQUENCE analytics.ids SET SCHEMA archive",
            "ALTER SEQUENCE analytics.ids SET SCHEMA archive",
        ),
        (
            "ALTER SEQUENCE analytics.ids SET SCHEMA TO archive",
            "ALTER SEQUENCE analytics.ids SET SCHEMA archive",
        ),
        (
            "ALTER SEQUENCE analytics.ids OWNER TO data_owner",
            "ALTER SEQUENCE analytics.ids OWNER TO data_owner",
        ),
    ],
)
def test_alter_sequence_behavior_and_metadata_forms(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, exp.Alter)


def test_alter_sequence_metadata_action_types() -> None:
    rename = parse_one("ALTER SEQUENCE ids RENAME TO new_ids", read="vertica")
    set_schema = parse_one("ALTER SEQUENCE ids SET SCHEMA archive", read="vertica")
    owner = parse_one("ALTER SEQUENCE ids OWNER TO alice", read="vertica")

    assert isinstance(rename.args["actions"][0], exp.AlterRename)
    assert isinstance(set_schema.args["actions"][0], vexp.SequenceSetSchemaAction)
    assert isinstance(owner.args["actions"][0], vexp.SequenceOwnerToAction)


def test_drop_multiple_sequences() -> None:
    sql = "DROP SEQUENCE IF EXISTS analytics.ids, archive.old_ids, bare_ids"
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Drop)
    assert expression.kind == "SEQUENCE"
    assert expression.args["exists"] is True
    assert len(expression.expressions) == 2


def test_sequence_ast_interoperates_with_postgres() -> None:
    postgres = parse_one(
        "CREATE SEQUENCE analytics.ids START WITH 10 INCREMENT BY 2 "
        "MINVALUE 1 MAXVALUE 100 CACHE 20 CYCLE",
        read="postgres",
    )
    assert postgres.sql(dialect="vertica") == (
        "CREATE SEQUENCE analytics.ids INCREMENT BY 2 MINVALUE 1 MAXVALUE 100 "
        "START WITH 10 CACHE 20 CYCLE"
    )

    vertica = parse_one(
        "CREATE SEQUENCE analytics.ids INCREMENT BY 2 START WITH 10 CACHE 20 CYCLE",
        read="vertica",
    )
    assert vertica.sql(dialect="postgres") == (
        "CREATE SEQUENCE analytics.ids START WITH 10 INCREMENT BY 2 CACHE 20 CYCLE"
    )


def test_sequence_generator_orders_no_options_without_mutation() -> None:
    canonical = "CREATE SEQUENCE ids NO MINVALUE NO MAXVALUE NO CACHE NO CYCLE"
    expression = parse_one(canonical, read="vertica")
    options = expression.find(exp.SequenceProperties)
    assert isinstance(options, exp.SequenceProperties)
    reversed_options = list(reversed(options.args["options"]))
    options.set("options", reversed_options)

    assert expression.sql(dialect="vertica") == canonical
    assert options.args["options"] == reversed_options


@pytest.mark.parametrize(
    "options",
    [
        exp.SequenceProperties(owned=exp.column("orders.id")),
        exp.SequenceProperties(options=[exp.var("ORDER")]),
        exp.SequenceProperties(cache=True),
    ],
)
def test_sequence_generator_rejects_foreign_options(
    options: exp.SequenceProperties,
) -> None:
    expression = exp.Create(
        this=exp.table_("ids"),
        kind="SEQUENCE",
        properties=exp.Properties(expressions=[options]),
    )

    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_drop_sequence_generator_rejects_foreign_cascade() -> None:
    expression = exp.Drop(this=exp.table_("ids"), kind="SEQUENCE", cascade=True)
    with pytest.raises(UnsupportedError, match="does not support CASCADE or RESTRICT"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "CREATE OR REPLACE SEQUENCE ids",
            "OR REPLACE SEQUENCE is not supported",
        ),
        (
            "CREATE SEQUENCE ids START WITH 1 INCREMENT BY 2",
            "Out-of-order SEQUENCE clause INCREMENT",
        ),
        (
            "CREATE SEQUENCE ids MINVALUE 1 NO MINVALUE",
            "Duplicate or conflicting SEQUENCE MINVALUE",
        ),
        (
            "CREATE SEQUENCE ids CACHE 10 NO CACHE",
            "Duplicate or conflicting SEQUENCE CACHE",
        ),
        (
            "CREATE SEQUENCE ids CYCLE NO CYCLE",
            "Duplicate or conflicting SEQUENCE CYCLE",
        ),
        (
            "CREATE SEQUENCE ids RESTART WITH 1",
            "Unexpected or out-of-order CREATE SEQUENCE clause",
        ),
        (
            "ALTER SEQUENCE ids",
            "requires behavior options or one metadata action",
        ),
        (
            "ALTER SEQUENCE ids RESTART WITH 1 INCREMENT BY 2",
            "Out-of-order SEQUENCE clause INCREMENT",
        ),
        (
            "ALTER SEQUENCE ids MINVALUE 1 NO MINVALUE",
            "Duplicate or conflicting SEQUENCE MINVALUE",
        ),
        (
            "ALTER SEQUENCE ids INCREMENT BY 1 RENAME TO other",
            "cannot combine behavior options with metadata actions",
        ),
        (
            "ALTER SEQUENCE ids RENAME TO other OWNER TO alice",
            "Unexpected ALTER SEQUENCE clause",
        ),
        (
            "ALTER SEQUENCE ids RENAME",
            "ALTER SEQUENCE RENAME requires TO",
        ),
        (
            "ALTER SEQUENCE ids RENAME TO",
            "RENAME TO requires a new name",
        ),
        (
            "ALTER SEQUENCE ids SET SCHEMA",
            "SET SCHEMA requires a schema name",
        ),
        (
            "ALTER SEQUENCE ids OWNER",
            "ALTER SEQUENCE OWNER requires TO",
        ),
        (
            "ALTER SEQUENCE ids OWNER TO",
            "OWNER TO requires an owner name",
        ),
        (
            "ALTER SEQUENCE ids START WITH 1",
            "requires behavior options or one metadata action",
        ),
        (
            "DROP SEQUENCE ids CASCADE",
            "does not support CASCADE or RESTRICT",
        ),
        (
            "DROP SEQUENCE ids RESTRICT",
            "does not support CASCADE or RESTRICT",
        ),
        (
            "DROP SEQUENCE ids,",
            "requires a name after each comma",
        ),
    ],
)
def test_sequence_ddl_rejects_conflicts_and_invalid_order(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("clause", "name"),
    [
        ("INCREMENT BY 1.5", "INCREMENT"),
        ("MINVALUE 1.5", "MINVALUE"),
        ("MAXVALUE 1.5", "MAXVALUE"),
        ("START WITH 1.5", "START"),
        ("CACHE 1.5", "CACHE"),
    ],
)
def test_create_sequence_requires_integer_options(clause: str, name: str) -> None:
    with pytest.raises(ParseError, match=rf"SEQUENCE {name} requires an integer"):
        parse_one(f"CREATE SEQUENCE ids {clause}", read="vertica")


def test_alter_sequence_requires_integer_restart() -> None:
    with pytest.raises(ParseError, match="SEQUENCE RESTART requires an integer"):
        parse_one("ALTER SEQUENCE ids RESTART WITH 1.5", read="vertica")
