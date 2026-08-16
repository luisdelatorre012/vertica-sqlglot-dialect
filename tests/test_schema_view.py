"""Vertica CREATE SCHEMA and CREATE VIEW option regressions."""

from __future__ import annotations

import contextlib

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_create_schema_full_options() -> None:
    sql = (
        "CREATE SCHEMA IF NOT EXISTS tenant.analytics "
        "AUTHORIZATION data_owner "
        "DEFAULT INCLUDE SCHEMA PRIVILEGES "
        "DISK_QUOTA '20G'"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert expression.kind == "SCHEMA"
    assert expression.args["exists"] is True
    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        vexp.SchemaAuthorizationProperty,
        vexp.DefaultInheritedPrivilegesProperty,
        vexp.DiskQuotaProperty,
    ]


@pytest.mark.parametrize(
    "clause",
    [
        "DEFAULT INCLUDE PRIVILEGES",
        "DEFAULT INCLUDE SCHEMA PRIVILEGES",
        "DEFAULT EXCLUDE PRIVILEGES",
        "DEFAULT EXCLUDE SCHEMA PRIVILEGES",
    ],
)
def test_create_schema_default_privilege_forms(clause: str) -> None:
    sql = f"CREATE SCHEMA analytics {clause}"
    expression = assert_roundtrip(sql, sql)
    assert isinstance(
        expression.find(vexp.DefaultInheritedPrivilegesProperty),
        vexp.DefaultInheritedPrivilegesProperty,
    )


def test_create_schema_generator_orders_properties_without_mutation() -> None:
    canonical = (
        "CREATE SCHEMA analytics AUTHORIZATION alice DEFAULT EXCLUDE PRIVILEGES DISK_QUOTA '1G'"
    )
    expression = parse_one(canonical, read="vertica")
    properties = expression.args["properties"]
    reversed_properties = list(reversed(properties.expressions))
    properties.set("expressions", reversed_properties)

    assert expression.sql(dialect="vertica") == canonical
    assert properties.expressions == reversed_properties


@pytest.mark.parametrize(
    "privileges",
    [
        "INCLUDE PRIVILEGES",
        "INCLUDE SCHEMA PRIVILEGES",
        "EXCLUDE PRIVILEGES",
        "EXCLUDE SCHEMA PRIVILEGES",
    ],
)
def test_create_view_inherited_privilege_forms(privileges: str) -> None:
    sql = (
        f"CREATE OR REPLACE VIEW analytics.order_totals (customer_id, total) "
        f"{privileges} AS "
        "SELECT customer_id, SUM(amount) AS total FROM orders GROUP BY customer_id"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert expression.kind == "VIEW"
    assert expression.args["replace"] is True
    assert isinstance(expression.this, exp.Schema)
    assert isinstance(
        expression.find(vexp.InheritedPrivilegesProperty),
        vexp.InheritedPrivilegesProperty,
    )


def test_simple_schema_and_view_remain_canonical() -> None:
    schema = assert_roundtrip("CREATE SCHEMA analytics", "CREATE SCHEMA analytics")
    view = assert_roundtrip(
        "CREATE VIEW analytics.ids AS SELECT id FROM source",
        "CREATE VIEW analytics.ids AS SELECT id FROM source",
    )

    assert isinstance(schema, exp.Create)
    assert schema.args.get("properties") is None
    assert isinstance(view, exp.Create)
    assert view.args.get("properties") is None


def test_schema_and_view_interoperate_with_postgres_ast() -> None:
    schema = parse_one("CREATE SCHEMA tenant.analytics", read="postgres")
    view = parse_one(
        "CREATE OR REPLACE VIEW analytics.ids (id) AS SELECT id FROM source",
        read="postgres",
    )

    assert schema.sql(dialect="vertica") == "CREATE SCHEMA tenant.analytics"
    assert view.sql(dialect="vertica") == (
        "CREATE OR REPLACE VIEW analytics.ids (id) AS SELECT id FROM source"
    )


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "CREATE OR REPLACE SCHEMA analytics",
            "OR REPLACE SCHEMA is not supported",
        ),
        (
            "CREATE SCHEMA analytics AUTHORIZATION",
            "AUTHORIZATION requires a user name",
        ),
        (
            "CREATE SCHEMA analytics DEFAULT PRIVILEGES",
            "DEFAULT requires INCLUDE or EXCLUDE PRIVILEGES",
        ),
        (
            "CREATE SCHEMA analytics DISK_QUOTA 20",
            "DISK_QUOTA requires a quoted quota",
        ),
        (
            "CREATE SCHEMA analytics DISK_QUOTA '1G' AUTHORIZATION alice",
            "out-of-order CREATE SCHEMA clause",
        ),
        (
            "CREATE VIEW analytics.ids (id BIGINT) AS SELECT id FROM source",
            "column lists require one or more column names",
        ),
        (
            "CREATE VIEW analytics.ids INCLUDE AS SELECT id FROM source",
            "Expected PRIVILEGES after INCLUDE or EXCLUDE",
        ),
        (
            "CREATE VIEW analytics.ids SELECT id FROM source",
            "requires AS followed by a query",
        ),
        (
            "CREATE VIEW analytics.ids AS",
            "requires a SELECT query",
        ),
        (
            "CREATE VIEW analytics.ids AS SELECT 1 DISK_QUOTA '1G'",
            "Unexpected CREATE VIEW clause",
        ),
    ],
)
def test_create_schema_and_view_reject_invalid_options(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


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
    ("sql", "action_type"),
    [
        ("ALTER VIEW v OWNER TO alice", vexp.ViewOwnerToAction),
        ('ALTER VIEW db.s."v" OWNER TO "owner"', vexp.ViewOwnerToAction),
        ("ALTER VIEW s.v SET SCHEMA archive", vexp.ViewSetSchemaAction),
        ("ALTER VIEW v INCLUDE PRIVILEGES", vexp.ViewPrivilegeAction),
        ("ALTER VIEW v EXCLUDE SCHEMA PRIVILEGES", vexp.ViewPrivilegeAction),
        ("ALTER VIEW v MATERIALIZE PRIVILEGES", vexp.ViewPrivilegeAction),
        ("ALTER VIEW v MATERIALIZE SCHEMA PRIVILEGES", vexp.ViewPrivilegeAction),
        ("ALTER VIEW s.v RENAME TO renamed", vexp.ViewRenameAction),
        (
            "ALTER VIEW db.s.first, db.s.second RENAME TO one, two",
            vexp.ViewRenameAction,
        ),
    ],
)
def test_alter_view_forms_are_typed_and_roundtrip(sql: str, action_type: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterView)
    assert expression.kind == "VIEW"
    assert len(expression.args["actions"]) == 1
    assert isinstance(expression.args["actions"][0], action_type)
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP VIEW v",
        "DROP VIEW IF EXISTS s.v",
        'DROP VIEW IF EXISTS db.s.v, db.s."select", other',
    ],
)
def test_drop_view_is_ordered_typed_and_roundtrips(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.DropViews)
    assert expression.kind == "VIEW"
    _assert_parent_links(expression)


def test_view_rename_preserves_equal_ordered_lists() -> None:
    expression = parse_one("ALTER VIEW s.a, s.b, s.c RENAME TO x, y, z", read="vertica")
    assert isinstance(expression, vexp.AlterView)
    sources = [expression.this, *expression.args["expressions"]]
    action = expression.args["actions"][0]
    assert isinstance(action, vexp.ViewRenameAction)
    assert [source.name for source in sources] == ["a", "b", "c"]
    assert [target.name for target in action.expressions] == ["x", "y", "z"]


def test_view_lifecycle_serialization_transform_optimizer_types_and_boundaries() -> None:
    expression = parse_one("ALTER VIEW s.old RENAME TO new", read="vertica")
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression
    transformed = expression.transform(
        lambda node: (
            exp.to_identifier("newer")
            if isinstance(node, exp.Identifier) and node.name == "new"
            else node
        )
    )
    assert _strict(transformed) == "ALTER VIEW s.old RENAME TO newer"
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterView)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.args["actions"][0].type == exp.DType.UNKNOWN.into_expr()
    assert_roundtrip("/* lead */ ALTER VIEW v OWNER TO u /* tail */")

    statements = parse(
        "CREATE VIEW v AS SELECT 1 AS x; ALTER VIEW v OWNER TO u; DROP VIEW IF EXISTS v, old_v",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        exp.Create,
        vexp.AlterView,
        vexp.DropViews,
    ]
    assert isinstance(statements[0].this, exp.Table)


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER VIEW",
        "ALTER VIEW v",
        "ALTER VIEW v OWNER",
        "ALTER VIEW v OWNER alice",
        "ALTER VIEW v OWNER TO",
        "ALTER VIEW v, w OWNER TO alice",
        "ALTER VIEW v SET",
        "ALTER VIEW v SET OWNER alice",
        "ALTER VIEW v SET SCHEMA",
        "ALTER VIEW v, w SET SCHEMA s",
        "ALTER VIEW v INCLUDE",
        "ALTER VIEW v INCLUDE SCHEMA",
        "ALTER VIEW v MATERIALIZE SCHEMA",
        "ALTER VIEW v, w EXCLUDE PRIVILEGES",
        "ALTER VIEW v RENAME",
        "ALTER VIEW v RENAME x",
        "ALTER VIEW v RENAME TO",
        "ALTER VIEW v, w RENAME TO x",
        "ALTER VIEW v RENAME TO x, y",
        "ALTER VIEW v, RENAME TO x",
        "ALTER VIEW v RENAME TO s.x",
        "ALTER VIEW v OWNER TO u RENAME TO x",
        "DROP VIEW",
        "DROP VIEW v,",
        "DROP IF EXISTS VIEW v",
        "DROP VIEW v IF EXISTS",
        "DROP VIEW v CASCADE",
        "DROP VIEW v RESTRICT",
        "DROP VIEW v, w CASCADE",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_recognized_invalid_view_lifecycle_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'ALTER "VIEW" v OWNER TO u',
        'ALTER VIEW v "OWNER" TO u',
        'ALTER VIEW v OWNER "TO" u',
        'ALTER VIEW v "SET" SCHEMA s',
        'ALTER VIEW v SET "SCHEMA" s',
        'ALTER VIEW v "INCLUDE" PRIVILEGES',
        'ALTER VIEW v INCLUDE "PRIVILEGES"',
        'ALTER VIEW v "MATERIALIZE" PRIVILEGES',
        'ALTER VIEW v "RENAME" TO x',
        'ALTER VIEW v RENAME "TO" x',
        'DROP "VIEW" v',
        'DROP VIEW "IF" EXISTS v',
    ],
)
def test_view_lifecycle_keyword_provenance_and_collisions(sql: str) -> None:
    expression: exp.Expr | None = None
    with contextlib.suppress(ParseError):
        expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, (vexp.AlterView, vexp.DropViews))

    table = parse_one("ALTER TABLE v RENAME TO x", read="vertica")
    local = parse_one("CREATE LOCAL TEMPORARY VIEW v AS SELECT 1", read="vertica")
    assert not isinstance(table, vexp.AlterView)
    assert not isinstance(local, vexp.AlterView)


def test_programmatic_view_lifecycle_generates_exact_sql() -> None:
    sources = [exp.to_table("db.s.a"), exp.to_table("db.s.b")]
    alter = vexp.AlterView(
        this=sources[0],
        expressions=sources[1:],
        kind="VIEW",
        actions=[
            vexp.ViewRenameAction(expressions=[exp.to_identifier("x"), exp.to_identifier("y")])
        ],
    )
    drop = vexp.DropViews(
        this=exp.to_table("s.x"),
        expressions=[exp.to_table("s.y")],
        kind="VIEW",
        exists=True,
    )
    assert _strict(alter) == "ALTER VIEW db.s.a, db.s.b RENAME TO x, y"
    assert _strict(drop) == "DROP VIEW IF EXISTS s.x, s.y"


def test_view_lifecycle_identifiers_share_utf8_and_tokenizer_contract() -> None:
    exact = f"a{'é' * 63}b"
    assert len(exact.encode()) == 128
    assert_roundtrip(f"ALTER VIEW {exact} RENAME TO {exact}")
    assert_roundtrip('DROP VIEW "SELECT", s."VIEW"')
    with pytest.raises(ParseError):
        parse_one(f"ALTER VIEW {exact}é OWNER TO u", read="vertica")
    with pytest.raises(ParseError):
        parse_one(f"ALTER VIEW v OWNER TO {exact}é", read="vertica")
    with pytest.raises(ParseError):
        parse_one("ALTER VIEW SELECT OWNER TO u", read="vertica")

    surrogate = chr(0xD800)
    with pytest.raises(UnsupportedError):
        _strict(
            vexp.DropViews(
                this=exp.Table(this=exp.to_identifier(surrogate, quoted=True)),
                kind="VIEW",
            )
        )


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "ALTER VIEW v OWNER TO u",
        "ALTER VIEW v SET SCHEMA s",
        "ALTER VIEW v MATERIALIZE PRIVILEGES",
        "ALTER VIEW v, w RENAME TO x, y",
        "DROP VIEW IF EXISTS v, w",
    ],
)
def test_view_lifecycle_roots_fail_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        parse_one(sql, read="vertica").sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.AlterView(this=exp.to_table("v"), kind="TABLE", actions=[]),
        vexp.AlterView(this=exp.to_identifier("v"), kind="VIEW", actions=[]),
        vexp.AlterView(this=exp.to_table("v"), kind="VIEW", actions=[]),
        vexp.AlterView(
            this=exp.to_table("v"),
            kind="VIEW",
            actions=vexp.ViewOwnerToAction(this=exp.to_identifier("u")),
        ),
        vexp.AlterView(
            this=exp.to_table("v"),
            expressions={},
            kind="VIEW",
            actions=[vexp.ViewOwnerToAction(this=exp.to_identifier("u"))],
        ),
        vexp.AlterView(
            this=exp.to_table("v"),
            expressions=[exp.to_table("w")],
            kind="VIEW",
            actions=[vexp.ViewOwnerToAction(this=exp.to_identifier("u"))],
        ),
        vexp.AlterView(
            this=exp.to_table("v"),
            kind="VIEW",
            actions=[vexp.ViewRenameAction(expressions=[])],
        ),
        vexp.AlterView(
            this=exp.to_table("v"),
            kind="VIEW",
            actions=[vexp.ViewPrivilegeAction(this=exp.var("UNKNOWN"))],
        ),
        vexp.AlterView(
            this=exp.to_table("v"),
            kind="VIEW",
            actions=[vexp.ViewPrivilegeAction(this=exp.var("INCLUDE"), schema="yes")],
        ),
        vexp.DropViews(kind="VIEW"),
        vexp.DropViews(this=exp.to_identifier("v"), kind="VIEW"),
        vexp.DropViews(this=exp.to_table("v"), expressions={}, kind="VIEW"),
        vexp.DropViews(this=exp.to_table("v"), kind="VIEW", exists="yes"),
        vexp.DropViews(this=exp.to_table("v"), kind="VIEW", cascade=True),
    ],
)
def test_malformed_programmatic_view_asts_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_detached_view_actions_fail_in_foreign_dialects() -> None:
    leaves: tuple[exp.Expr, ...] = (
        vexp.ViewOwnerToAction(this=exp.to_identifier("u")),
        vexp.ViewSetSchemaAction(this=exp.to_identifier("s")),
        vexp.ViewPrivilegeAction(this=exp.var("INCLUDE"), schema=True),
        vexp.ViewRenameAction(expressions=[exp.to_identifier("x")]),
    )
    for leaf in leaves:
        assert _strict(leaf)
        for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
            with pytest.raises((UnsupportedError, ValueError)):
                leaf.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
