"""Vertica CREATE SCHEMA and CREATE VIEW option regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

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
