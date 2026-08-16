"""Semantic Vertica ACCESS POLICY lifecycle regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected", "root_type", "rows", "enabled"),
    [
        (
            "CREATE ACCESS POLICY ON public.customer FOR COLUMN email "
            "CASE WHEN enabled_role('admin') THEN email ELSE 'hidden' END ENABLE",
            "CREATE ACCESS POLICY ON public.customer FOR COLUMN email "
            "CASE WHEN ENABLED_ROLE('admin') THEN email ELSE 'hidden' END ENABLE",
            vexp.CreateAccessPolicy,
            False,
            True,
        ),
        (
            "CREATE ACCESS POLICY ON db.sales.orders FOR ROWS WHERE region = current_user "
            "GRANT TRUSTED DISABLE",
            "CREATE ACCESS POLICY ON db.sales.orders FOR ROWS WHERE region = CURRENT_USER "
            "GRANT TRUSTED DISABLE",
            vexp.CreateAccessPolicy,
            True,
            False,
        ),
        (
            'CREATE ACCESS POLICY ON "db"."sales"."order table" FOR COLUMN "select" '
            'COALESCE("select", 0) ENABLE',
            None,
            vexp.CreateAccessPolicy,
            False,
            True,
        ),
        (
            "ALTER ACCESS POLICY ON sales.orders FOR COLUMN amount amount * 2 GRANT TRUSTED ENABLE",
            None,
            vexp.AlterAccessPolicy,
            False,
            True,
        ),
        (
            "ALTER ACCESS POLICY ON sales.orders FOR ROWS WHERE active AND amount > 0 "
            "GRANT TRUSTED DISABLE",
            None,
            vexp.AlterAccessPolicy,
            True,
            False,
        ),
        (
            "ALTER ACCESS POLICY ON orders FOR ROWS GRANT TRUSTED ENABLE",
            None,
            vexp.AlterAccessPolicy,
            True,
            True,
        ),
        (
            "ALTER ACCESS POLICY ON orders FOR COLUMN amount COPY TO TABLE archive",
            None,
            vexp.AlterAccessPolicy,
            False,
            None,
        ),
        (
            "ALTER ACCESS POLICY ON sales.orders FOR ROWS COPY TO TABLE archive",
            None,
            vexp.AlterAccessPolicy,
            True,
            None,
        ),
        (
            "DROP ACCESS POLICY ON orders FOR COLUMN amount",
            None,
            vexp.DropAccessPolicy,
            False,
            None,
        ),
        (
            "DROP ACCESS POLICY ON orders FOR ROWS",
            None,
            vexp.DropAccessPolicy,
            True,
            None,
        ),
    ],
)
def test_access_policy_lifecycle_matrix(
    sql: str,
    expected: str | None,
    root_type: type[exp.Expr],
    rows: bool,
    enabled: bool | None,
) -> None:
    expression = assert_roundtrip(sql, expected or sql)

    assert isinstance(expression, root_type)
    assert expression.args["kind"] == "ACCESS POLICY"
    target = expression.args["this"]
    assert isinstance(target, vexp.AccessPolicyTarget)
    assert target.args["rows"] is rows
    assert expression.args.get("enabled") is enabled
    assert exp.Expression.load(expression.dump()) == expression
    assert expression.copy() == expression


def test_access_policy_tree_metadata_and_traversal() -> None:
    expression = assert_roundtrip(
        "CREATE ACCESS POLICY ON sales.orders FOR COLUMN amount "
        "CASE WHEN active THEN amount + tax ELSE 0 END GRANT TRUSTED ENABLE"
    )
    target = expression.args["this"]
    policy = expression.args["expression"]

    assert isinstance(target, vexp.AccessPolicyTarget)
    assert target.parent is expression
    assert target.arg_key == "this"
    assert policy.parent is expression
    assert policy.arg_key == "expression"
    assert {column.name for column in policy.find_all(exp.Column)} == {"active", "amount", "tax"}
    assert [table.name for table in expression.find_all(exp.Table)] == ["orders"]

    transformed = expression.transform(
        lambda node: (
            exp.column("surcharge") if isinstance(node, exp.Column) and node.name == "tax" else node
        )
    )
    assert "amount + surcharge" in transformed.sql(dialect="vertica")


def test_access_policy_optimizer_and_type_traversal() -> None:
    expression = parse_one(
        "CREATE ACCESS POLICY ON sales.orders FOR ROWS WHERE active AND amount > 0 ENABLE",
        read="vertica",
    )
    schema = {"sales": {"orders": {"active": "BOOLEAN", "amount": "INT"}}}

    annotated = annotate_types(expression.copy(), dialect="vertica", schema=schema)
    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)

    assert isinstance(annotated, vexp.CreateAccessPolicy)
    assert isinstance(annotated.args["expression"].type, exp.DataType)
    assert isinstance(optimized, vexp.CreateAccessPolicy)
    assert isinstance(
        parse_one(optimized.sql(dialect="vertica"), read="vertica"), vexp.CreateAccessPolicy
    )


def test_access_policy_comments_and_statement_boundaries() -> None:
    statements = parse(
        "/* before */ CREATE ACCESS POLICY ON t FOR ROWS WHERE active ENABLE; "
        "ALTER ACCESS POLICY ON t FOR ROWS COPY TO TABLE u; "
        "DROP ACCESS POLICY ON t FOR ROWS; SELECT 1",
        read="vertica",
    )

    assert [type(statement) for statement in statements] == [
        vexp.CreateAccessPolicy,
        vexp.AlterAccessPolicy,
        vexp.DropAccessPolicy,
        exp.Select,
    ]
    assert statements[0].comments == [" before "]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE ACCESS POLICY t FOR ROWS WHERE active ENABLE",
        "CREATE ACCESS ON t FOR ROWS WHERE active ENABLE",
        "CREATE ACCESS POLICY ON t ROWS WHERE active ENABLE",
        "CREATE ACCESS POLICY ON t FOR ROWS active ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN c ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN c value",
        "CREATE ACCESS POLICY ON t FOR COLUMN c value GRANT ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN c value GRANT TRUSTED",
        "CREATE ACCESS POLICY ON t FOR COLUMN c value ENABLE GRANT TRUSTED",
        "CREATE ACCESS POLICY ON t FOR COLUMN c value + GRANT TRUSTED ENABLE",
        "CREATE OR REPLACE ACCESS POLICY ON t FOR COLUMN c value ENABLE",
        "CREATE ACCESS POLICY IF NOT EXISTS ON t FOR COLUMN c value ENABLE",
        "CREATE ACCESS POLICY ON db.s.extra.t FOR COLUMN c value ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN s.c value ENABLE",
        "ALTER ACCESS POLICY ON t FOR ROWS ENABLE",
        "ALTER ACCESS POLICY ON t FOR COLUMN c value ENABLE",
        "ALTER ACCESS POLICY ON t FOR ROWS WHERE active ENABLE",
        "ALTER ACCESS POLICY ON t FOR ROWS GRANT TRUSTED",
        "ALTER ACCESS POLICY ON t FOR ROWS GRANT TRUSTED ENABLE DISABLE",
        "ALTER ACCESS POLICY ON t FOR ROWS COPY TABLE u",
        "ALTER ACCESS POLICY ON t FOR ROWS COPY TO TABLE s.u",
        "ALTER ACCESS POLICY ON t FOR ROWS COPY TO TABLE u GRANT TRUSTED ENABLE",
        "ALTER ACCESS POLICY ON t FOR ROWS WHERE active COPY TO TABLE u",
        "DROP ACCESS POLICY t FOR ROWS",
        "DROP ACCESS POLICY ON s.t FOR ROWS",
        "DROP ACCESS POLICY ON t FOR COLUMN",
        "DROP ACCESS POLICY ON t FOR ROWS CASCADE",
        "DROP ACCESS POLICY IF EXISTS ON t FOR ROWS",
        "DROP IF EXISTS ACCESS POLICY ON t FOR ROWS",
        'CREATE "ACCESS" POLICY ON t FOR ROWS WHERE active ENABLE',
        'ALTER ACCESS "POLICY" ON t FOR ROWS GRANT TRUSTED ENABLE',
        "CREATE ACCESS POLІCY ON t FOR ROWS WHERE active ENABLE",  # noqa: RUF001
        "CREATE ACCESS POLICY ON t FOR ROWS WHERE EXISTS (SELECT 1) ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN c SUM(c) ENABLE",
        "CREATE ACCESS POLICY ON t FOR COLUMN c ROW_NUMBER() OVER () ENABLE",
    ],
)
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_invalid_access_policy_source_fails_atomically(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


def test_access_policy_neighboring_dispatch_is_unchanged() -> None:
    statements = (
        "CREATE TABLE access (policy INT)",
        "ALTER TABLE access ADD COLUMN policy INT",
        "DROP TABLE access",
        "SELECT access, policy FROM permissions",
    )

    for sql in statements:
        expression = parse_one(sql, read="vertica")
        assert not isinstance(
            expression,
            (vexp.CreateAccessPolicy, vexp.AlterAccessPolicy, vexp.DropAccessPolicy),
        )


def test_access_policy_identifier_boundaries() -> None:
    boundary = "é" * 64
    sql = f'CREATE ACCESS POLICY ON "{boundary}" FOR COLUMN "{boundary}" value ENABLE'
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression, vexp.CreateAccessPolicy)

    with pytest.raises(ParseError):
        parse_one(
            f'CREATE ACCESS POLICY ON "{boundary}x" FOR ROWS WHERE active ENABLE',
            read="vertica",
        )
    with pytest.raises(ParseError):
        parse_one(
            f'CREATE ACCESS POLICY ON t FOR COLUMN "{boundary}x" value ENABLE',
            read="vertica",
        )


def test_access_policy_programmatic_ast_validation() -> None:
    row_target = vexp.AccessPolicyTarget(this=exp.to_table("t"), rows=True)
    column_target = vexp.AccessPolicyTarget(
        this=exp.to_table("t"), column=exp.to_identifier("c"), rows=False
    )
    valid_policy = exp.column("active")
    invalid_utf8_table = exp.to_table("t")
    invalid_utf8_table.this.set("this", "\ud800")
    falsey_extra_table = exp.to_table("t")
    falsey_extra_table.set("alias", False)
    malformed = (
        vexp.AccessPolicyTarget(this=exp.to_table("t"), rows=False),
        vexp.AccessPolicyTarget(this=exp.to_table("t"), column=exp.to_identifier("c"), rows=True),
        vexp.AccessPolicyTarget(this=exp.to_table("t"), rows="yes"),
        vexp.AccessPolicyTarget(this=exp.to_table("db.s.extra.t"), rows=True),
        vexp.AccessPolicyTarget(this=falsey_extra_table, rows=True),
        vexp.AccessPolicyTarget(this=invalid_utf8_table, rows=True),
        vexp.CreateAccessPolicy(
            this=row_target.copy(),
            expression=valid_policy.copy(),
            kind="TABLE",
            grant_trusted=False,
            enabled=True,
        ),
        vexp.CreateAccessPolicy(
            this=row_target.copy(), kind="ACCESS POLICY", grant_trusted=False, enabled=True
        ),
        vexp.CreateAccessPolicy(
            this=row_target.copy(),
            expression=exp.select("x"),
            kind="ACCESS POLICY",
            grant_trusted=False,
            enabled=True,
        ),
        vexp.CreateAccessPolicy(
            this=column_target.copy(),
            expression=exp.Sum(this=exp.column("c")),
            kind="ACCESS POLICY",
            grant_trusted=False,
            enabled=True,
        ),
        vexp.CreateAccessPolicy(
            this=column_target.copy(),
            expression=exp.Add(this=exp.column("c")),
            kind="ACCESS POLICY",
            grant_trusted=False,
            enabled=True,
        ),
        vexp.CreateAccessPolicy(
            this=column_target.copy(),
            expression=valid_policy.copy(),
            kind="ACCESS POLICY",
            grant_trusted="yes",
            enabled=True,
        ),
        vexp.CreateAccessPolicy(
            this=column_target.copy(),
            expression=valid_policy.copy(),
            kind="ACCESS POLICY",
            grant_trusted=False,
            enabled="yes",
        ),
        vexp.CreateAccessPolicy(
            this=column_target.copy(),
            expression=valid_policy.copy(),
            kind="ACCESS POLICY",
            grant_trusted=False,
            enabled=True,
            replace=False,
        ),
        vexp.AlterAccessPolicy(
            this=row_target.copy(),
            kind="ACCESS POLICY",
            grant_trusted=True,
            enabled=True,
            actions=[],
        ),
        vexp.AlterAccessPolicy(
            this=row_target.copy(), kind="ACCESS POLICY", grant_trusted=False, enabled=True
        ),
        vexp.AlterAccessPolicy(
            this=row_target.copy(),
            expression=valid_policy.copy(),
            kind="ACCESS POLICY",
            copy_to=exp.to_table("u"),
        ),
        vexp.AlterAccessPolicy(
            this=row_target.copy(), kind="ACCESS POLICY", copy_to=exp.to_table("s.u")
        ),
        vexp.DropAccessPolicy(this=row_target.copy(), kind="ACCESS POLICY", exists=False),
        vexp.DropAccessPolicy(this=exp.to_table("t"), kind="ACCESS POLICY"),
    )

    for expression in malformed:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE ACCESS POLICY ON t FOR ROWS WHERE active ENABLE",
        "ALTER ACCESS POLICY ON t FOR COLUMN c COPY TO TABLE u",
        "DROP ACCESS POLICY ON t FOR ROWS",
    ],
)
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_access_policy_foreign_generation_is_atomic(sql: str, dialect: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
    nested = exp.Tuple(expressions=[expression.copy()])
    with pytest.raises((UnsupportedError, ValueError)):
        nested.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_detached_access_policy_target_fails_in_foreign_dialects() -> None:
    target = vexp.AccessPolicyTarget(this=exp.to_table("t"), rows=True)

    for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
        with pytest.raises((UnsupportedError, ValueError)):
            target.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
