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


def test_authentication_identifier_contract_and_dispatch_collisions() -> None:
    exact = f"a{'é' * 63}b"
    assert len(exact.encode()) == 128
    assert_roundtrip(f"CREATE AUTHENTICATION {exact} METHOD 'hash' LOCAL")
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
        assert not isinstance(expression, (vexp.CreateAuthentication, vexp.DropAuthentication))


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER AUTHENTICATION a SET bind_password = 'S3CR3T_DO_NOT_LEAK'",
        "ALTER AUTHENTICATION a SET client_secret = E'S3CR3T_DO_NOT_LEAK'",
        "ALTER AUTHENTICATION a SET client_secret = U&'S3CR3T_DO_NOT_LEAK'",
        "ALTER AUTHENTICATION a SET client_secret = N'S3CR3T_DO_NOT_LEAK'",
        "ALTER AUTHENTICATION a SET client_secret = $$S3CR3T_DO_NOT_LEAK$$",
        "ALTER AUTHENTICATION a SET client_secret = B'0101'",
        "ALTER AUTHENTICATION a SET client_secret = X'DEAD'",
        "CREATE AUTHENTICATION a METHOD 'ldap' LOCAL SET bind_password = 'S3CR3T_DO_NOT_LEAK'",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_excluded_authentication_set_values_are_sanitized(
    sql: str, error_level: ErrorLevel, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.clear()
    with caplog.at_level(logging.DEBUG), pytest.raises(ParseError) as caught:
        parse_one(sql, read="vertica", error_level=error_level)
    observed = " ".join((str(caught.value), repr(caught.value.errors), caplog.text))
    assert "S3CR3T_DO_NOT_LEAK" not in observed
    assert str(caught.value) == "Unsupported secret-bearing AUTHENTICATION clause"


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION a METHOD 'hash' LOCAL",
        "CREATE AUTHENTICATION a METHOD 'ldap' HOST TLS 'address' ENFORCEMFA FALLTHROUGH",
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
