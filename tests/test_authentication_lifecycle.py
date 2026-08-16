"""Semantic non-secret Vertica AUTHENTICATION lifecycle regressions."""

from __future__ import annotations

import logging

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

METHODS = ("trust", "reject", "hash", "gss", "ident", "ldap", "tls", "oauth")


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str, quoted: bool = False) -> exp.Identifier:
    return exp.to_identifier(name, quoted=quoted)


def _access(kind: str, address: str | None = None, tls: bool | None = None) -> exp.Expr:
    return vexp.AuthenticationAccess(
        this=exp.var(kind),
        expression=exp.Literal.string(address) if address is not None else None,
        tls=tls,
    )


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


@pytest.mark.parametrize("method", METHODS)
def test_all_create_authentication_methods_are_typed(method: str) -> None:
    expression = assert_roundtrip(f"CREATE AUTHENTICATION auth_{method} METHOD '{method}' LOCAL")
    assert isinstance(expression, vexp.CreateAuthentication)
    assert expression.kind == "AUTHENTICATION"
    assert expression.args["method"] == exp.Literal.string(method)
    assert isinstance(expression.args["access"], vexp.AuthenticationAccess)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION local_hash METHOD 'hash' LOCAL",
        "CREATE AUTHENTICATION remote_hash METHOD 'hash' HOST '0.0.0.0/0'",
        "CREATE AUTHENTICATION tls_hash METHOD 'hash' HOST TLS '::/0'",
        "CREATE AUTHENTICATION plain_reject METHOD 'reject' HOST NO TLS 'host.example'",
        "CREATE AUTHENTICATION ldap_mfa METHOD 'ldap' HOST '10.0.0.0/8' ENFORCEMFA",
        "CREATE AUTHENTICATION ldap_fallback METHOD 'ldap' LOCAL FALLTHROUGH",
        (
            "CREATE AUTHENTICATION ldap_both METHOD 'ldap' HOST TLS '10.0.0.0/8' "
            "ENFORCEMFA FALLTHROUGH"
        ),
        "DROP AUTHENTICATION auth_hash",
        "DROP AUTHENTICATION IF EXISTS auth_hash CASCADE",
    ],
)
def test_authentication_forms_roundtrip(sql: str) -> None:
    expression = assert_roundtrip(sql)
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


def test_programmatic_authentication_generation() -> None:
    create = vexp.CreateAuthentication(
        this=_identifier("ldap_auth"),
        kind="AUTHENTICATION",
        method=exp.Literal.string("ldap"),
        access=_access("HOST", "10.0.0.0/8", tls=False),
        enforce_mfa=True,
        fallthrough=True,
    )
    drop = vexp.DropAuthentication(
        this=_identifier("ldap_auth"), kind="AUTHENTICATION", exists=True, cascade=True
    )
    assert _strict(create) == (
        "CREATE AUTHENTICATION ldap_auth METHOD 'ldap' HOST NO TLS '10.0.0.0/8' "
        "ENFORCEMFA FALLTHROUGH"
    )
    assert _strict(drop) == "DROP AUTHENTICATION IF EXISTS ldap_auth CASCADE"


@pytest.mark.parametrize(
    ("sql", "action_type"),
    [
        ("ALTER AUTHENTICATION a ENABLE", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a DISABLE", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a LOCAL", vexp.AuthenticationAccess),
        ("ALTER AUTHENTICATION a HOST '0.0.0.0/0'", vexp.AuthenticationAccess),
        ("ALTER AUTHENTICATION a HOST TLS '::/0'", vexp.AuthenticationAccess),
        ("ALTER AUTHENTICATION a HOST NO TLS 'host.example'", vexp.AuthenticationAccess),
        ("ALTER AUTHENTICATION a RENAME TO renamed", exp.AlterRename),
        ("ALTER AUTHENTICATION a METHOD 'ldap'", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a PRIORITY 0", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a PRIORITY 123", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a ENFORCEMFA TRUE", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a ENFORCEMFA FALSE", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a FALLTHROUGH", vexp.AuthenticationAction),
        ("ALTER AUTHENTICATION a NO FALLTHROUGH", vexp.AuthenticationAction),
    ],
)
def test_alter_authentication_actions_are_typed(sql: str, action_type: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterAuthentication)
    assert expression.kind == "AUTHENTICATION"
    assert len(expression.actions) == 1
    assert isinstance(expression.actions[0], action_type)
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize("method", METHODS)
def test_all_alter_authentication_methods_are_finite(method: str) -> None:
    expression = assert_roundtrip(f"ALTER AUTHENTICATION a METHOD '{method}'")
    action = expression.actions[0]
    assert isinstance(action, vexp.AuthenticationAction)
    assert action.args["expression"] == exp.Literal.string(method)


def test_alter_authentication_huge_priority_is_lexical() -> None:
    digits = "9" * 10_000
    expression = assert_roundtrip(f"ALTER AUTHENTICATION a PRIORITY {digits}")
    action = expression.actions[0]
    assert isinstance(action, vexp.AuthenticationAction)
    assert action.args["expression"].this == digits


def test_programmatic_alter_authentication_generation() -> None:
    alter = vexp.AlterAuthentication(
        this=_identifier("a"),
        kind="AUTHENTICATION",
        actions=[
            vexp.AuthenticationAction(
                this=exp.var("ENFORCEMFA"), expression=exp.Boolean(this=False)
            )
        ],
    )
    assert _strict(alter) == "ALTER AUTHENTICATION a ENFORCEMFA FALSE"
    alter.set("actions", [_access("HOST", "::/0", tls=True)])
    assert _strict(alter) == "ALTER AUTHENTICATION a HOST TLS '::/0'"
    alter.set(
        "actions",
        [
            vexp.AuthenticationSet(
                expressions=[
                    vexp.AuthenticationParameter(
                        this=exp.var("validate_type"), expression=exp.Literal.string("JWT")
                    ),
                    vexp.AuthenticationParameter(
                        this=exp.var("jit_enabled"), expression=exp.Literal.string("no")
                    ),
                ]
            )
        ],
    )
    assert _strict(alter) == (
        "ALTER AUTHENTICATION a SET validate_type = 'JWT', jit_enabled = 'no'"
    )


@pytest.mark.parametrize(
    ("sql", "name", "value", "canonical"),
    [
        ("ALTER AUTHENTICATION a SET validate_type = 'IDP'", "validate_type", "IDP", "IDP"),
        ("ALTER AUTHENTICATION a SET VALIDATE_TYPE='jwt'", "validate_type", "JWT", "JWT"),
        ("ALTER AUTHENTICATION a SET jit_enabled = 'yes'", "jit_enabled", "yes", "yes"),
        ("ALTER AUTHENTICATION a SET JIT_ENABLED='NO'", "jit_enabled", "no", "no"),
    ],
)
def test_safe_authentication_parameters_are_typed(
    sql: str, name: str, value: str, canonical: str
) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterAuthentication)
    action = expression.actions[0]
    assert isinstance(action, vexp.AuthenticationSet)
    parameter = action.expressions[0]
    assert isinstance(parameter, vexp.AuthenticationParameter)
    assert parameter.args["this"] == exp.var(name)
    assert parameter.args["expression"] == exp.Literal.string(value)
    assert f"{name} = '{canonical}'" in _strict(expression)


def test_authentication_set_order_serialization_transform_optimizer_and_batches() -> None:
    expression = assert_roundtrip(
        "/* lead */ ALTER AUTHENTICATION a SET jit_enabled='yes', validate_type='jwt' /* tail */"
    )
    action = expression.actions[0]
    assert isinstance(action, vexp.AuthenticationSet)
    assert [parameter.args["this"].this for parameter in action.expressions] == [
        "jit_enabled",
        "validate_type",
    ]
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression
    transformed = expression.transform(
        lambda node: (
            exp.Literal.string("no")
            if isinstance(node, exp.Literal) and node.this == "yes"
            else node
        )
    )
    assert "jit_enabled = 'no'" in _strict(transformed)
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterAuthentication)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.find(vexp.AuthenticationSet).type == exp.DType.UNKNOWN.into_expr()
    statements = parse(
        "ALTER AUTHENTICATION a SET validate_type='IDP'; SELECT 1; "
        "ALTER AUTHENTICATION a SET jit_enabled='no'",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.AlterAuthentication,
        exp.Select,
        vexp.AlterAuthentication,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER AUTHENTICATION set ENABLE",
        "ALTER AUTHENTICATION \"SET\" SET validate_type = 'JWT'",
    ],
)
def test_authentication_target_named_set_does_not_confuse_the_secret_firewall(sql: str) -> None:
    assert isinstance(assert_roundtrip(sql), vexp.AlterAuthentication)


def test_alter_authentication_serialization_transform_optimizer_comments_and_batches() -> None:
    expression = parse_one(
        "/* lead */ ALTER AUTHENTICATION a HOST TLS '10.0.0.0/8' /* tail */",
        read="vertica",
    )
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression
    transformed = expression.transform(
        lambda node: (
            exp.Literal.string("host.example")
            if isinstance(node, exp.Literal) and node.this == "10.0.0.0/8"
            else node
        )
    )
    assert "'host.example'" in _strict(transformed)
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterAuthentication)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.find(vexp.AuthenticationAccess).type == exp.DType.UNKNOWN.into_expr()
    statements = parse(
        "ALTER AUTHENTICATION a ENABLE; GRANT AUTHENTICATION a TO analyst; "
        "ALTER AUTHENTICATION a PRIORITY 2",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.AlterAuthentication,
        vexp.AuthenticationGrant,
        vexp.AlterAuthentication,
    ]


def test_serialization_transform_optimizer_types_comments_and_batches() -> None:
    expression = parse_one(
        "CREATE AUTHENTICATION ldap_auth METHOD 'ldap' HOST TLS '10.0.0.0/8' ENFORCEMFA",
        read="vertica",
    )
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression
    transformed = expression.transform(
        lambda node: (
            exp.Literal.string("host.example")
            if isinstance(node, exp.Literal) and node.this == "10.0.0.0/8"
            else node
        )
    )
    assert "'host.example'" in _strict(transformed)
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.CreateAuthentication)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.find(vexp.AuthenticationAccess).type == exp.DType.UNKNOWN.into_expr()
    assert_roundtrip("/* lead */ CREATE AUTHENTICATION a METHOD 'hash' LOCAL /* tail */")
    statements = parse(
        "CREATE AUTHENTICATION a METHOD 'hash' LOCAL; "
        "GRANT AUTHENTICATION a TO analyst; DROP AUTHENTICATION a",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateAuthentication,
        vexp.AuthenticationGrant,
        vexp.DropAuthentication,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION",
        "CREATE AUTHENTICATION a",
        "CREATE AUTHENTICATION a METHOD",
        "CREATE AUTHENTICATION a METHOD hash LOCAL",
        "CREATE AUTHENTICATION a METHOD 'password' LOCAL",
        "CREATE AUTHENTICATION a METHOD 'ldap'",
        "CREATE AUTHENTICATION a METHOD 'ldap' LOCAL 'address'",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST TLS",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST NO 'address'",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST 'address' TLS",
        "CREATE AUTHENTICATION a METHOD 'ldap' LOCAL FALLTHROUGH ENFORCEMFA",
        "CREATE AUTHENTICATION a METHOD 'gss' LOCAL FALLTHROUGH",
        "CREATE AUTHENTICATION a METHOD 'oauth' LOCAL FALLTHROUGH",
        "CREATE AUTHENTICATION a METHOD 'reject' LOCAL FALLTHROUGH",
        "CREATE AUTHENTICATION a METHOD 'trust' LOCAL FALLTHROUGH",
        "CREATE OR REPLACE AUTHENTICATION a METHOD 'hash' LOCAL",
        "CREATE IF NOT EXISTS AUTHENTICATION a METHOD 'hash' LOCAL",
        "DROP AUTHENTICATION",
        "DROP AUTHENTICATION a, b",
        "DROP AUTHENTICATION a RESTRICT",
        "DROP IF EXISTS AUTHENTICATION a",
        "DROP AUTHENTICATION a IF EXISTS",
        "DROP AUTHENTICATION a CASCADE extra",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_invalid_authentication_syntax_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE \"AUTHENTICATION\" a METHOD 'hash' LOCAL",
        "CREATE AUTHENTICATION a \"METHOD\" 'hash' LOCAL",
        "CREATE AUTHENTICATION a METHOD 'hash' \"LOCAL\"",
        "CREATE AUTHENTICATION a METHOD 'hash' HOST \"TLS\" 'address'",
        "CREATE AUTHENTICATION a METHOD 'hash' HOST \"NO\" TLS 'address'",
        'DROP "AUTHENTICATION" a',
        'DROP AUTHENTICATION "IF" EXISTS a',
        'DROP AUTHENTICATION a "CASCADE"',
    ],
)
def test_authentication_keyword_provenance_is_exact(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_confusable_authentication_kind_does_not_dispatch() -> None:
    expression = parse_one("CREATE AUTHENTICAT\u0130ON a METHOD 'hash' LOCAL", read="vertica")
    assert not isinstance(expression, vexp.CreateAuthentication)


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER AUTHENTICATION",
        "ALTER AUTHENTICATION a",
        "ALTER AUTHENTICATION a ENABLE DISABLE",
        "ALTER AUTHENTICATION a LOCAL HOST 'address'",
        "ALTER AUTHENTICATION a LOCAL 'address'",
        "ALTER AUTHENTICATION a HOST",
        "ALTER AUTHENTICATION a HOST TLS",
        "ALTER AUTHENTICATION a HOST NO 'address'",
        "ALTER AUTHENTICATION a HOST NO TLS",
        "ALTER AUTHENTICATION a HOST 'address' TLS",
        "ALTER AUTHENTICATION a RENAME",
        "ALTER AUTHENTICATION a RENAME b",
        "ALTER AUTHENTICATION a RENAME TO",
        "ALTER AUTHENTICATION a METHOD",
        "ALTER AUTHENTICATION a METHOD ldap",
        "ALTER AUTHENTICATION a METHOD 'password'",
        "ALTER AUTHENTICATION a PRIORITY",
        "ALTER AUTHENTICATION a PRIORITY -1",
        "ALTER AUTHENTICATION a PRIORITY +1",
        "ALTER AUTHENTICATION a PRIORITY 1.0",
        "ALTER AUTHENTICATION a PRIORITY '1'",
        "ALTER AUTHENTICATION a ENFORCEMFA",
        "ALTER AUTHENTICATION a ENFORCEMFA 1",
        "ALTER AUTHENTICATION a ENFORCEMFA 'true'",
        "ALTER AUTHENTICATION a NO",
        "ALTER AUTHENTICATION a NO ENFORCEMFA",
        "ALTER AUTHENTICATION a FALLTHROUGH PRIORITY 1",
        "ALTER IF EXISTS AUTHENTICATION a ENABLE",
        "ALTER AUTHENTICATION a SET safe = 1",
        "ALTER AUTHENTICATION a SET",
        "ALTER AUTHENTICATION a SET validate_type",
        "ALTER AUTHENTICATION a SET validate_type 'JWT'",
        "ALTER AUTHENTICATION a SET validate_type = 'JWT',",
        "ALTER AUTHENTICATION a SET validate_type = 'JWT', validate_type = 'IDP'",
        "ALTER AUTHENTICATION a SET validate_type = 'JWT' ENABLE",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_invalid_alter_authentication_syntax_fails_closed(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'ALTER "AUTHENTICATION" a ENABLE',
        'ALTER AUTHENTICATION a "ENABLE"',
        "ALTER AUTHENTICATION a HOST \"TLS\" 'address'",
        "ALTER AUTHENTICATION a HOST \"NO\" TLS 'address'",
        'ALTER AUTHENTICATION a "RENAME" TO b',
        'ALTER AUTHENTICATION a RENAME "TO" b',
        "ALTER AUTHENTICATION a \"METHOD\" 'ldap'",
        'ALTER AUTHENTICATION a "PRIORITY" 1',
        'ALTER AUTHENTICATION a "ENFORCEMFA" TRUE',
        'ALTER AUTHENTICATION a "FALLTHROUGH"',
    ],
)
def test_alter_authentication_keyword_provenance_is_exact(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_authentication_identifier_contract_and_dispatch_collisions() -> None:
    exact = f"a{'é' * 63}b"
    assert len(exact.encode()) == 128
    assert_roundtrip(f"CREATE AUTHENTICATION {exact} METHOD 'hash' LOCAL")
    assert_roundtrip(f"ALTER AUTHENTICATION {exact} ENABLE")
    with pytest.raises(ParseError):
        parse_one(f"CREATE AUTHENTICATION {exact}é METHOD 'hash' LOCAL", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE AUTHENTICATION app.auth METHOD 'hash' LOCAL", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE AUTHENTICATION SELECT METHOD 'hash' LOCAL", read="vertica")
    assert_roundtrip("CREATE AUTHENTICATION \"SELECT\" METHOD 'hash' LOCAL")

    for sql in (
        "CREATE USER authentication ACCOUNT LOCK",
        "CREATE PROFILE authentication LIMIT PASSWORD_MIN_LENGTH 8",
        "GRANT AUTHENTICATION authentication TO analyst",
        "REVOKE AUTHENTICATION authentication FROM analyst",
        "CREATE TABLE authentication (id INT)",
    ):
        expression = parse_one(sql, read="vertica")
        assert not isinstance(
            expression,
            (vexp.CreateAuthentication, vexp.AlterAuthentication, vexp.DropAuthentication),
        )


@pytest.mark.parametrize(
    "name",
    ["bind_password", "client_secret", "UnknownParameter", "validate_type"],
)
@pytest.mark.parametrize(
    "value",
    [
        "'S3CR3T_DO_NOT_LEAK'",
        "E'S3CR3T_DO_NOT_LEAK'",
        "U&'S3CR3T_DO_NOT_LEAK'",
        "N'S3CR3T_DO_NOT_LEAK'",
        "$$S3CR3T_DO_NOT_LEAK$$",
        "B'01010011'",
        "X'533343523354'",
        "R'S3CR3T_DO_NOT_LEAK'",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_excluded_authentication_set_values_are_sanitized(
    name: str,
    value: str,
    error_level: ErrorLevel,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sql = f"ALTER AUTHENTICATION a SET {name} = {value}"
    caplog.clear()
    with caplog.at_level(logging.DEBUG), pytest.raises(ParseError) as caught:
        parse_one(sql, read="vertica", error_level=error_level)
    captured = capsys.readouterr()
    observed = " ".join(
        (str(caught.value), repr(caught.value.errors), caplog.text, captured.out, captured.err)
    )
    assert "S3CR3T_DO_NOT_LEAK" not in observed
    assert str(caught.value) == "Unsupported secret-bearing AUTHENTICATION clause"


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION a METHOD 'ldap' LOCAL SET bind_password = 'S3CR3T_DO_NOT_LEAK'",
        "ALTER AUTHENTICATION a SET validate_type = IDP",
        "ALTER AUTHENTICATION a SET validate_type = 'OIDC'",
        "ALTER AUTHENTICATION a SET jit_enabled = 'true'",
        "ALTER AUTHENTICATION a SET validate_hostname = 'true'",
        "ALTER AUTHENTICATION a SET \"validate_type\" = 'JWT'",
        "ALTER AUTHENTICATION a SET validate_type = 'JWT', client_secret = 'secret'",
    ],
)
def test_unreviewed_authentication_parameters_fail_through_sanitizer(sql: str) -> None:
    with pytest.raises(ParseError) as caught:
        parse_one(sql, read="vertica")
    assert str(caught.value) == "Unsupported secret-bearing AUTHENTICATION clause"


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION a METHOD 'hash' LOCAL",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST TLS 'address' ENFORCEMFA FALLTHROUGH",
        "ALTER AUTHENTICATION a HOST NO TLS 'address'",
        "ALTER AUTHENTICATION a ENFORCEMFA FALSE",
        "ALTER AUTHENTICATION a SET validate_type = 'JWT'",
        "DROP AUTHENTICATION IF EXISTS a CASCADE",
    ],
)
def test_authentication_roots_fail_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        parse_one(sql, read="vertica").sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="TABLE",
            method=exp.Literal.string("hash"),
            access=_access("LOCAL"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.var("hash"),
            access=_access("LOCAL"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("password"),
            access=_access("LOCAL"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("hash"),
            access=exp.var("LOCAL"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("hash"),
            access=_access("LOCAL", "address"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("hash"),
            access=_access("HOST"),
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("trust"),
            access=_access("LOCAL"),
            fallthrough=True,
        ),
        vexp.CreateAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            method=exp.Literal.string("hash"),
            access=_access("LOCAL"),
            enforce_mfa="yes",
        ),
        vexp.DropAuthentication(kind="AUTHENTICATION"),
        vexp.DropAuthentication(this=_identifier("a"), kind="TABLE"),
        vexp.DropAuthentication(this=_identifier("a"), kind="AUTHENTICATION", exists="yes"),
        vexp.AlterAuthentication(
            this=_identifier("a"),
            kind="TABLE",
            actions=[vexp.AuthenticationAction(this=exp.var("ENABLE"))],
        ),
        vexp.AlterAuthentication(this=_identifier("a"), kind="AUTHENTICATION", actions=[]),
        vexp.AlterAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            actions=[
                vexp.AuthenticationAction(this=exp.var("ENABLE")),
                vexp.AuthenticationAction(this=exp.var("DISABLE")),
            ],
        ),
        vexp.AlterAuthentication(
            this=_identifier("a"), kind="AUTHENTICATION", actions=[exp.var("ENABLE")]
        ),
        vexp.AlterAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            actions=[
                vexp.AuthenticationAction(
                    this=exp.var("PRIORITY"), expression=exp.Literal.number("-1")
                )
            ],
        ),
        vexp.AlterAuthentication(
            this=_identifier("a"),
            kind="AUTHENTICATION",
            actions=[
                vexp.AuthenticationAction(this=exp.var("ENFORCEMFA"), expression=exp.var("TRUE"))
            ],
        ),
        vexp.AuthenticationAction(this=exp.var("BOGUS")),
        vexp.AuthenticationSet(),
        vexp.AuthenticationSet(expressions=[]),
        vexp.AuthenticationSet(expressions={}),
        vexp.AuthenticationSet(expressions=[exp.var("validate_type")]),
        vexp.AuthenticationSet(
            expressions=[
                vexp.AuthenticationParameter(
                    this=exp.var("validate_type"), expression=exp.Literal.string("JWT")
                ),
                vexp.AuthenticationParameter(
                    this=exp.var("validate_type"), expression=exp.Literal.string("IDP")
                ),
            ]
        ),
        vexp.AuthenticationParameter(
            this=exp.var("client_secret"), expression=exp.Literal.string("secret")
        ),
        vexp.AuthenticationParameter(
            this=exp.var("VALIDATE_TYPE"), expression=exp.Literal.string("JWT")
        ),
        vexp.AuthenticationParameter(
            this=_identifier("validate_type", quoted=True), expression=exp.Literal.string("JWT")
        ),
        vexp.AuthenticationParameter(this=exp.var("validate_type")),
        vexp.AuthenticationParameter(this=exp.var("validate_type"), expression=exp.var("JWT")),
        vexp.AuthenticationParameter(
            this=exp.var("validate_type"), expression=exp.Literal.string("OIDC")
        ),
        vexp.AuthenticationParameter(
            this=exp.var("jit_enabled"), expression=exp.Literal.string("true")
        ),
        _set_arg(
            vexp.AuthenticationParameter(
                this=exp.var("validate_type"), expression=exp.Literal.string("JWT")
            ),
            "bogus",
            True,
        ),
        _set_arg(_access("LOCAL"), "bogus", True),
    ],
)
def test_malformed_programmatic_authentication_asts_fail_atomically(
    expression: exp.Expr,
) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_authentication_access_leaf_fails_in_foreign_dialects() -> None:
    for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
        with pytest.raises((UnsupportedError, ValueError)):
            _access("HOST", "address", tls=True).sql(
                dialect=dialect, unsupported_level=ErrorLevel.RAISE
            )
        with pytest.raises((UnsupportedError, ValueError)):
            vexp.AuthenticationAction(this=exp.var("ENABLE")).sql(
                dialect=dialect, unsupported_level=ErrorLevel.RAISE
            )
        with pytest.raises((UnsupportedError, ValueError)):
            vexp.AuthenticationSet(
                expressions=[
                    vexp.AuthenticationParameter(
                        this=exp.var("validate_type"), expression=exp.Literal.string("JWT")
                    )
                ]
            ).sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
