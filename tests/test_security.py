"""Vertica GRANT and REVOKE semantic regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_ordinary_object_privileges_remain_canonical() -> None:
    grant_sql = "GRANT SELECT, UPDATE ON TABLE analytics.events TO alice, analyst"
    revoke_sql = (
        "REVOKE GRANT OPTION FOR SELECT ON TABLE analytics.events FROM alice, analyst CASCADE"
    )

    grant = assert_roundtrip(grant_sql, grant_sql)
    revoke = assert_roundtrip(revoke_sql, revoke_sql)

    assert type(grant) is exp.Grant
    assert type(revoke) is exp.Revoke
    assert isinstance(grant.args["securable"], exp.Table)
    assert isinstance(revoke.args["securable"], exp.Table)
    assert all(type(privilege) is exp.GrantPrivilege for privilege in grant.args["privileges"])
    assert all(type(principal) is exp.GrantPrincipal for principal in grant.args["principals"])

    assert grant.sql(dialect="postgres") == grant_sql
    assert revoke.sql(dialect="postgres") == revoke_sql


def test_multi_target_grant_uses_structured_securable() -> None:
    sql = (
        "GRANT SELECT, UPDATE ON TABLE events, analytics.events_archive "
        "TO alice, analyst WITH GRANT OPTION"
    )
    expression = assert_roundtrip(sql, sql)

    assert type(expression) is exp.Grant
    target = expression.args["securable"]
    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert target.args["kind"] == "TABLE"
    assert [table.name for table in target.expressions] == ["events", "events_archive"]
    assert expression.args["grant_option"] is True
    assert [principal.name for principal in expression.args["principals"]] == [
        "alice",
        "analyst",
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT SELECT ON events, events_archive TO alice",
        "GRANT ALTER ON TLS CONFIGURATION server_tls TO security_admin",
        "GRANT EXECUTE ON DATA LOADER analytics.ingest TO loader",
    ],
)
def test_other_named_object_targets(sql: str) -> None:
    assert_roundtrip(sql, sql)


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT SELECT ON ALL TABLES IN SCHEMA public, analytics TO reader",
        "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public, analytics TO reader",
        "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public, analytics TO reader",
        (
            "REVOKE GRANT OPTION FOR SELECT ON ALL TABLES IN SCHEMA public, analytics "
            "FROM reader CASCADE"
        ),
    ],
)
def test_all_in_schema_targets_are_structured(sql: str) -> None:
    expression = assert_roundtrip(sql, sql)
    target = expression.args["securable"]

    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert target.args["all_in_schema"] is True
    assert [schema.name for schema in target.expressions] == ["public", "analytics"]


def test_all_privileges_extend_is_explicit() -> None:
    sql = "GRANT ALL PRIVILEGES EXTEND ON ALL TABLES IN SCHEMA analytics TO maintainer"
    expression = assert_roundtrip(sql, sql)
    privilege = expression.args["privileges"][0]

    assert isinstance(privilege, vexp.ExtendedGrantPrivilege)
    assert privilege.name == "ALL"
    assert privilege.args["privileges"] is True
    assert privilege.args["extend"] is True


def test_role_grant_and_revoke_semantics() -> None:
    grant_sql = "GRANT analyst, reader TO alice, bob WITH ADMIN OPTION"
    revoke_sql = "REVOKE ADMIN OPTION FOR analyst, reader FROM alice, bob CASCADE"

    grant = assert_roundtrip(grant_sql, grant_sql)
    revoke = assert_roundtrip(revoke_sql, revoke_sql)

    assert isinstance(grant, vexp.RoleGrant)
    assert isinstance(revoke, vexp.RoleRevoke)
    assert [role.name for role in grant.args["roles"]] == ["analyst", "reader"]
    assert grant.args["admin_option"] is True
    assert revoke.args["admin_option"] is True
    assert revoke.args["cascade"] == "CASCADE"


def test_authentication_grant_and_revoke_semantics() -> None:
    grant_sql = 'GRANT AUTHENTICATION "ldap method" TO alice, analyst, PUBLIC'
    revoke_sql = 'REVOKE AUTHENTICATION "ldap method" FROM alice, analyst, PUBLIC'

    grant = assert_roundtrip(grant_sql, grant_sql)
    revoke = assert_roundtrip(revoke_sql, revoke_sql)

    assert isinstance(grant, vexp.AuthenticationGrant)
    assert isinstance(revoke, vexp.AuthenticationRevoke)
    assert grant.this.name == "ldap method"
    assert [principal.name for principal in grant.args["principals"]] == [
        "alice",
        "analyst",
        "PUBLIC",
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT USAGE ON RESOURCE POOL general TO alice WITH GRANT OPTION",
        "GRANT USAGE ON RESOURCE POOL general, batch FOR SUBCLUSTER sc1 TO alice",
        "GRANT USAGE ON RESOURCE POOL general FOR CURRENT SUBCLUSTER TO alice",
        (
            "REVOKE GRANT OPTION FOR USAGE ON RESOURCE POOL general FOR SUBCLUSTER sc1 "
            "FROM alice CASCADE"
        ),
        "REVOKE ALL PRIVILEGES ON RESOURCE POOL general FROM alice CASCADE",
    ],
)
def test_resource_pool_privileges(sql: str) -> None:
    assert_roundtrip(sql, sql)


def test_resource_pool_qualifiers_are_structured() -> None:
    named = assert_roundtrip(
        "GRANT USAGE ON RESOURCE POOL general, batch FOR SUBCLUSTER sc1 TO alice"
    )
    current = assert_roundtrip(
        "GRANT USAGE ON RESOURCE POOL general FOR CURRENT SUBCLUSTER TO alice"
    )

    named_target = named.args["securable"]
    current_target = current.args["securable"]
    assert isinstance(named_target, vexp.VerticaPrivilegeTarget)
    assert isinstance(current_target, vexp.VerticaPrivilegeTarget)
    assert named_target.args["subcluster"].name == "sc1"
    assert named_target.args["current_subcluster"] is False
    assert current_target.args["current_subcluster"] is True


def test_location_and_workload_targets() -> None:
    location_sql = (
        "GRANT READ, WRITE ON LOCATION '/warehouse/data' ON node01 TO loader WITH GRANT OPTION"
    )
    workload_sql = "REVOKE USAGE ON WORKLOAD analytics FROM analyst"

    location = assert_roundtrip(location_sql, location_sql)
    workload = assert_roundtrip(workload_sql, workload_sql)
    location_target = location.args["securable"]
    workload_target = workload.args["securable"]

    assert isinstance(location_target, vexp.VerticaPrivilegeTarget)
    assert location_target.expressions[0].to_py() == "/warehouse/data"
    assert location_target.args["node"].name == "node01"
    assert isinstance(workload_target, vexp.VerticaPrivilegeTarget)
    assert workload_target.args["kind"] == "WORKLOAD"


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "GRANT EXECUTE ON FUNCTION analytics.f(x INT, VARCHAR), analytics.empty() "
            "TO alice, operator",
            "GRANT EXECUTE ON FUNCTION analytics.f(x BIGINT, VARCHAR), analytics.empty() "
            "TO alice, operator",
        ),
        (
            "GRANT ALL PRIVILEGES EXTEND ON AGGREGATE FUNCTION agg(NUMERIC(10, 2)) TO operator",
            "GRANT ALL PRIVILEGES EXTEND ON AGGREGATE FUNCTION agg(DECIMAL(10, 2)) TO operator",
        ),
        ("GRANT EXECUTE ON ANALYTIC FUNCTION ranker() TO operator", None),
        ("GRANT EXECUTE ON TRANSFORM FUNCTION tokenize(VARCHAR) TO operator", None),
        ("GRANT EXECUTE ON FILTER keep_rows(BOOLEAN) TO operator", None),
        ("GRANT EXECUTE ON PARSER csv_parser() TO operator", None),
        ("GRANT EXECUTE ON SOURCE file_source() TO operator", None),
        (
            "REVOKE GRANT OPTION FOR EXECUTE ON PROCEDURE analytics.refresh(x INT) "
            "FROM operator CASCADE",
            "REVOKE GRANT OPTION FOR EXECUTE ON PROCEDURE analytics.refresh(x BIGINT) "
            "FROM operator CASCADE",
        ),
    ],
)
def test_routine_and_udx_signatures(sql: str, expected: str | None) -> None:
    expression = assert_roundtrip(sql, expected or sql)
    target = expression.args["securable"]

    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert all(isinstance(signature, vexp.RoutineSignature) for signature in target.expressions)


def test_named_and_anonymous_routine_arguments_are_distinct() -> None:
    expression = assert_roundtrip(
        "GRANT EXECUTE ON FUNCTION f(value INT, VARCHAR, custom_type) TO alice",
        "GRANT EXECUTE ON FUNCTION f(value BIGINT, VARCHAR, custom_type) TO alice",
    )
    signature = expression.find(vexp.RoutineSignature)

    assert isinstance(signature, vexp.RoutineSignature)
    assert isinstance(signature.expressions[0], exp.ColumnDef)
    assert isinstance(signature.expressions[1], exp.DataType)
    assert isinstance(signature.expressions[2], exp.DataType)


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT analyst TO alice",
        "REVOKE analyst FROM alice CASCADE",
        "GRANT AUTHENTICATION ldap TO alice",
        "GRANT SELECT ON TABLE a, b TO alice",
        "GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO alice",
        "GRANT USAGE ON RESOURCE POOL p FOR SUBCLUSTER sc TO alice",
        "GRANT READ ON LOCATION '/data' ON node01 TO alice",
        "GRANT USAGE ON WORKLOAD analytics TO alice",
        "GRANT EXECUTE ON FUNCTION f(INT) TO alice",
    ],
)
def test_vertica_extended_security_fails_atomically_in_postgres(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises(ValueError, match="Unsupported expression type"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT",
        "GRANT analyst",
        "GRANT analyst TO",
        "GRANT analyst, TO alice",
        "GRANT analyst TO alice,",
        "GRANT analyst TO alice WITH GRANT OPTION",
        "GRANT analyst TO alice WITH ADMIN",
        "GRANT analyst TO alice WITH ADMIN OPTION CASCADE",
        "REVOKE",
        "REVOKE analyst",
        "REVOKE analyst FROM",
        "REVOKE analyst, FROM alice",
        "REVOKE analyst FROM alice,",
        "REVOKE ADMIN analyst FROM alice",
        "REVOKE ADMIN OPTION analyst FROM alice",
        "REVOKE analyst FROM alice RESTRICT",
        "REVOKE GRANT OPTION FOR analyst FROM alice",
        "REVOKE GRANT privilege ON TABLE t FROM alice",
    ],
)
def test_role_privilege_negatives(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT AUTHENTICATION TO alice",
        "GRANT AUTHENTICATION ldap alice",
        "GRANT AUTHENTICATION ldap TO",
        "GRANT AUTHENTICATION ldap, kerberos TO alice",
        "GRANT AUTHENTICATION ldap TO alice WITH GRANT OPTION",
        "GRANT AUTHENTICATION ldap TO alice WITH ADMIN OPTION",
        "REVOKE AUTHENTICATION FROM alice",
        "REVOKE AUTHENTICATION ldap alice",
        "REVOKE AUTHENTICATION ldap FROM",
        "REVOKE AUTHENTICATION ldap FROM alice CASCADE",
        "REVOKE AUTHENTICATION ldap FROM alice RESTRICT",
    ],
)
def test_authentication_privilege_negatives(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT ON TABLE t TO alice",
        "GRANT SELECT TABLE t TO alice",
        "GRANT SELECT ON TABLE TO alice",
        "GRANT SELECT ON TABLE t alice",
        "GRANT SELECT ON TABLE t TO",
        "GRANT SELECT, ON TABLE t TO alice",
        "GRANT SELECT ON TABLE t, TO alice",
        "GRANT SELECT ON TABLE t TO alice,",
        "GRANT ALL, SELECT ON TABLE t TO alice",
        "GRANT SELECT, ALL ON TABLE t TO alice",
        "GRANT SELECT EXTEND ON TABLE t TO alice",
        "GRANT ALL EXTEND PRIVILEGES ON TABLE t TO alice",
        "REVOKE ALL EXTEND ON TABLE t FROM alice",
        "REVOKE SELECT ON TABLE t FROM alice RESTRICT",
        "GRANT SELECT ON ALL VIEWS IN SCHEMA analytics TO alice",
        "GRANT SELECT ON ALL TABLES analytics TO alice",
        "GRANT SELECT ON ALL TABLES IN SCHEMA TO alice",
        "GRANT SELECT ON ALL TABLES IN SCHEMA analytics, TO alice",
        "GRANT SELECT ON TABLE t TO alice WITH ADMIN OPTION",
        "REVOKE SELECT ON TABLE t alice",
    ],
)
def test_object_privilege_negatives(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT ALL ON RESOURCE POOL p TO alice",
        "GRANT SELECT ON RESOURCE POOL p TO alice",
        "GRANT USAGE ON RESOURCE POOL p FOR TO alice",
        "GRANT USAGE ON RESOURCE POOL p FOR SUBCLUSTER TO alice",
        "GRANT USAGE ON RESOURCE POOL p FOR CURRENT TO alice",
        "GRANT USAGE ON RESOURCE POOL p FOR CURRENT SUBCLUSTER FOR SUBCLUSTER sc TO alice",
        "GRANT SELECT ON WORKLOAD analytics TO alice",
        "GRANT ALL ON WORKLOAD analytics TO alice",
        "GRANT USAGE ON WORKLOAD analytics, batch TO alice",
        "GRANT USAGE ON WORKLOAD analytics TO alice, bob",
        "GRANT USAGE ON WORKLOAD analytics TO alice WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR USAGE ON WORKLOAD analytics FROM alice",
        "REVOKE USAGE ON WORKLOAD analytics FROM alice CASCADE",
        "REVOKE USAGE ON WORKLOAD analytics FROM alice, bob",
        "GRANT USAGE ON LOCATION '/data' TO alice",
        "GRANT READ ON LOCATION data TO alice",
        "GRANT READ ON LOCATION '/data' ON TO alice",
        "GRANT ALL EXTEND ON LOCATION '/data' TO alice",
    ],
)
def test_special_target_negatives(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT EXECUTE ON FUNCTION f TO alice",
        "GRANT EXECUTE ON FUNCTION (INT) TO alice",
        "GRANT EXECUTE ON FUNCTION f(INT,) TO alice",
        "GRANT EXECUTE ON FUNCTION f(INT), TO alice",
        "GRANT EXECUTE ON FUNCTION f(INT), FUNCTION g(INT) TO alice",
        "GRANT USAGE ON FUNCTION f() TO alice",
        "GRANT ALTER ON PROCEDURE p() TO alice",
        "GRANT ALL PRIVILEGES EXTEND ON PROCEDURE p() TO alice",
        "REVOKE EXECUTE ON PROCEDURE p FROM alice",
        "GRANT EXECUTE ON FUNCTION f(x +) TO alice",
        "GRANT EXECUTE ON FUNCTION f(x INT trailing) TO alice",
    ],
)
def test_routine_privilege_negatives(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_programmatic_security_ast_restrictions() -> None:
    principal = exp.GrantPrincipal(this=exp.to_identifier("alice"))
    workload = vexp.VerticaPrivilegeTarget(
        kind="WORKLOAD",
        expressions=[exp.to_table("analytics")],
    )
    invalid_workload = exp.Grant(
        privileges=[exp.GrantPrivilege(this=exp.var("USAGE"))],
        securable=workload,
        principals=[principal],
        grant_option=True,
    )

    with pytest.raises(UnsupportedError, match="WORKLOAD"):
        invalid_workload.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    resource_pool = vexp.VerticaPrivilegeTarget(
        kind="RESOURCE POOL",
        expressions=[exp.to_table("general")],
    )
    invalid_pool = exp.Grant(
        privileges=[exp.GrantPrivilege(this=exp.var("ALL"))],
        securable=resource_pool,
        principals=[principal.copy()],
    )
    with pytest.raises(UnsupportedError, match="RESOURCE POOL"):
        invalid_pool.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_custom_security_node_conflicts() -> None:
    conflicting_pool = vexp.VerticaPrivilegeTarget(
        kind="RESOURCE POOL",
        expressions=[exp.to_table("general")],
        subcluster=exp.to_identifier("sc1"),
        current_subcluster=True,
    )
    with pytest.raises(UnsupportedError, match="two subcluster"):
        conflicting_pool.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    malformed_routine = vexp.VerticaPrivilegeTarget(
        kind="FUNCTION",
        expressions=[exp.to_table("f")],
    )
    with pytest.raises(UnsupportedError, match="typed signatures"):
        malformed_routine.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    role = vexp.RoleGrant(
        roles=[exp.to_identifier("analyst")],
        principals=[exp.GrantPrincipal(this=exp.to_identifier("alice"))],
        grant_option=True,
    )
    with pytest.raises(UnsupportedError, match="ADMIN OPTION"):
        role.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_privilege_target_shape_restrictions() -> None:
    invalid_targets = [
        (
            vexp.VerticaPrivilegeTarget(kind="TABLE", expressions=[]),
            "at least one object",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="SCHEMA",
                expressions=[exp.to_table("analytics")],
                all_in_schema=True,
            ),
            "functions, sequences, or tables",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="TABLE",
                expressions=[exp.to_table("analytics")],
                all_in_schema=True,
                node=exp.to_identifier("node01"),
            ),
            "target qualifiers",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="LOCATION",
                expressions=[exp.Literal.string("/a"), exp.Literal.string("/b")],
            ),
            "exactly one path",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="TABLE",
                expressions=[exp.to_table("events")],
                node=exp.to_identifier("node01"),
            ),
            "Only LOCATION",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="WORKLOAD",
                expressions=[exp.to_table("a"), exp.to_table("b")],
            ),
            "exactly one workload",
        ),
        (
            vexp.VerticaPrivilegeTarget(
                kind="TABLE",
                expressions=[exp.to_table("events")],
                subcluster=exp.to_identifier("sc1"),
            ),
            "Only RESOURCE POOL",
        ),
    ]

    for target, message in invalid_targets:
        with pytest.raises(UnsupportedError, match=message):
            target.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_statement_and_extend_restrictions() -> None:
    principal = exp.GrantPrincipal(this=exp.to_identifier("alice"))
    extended = vexp.ExtendedGrantPrivilege(
        this=exp.var("ALL"),
        extend=True,
    )
    location = vexp.VerticaPrivilegeTarget(
        kind="LOCATION",
        expressions=[exp.Literal.string("/data")],
    )
    grant = exp.Grant(
        privileges=[extended],
        securable=location,
        principals=[principal],
    )
    with pytest.raises(UnsupportedError, match="LOCATION"):
        grant.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    malformed_extend = vexp.ExtendedGrantPrivilege(this=exp.var("ALL"), extend=False)
    with pytest.raises(UnsupportedError, match="requires ALL"):
        malformed_extend.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    role_revoke = vexp.RoleRevoke(
        roles=[exp.to_identifier("analyst")],
        principals=[principal.copy()],
        grant_option=True,
    )
    with pytest.raises(UnsupportedError, match="ADMIN OPTION"):
        role_revoke.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    empty_role = vexp.RoleGrant(roles=[], principals=[])
    with pytest.raises(UnsupportedError, match="roles and grantees"):
        empty_role.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    empty_role_revoke = vexp.RoleRevoke(roles=[], principals=[])
    with pytest.raises(UnsupportedError, match="roles and grantees"):
        empty_role_revoke.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    empty_auth_grant = vexp.AuthenticationGrant(principals=[])
    with pytest.raises(UnsupportedError, match="method and grantees"):
        empty_auth_grant.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    empty_auth_revoke = vexp.AuthenticationRevoke(principals=[])
    with pytest.raises(UnsupportedError, match="method and grantees"):
        empty_auth_revoke.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    auth_grant = vexp.AuthenticationGrant(
        this=exp.to_identifier("ldap"),
        principals=[principal.copy()],
        grant_option=True,
    )
    with pytest.raises(UnsupportedError, match="does not support options"):
        auth_grant.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    auth_revoke = vexp.AuthenticationRevoke(
        this=exp.to_identifier("ldap"),
        principals=[principal.copy()],
        cascade="CASCADE",
    )
    with pytest.raises(UnsupportedError, match="does not support options"):
        auth_revoke.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
