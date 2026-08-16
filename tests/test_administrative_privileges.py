"""Exact Vertica administrative GRANT and REVOKE contracts."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT ALTER, DROP, EXECUTE ON DATA LOADER ingest TO loader WITH GRANT OPTION",
        "GRANT ALL PRIVILEGES ON DATA LOADER staging.ingest TO loader, PUBLIC",
        "REVOKE GRANT OPTION FOR EXECUTE ON DATA LOADER staging.ingest FROM loader CASCADE",
        "GRANT USAGE, ALTER, DROP ON KEY key_a, key_b TO security_admin",
        "GRANT ALL PRIVILEGES EXTEND ON KEY key_a TO security_admin WITH GRANT OPTION",
        "REVOKE ALL PRIVILEGES ON KEY key_a, key_b FROM security_admin",
        "GRANT USAGE, DROP ON LIBRARY db.extensions.parsers, public.transforms TO developer",
        "GRANT ALL EXTEND ON LIBRARY extensions.parsers TO developer WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR USAGE ON LIBRARY extensions.parsers FROM developer CASCADE",
        "REVOKE ALL PRIVILEGES ON LIBRARY lib_a, db.public.lib_b FROM developer",
        "GRANT USAGE, ALTER, DROP ON TLS CONFIGURATION server, data_channel TO tls_admin",
        "REVOKE GRANT OPTION FOR ALL ON TLS CONFIGURATION server FROM tls_admin",
    ],
)
def test_administrative_privilege_matrix(sql: str) -> None:
    expression = assert_roundtrip(sql, sql)
    target = expression.args["securable"]

    assert type(expression) in {exp.Grant, exp.Revoke}
    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert target.args["kind"] in {"DATA LOADER", "KEY", "LIBRARY", "TLS CONFIGURATION"}
    assert all(isinstance(value, exp.Table) for value in target.expressions)
    assert expression.copy() == expression
    assert exp.Expression.load(expression.dump()) == expression


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT EXECUTE ON FUNCTION f() TO analyst",
        "GRANT EXECUTE ON AGGREGATE FUNCTION f(x INT) TO analyst",
        "GRANT EXECUTE ON ANALYTIC FUNCTION f(INT) TO analyst",
        "GRANT EXECUTE ON TRANSFORM FUNCTION f() TO analyst",
        "GRANT EXECUTE ON FILTER f() TO analyst",
        "GRANT EXECUTE ON PARSER f() TO analyst",
        "GRANT EXECUTE ON SOURCE f() TO analyst",
    ],
)
def test_factory_udx_privilege_signatures_remain_typed(sql: str) -> None:
    expected = sql.replace("x INT", "x BIGINT").replace("f(INT)", "f(BIGINT)")
    expression = assert_roundtrip(sql, expected)
    target = expression.args["securable"]

    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert all(isinstance(value, vexp.RoutineSignature) for value in target.expressions)


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT USAGE ON DATA LOADER a, b TO loader",
        "GRANT USAGE ON DATA LOADER db.schema.loader TO loader",
        "GRANT USAGE ON KEY schema.key_a TO security_admin",
        "GRANT USAGE ON TLS CONFIGURATION schema.server TO tls_admin",
        "GRANT USAGE ON LIBRARY catalog.db.schema.library TO developer",
        "GRANT SELECT ON DATA LOADER ingest TO loader",
        "GRANT EXECUTE ON KEY key_a TO security_admin",
        "GRANT ALTER ON LIBRARY library_a TO developer",
        "REVOKE DROP ON LIBRARY library_a FROM developer",
        "GRANT EXECUTE ON TLS CONFIGURATION server TO tls_admin",
        "GRANT ALL ON TLS CONFIGURATION server TO tls_admin",
        "GRANT ALL EXTEND ON DATA LOADER ingest TO loader",
        "GRANT ALL EXTEND ON TLS CONFIGURATION server TO tls_admin",
        "REVOKE USAGE ON KEY key_a FROM security_admin CASCADE",
        "REVOKE USAGE ON TLS CONFIGURATION server FROM tls_admin CASCADE",
    ],
)
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_invalid_administrative_privileges_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT USAGE ON KEY key_a TO security_admin",
        "REVOKE EXECUTE ON DATA LOADER ingest FROM loader CASCADE",
        "GRANT USAGE ON LIBRARY extensions.parsers TO developer",
        "REVOKE ALL ON TLS CONFIGURATION server FROM tls_admin",
    ],
)
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_administrative_privileges_fail_atomically_in_foreign_dialects(
    sql: str, dialect: str
) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_programmatic_administrative_privilege_validation() -> None:
    principal = exp.GrantPrincipal(this=exp.to_identifier("admin"))
    privilege = exp.GrantPrivilege(this=exp.var("USAGE"))

    invalid_expressions = [
        exp.Grant(
            privileges=[privilege.copy()],
            securable=vexp.VerticaPrivilegeTarget(
                kind="DATA LOADER", expressions=[exp.to_table("a"), exp.to_table("b")]
            ),
            principals=[principal.copy()],
        ),
        exp.Grant(
            privileges=[privilege.copy()],
            securable=vexp.VerticaPrivilegeTarget(
                kind="KEY", expressions=[exp.to_table("schema.key_a")]
            ),
            principals=[principal.copy()],
        ),
        exp.Revoke(
            privileges=[exp.GrantPrivilege(this=exp.var("DROP"))],
            securable=vexp.VerticaPrivilegeTarget(
                kind="LIBRARY", expressions=[exp.to_table("library_a")]
            ),
            principals=[principal.copy()],
        ),
        exp.Revoke(
            privileges=[privilege.copy()],
            securable=vexp.VerticaPrivilegeTarget(
                kind="TLS CONFIGURATION", expressions=[exp.to_table("server")]
            ),
            principals=[principal.copy()],
            cascade="CASCADE",
        ),
        exp.Grant(
            privileges=[privilege.copy()],
            securable=vexp.VerticaPrivilegeTarget(kind="KEY", expressions=[exp.to_table("key_a")]),
            principals=[exp.GrantPrincipal(this=exp.Column(this="admin", table="role"))],
        ),
        exp.Grant(
            privileges=[privilege.copy()],
            securable=vexp.VerticaPrivilegeTarget(
                kind=exp.var("KEY"), expressions=[exp.to_table("key_a")]
            ),
            principals=[principal.copy()],
        ),
        exp.Grant(
            privileges=[
                vexp.ExtendedGrantPrivilege(
                    this=exp.var("ALL"), privileges=[exp.var("bad")], extend=True
                )
            ],
            securable=vexp.VerticaPrivilegeTarget(kind="KEY", expressions=[exp.to_table("key_a")]),
            principals=[principal.copy()],
        ),
    ]

    for expression in invalid_expressions:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_administrative_identifier_boundaries_and_comments() -> None:
    boundary = "é" * 64
    expression = assert_roundtrip(
        f'GRANT USAGE ON KEY "{boundary}" TO "security role"',
        f'GRANT USAGE ON KEY "{boundary}" TO "security role"',
    )
    assert expression.args["securable"].expressions[0].name == boundary

    with pytest.raises(ParseError):
        parse_one(f'GRANT USAGE ON KEY "{boundary}x" TO admin', read="vertica")

    statements = parse_one(
        "GRANT /* target */ USAGE ON KEY key_a TO admin",
        read="vertica",
    )
    assert isinstance(statements, exp.Grant)
