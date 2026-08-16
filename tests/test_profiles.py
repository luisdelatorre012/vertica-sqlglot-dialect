"""Semantic Vertica PROFILE lifecycle regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

PARAMETERS = (
    "PASSWORD_LIFE_TIME",
    "PASSWORD_MIN_LIFE_TIME",
    "PASSWORD_GRACE_TIME",
    "FAILED_LOGIN_ATTEMPTS",
    "PASSWORD_LOCK_TIME",
    "PASSWORD_REUSE_MAX",
    "PASSWORD_REUSE_TIME",
    "PASSWORD_MAX_LENGTH",
    "PASSWORD_MIN_LENGTH",
    "PASSWORD_MIN_LETTERS",
    "PASSWORD_MIN_UPPERCASE_LETTERS",
    "PASSWORD_MIN_LOWERCASE_LETTERS",
    "PASSWORD_MIN_DIGITS",
    "PASSWORD_MIN_SYMBOLS",
    "PASSWORD_MIN_CHAR_CHANGE",
)


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str, quoted: bool = False) -> exp.Identifier:
    return exp.to_identifier(name, quoted=quoted)


def _parameter(name: str, value: exp.Expr) -> vexp.ProfileParameter:
    return vexp.ProfileParameter(this=exp.var(name), expression=value)


def _limit(*parameters: vexp.ProfileParameter) -> vexp.ProfileLimit:
    return vexp.ProfileLimit(expressions=list(parameters))


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


def test_all_profile_parameters_are_typed_ordered_and_roundtrip() -> None:
    pairs = [f"{name} {'8' if name == 'PASSWORD_MAX_LENGTH' else '1'}" for name in PARAMETERS]
    expression = assert_roundtrip(f"CREATE PROFILE policy LIMIT {' '.join(pairs)}")

    assert isinstance(expression, vexp.CreateProfile)
    assert expression.kind == "PROFILE"
    assert isinstance(expression.args["limit"], vexp.ProfileLimit)
    parameters = expression.args["limit"].expressions
    assert [parameter.name for parameter in parameters] == list(PARAMETERS)
    assert all(isinstance(parameter, vexp.ProfileParameter) for parameter in parameters)
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "root"),
    [
        ("CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH UNLIMITED", vexp.CreateProfile),
        ("ALTER PROFILE p LIMIT PASSWORD_MIN_LENGTH DEFAULT", vexp.AlterProfile),
        ("ALTER PROFILE DEFAULT LIMIT PASSWORD_MIN_SYMBOLS 1", vexp.AlterProfile),
        ("ALTER PROFILE p RENAME TO p2", vexp.AlterProfile),
        ("DROP PROFILE p", vexp.DropProfiles),
        ("DROP PROFILE IF EXISTS p, p2 CASCADE", vexp.DropProfiles),
    ],
)
def test_profile_lifecycle_forms_roundtrip(sql: str, root: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, root)
    _assert_parent_links(expression)


def test_programmatic_profile_lifecycle_generates_exact_sql() -> None:
    create = vexp.CreateProfile(
        this=_identifier("p"),
        kind="PROFILE",
        limit=_limit(_parameter("PASSWORD_MAX_LENGTH", exp.Literal.number("64"))),
    )
    alter = vexp.AlterProfile(
        this=_identifier("DEFAULT"),
        kind="PROFILE",
        actions=[_limit(_parameter("PASSWORD_MIN_SYMBOLS", exp.var("DEFAULT")))],
    )
    rename = vexp.AlterProfile(
        this=_identifier("p"),
        kind="PROFILE",
        actions=[exp.AlterRename(this=_identifier("p2"))],
    )
    drop = vexp.DropProfiles(
        this=_identifier("p"),
        expressions=[_identifier("p2")],
        kind="PROFILE",
        exists=True,
        cascade=True,
    )
    assert [_strict(item) for item in (create, alter, rename, drop)] == [
        "CREATE PROFILE p LIMIT PASSWORD_MAX_LENGTH 64",
        "ALTER PROFILE DEFAULT LIMIT PASSWORD_MIN_SYMBOLS DEFAULT",
        "ALTER PROFILE p RENAME TO p2",
        "DROP PROFILE IF EXISTS p, p2 CASCADE",
    ]


def test_serialization_copy_transform_optimizer_types_comments_and_statements() -> None:
    expression = parse_one(
        "ALTER PROFILE p LIMIT PASSWORD_MAX_LENGTH 64 PASSWORD_MIN_LENGTH 12",
        read="vertica",
    )
    assert expression.copy() == expression
    restored = exp.Expr.load(expression.dump())
    assert restored == expression
    assert isinstance(restored, vexp.AlterProfile)
    transformed = expression.transform(
        lambda node: (
            exp.Literal.number("16")
            if isinstance(node, exp.Literal) and node.this == "12"
            else node
        )
    )
    assert _strict(transformed).endswith("PASSWORD_MIN_LENGTH 16")
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterProfile)
    assert parse_one(_strict(optimized), read="vertica") == optimized
    annotated = annotate_types(expression.copy(), dialect="vertica")
    assert annotated.find(vexp.ProfileParameter).type == exp.DType.UNKNOWN.into_expr()
    assert_roundtrip("/* lead */ CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 8 /* tail */")
    statements = parse(
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 8; "
        "ALTER PROFILE p RENAME TO p2; DROP PROFILE p2",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateProfile,
        vexp.AlterProfile,
        vexp.DropProfiles,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE PROFILE",
        "CREATE PROFILE DEFAULT LIMIT PASSWORD_MIN_LENGTH 8",
        'CREATE PROFILE "DEFAULT" LIMIT PASSWORD_MIN_LENGTH 8',
        "CREATE PROFILE p",
        "CREATE PROFILE p LIMIT",
        "CREATE PROFILE p LIMIT UNKNOWN 1",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH DEFAULT",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 1, PASSWORD_MIN_DIGITS 1",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 1 password_min_length 2",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH -1",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH +1",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 1.5",
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH '1'",
        "CREATE PROFILE p LIMIT PASSWORD_LIFE_TIME 0",
        "CREATE PROFILE p LIMIT PASSWORD_MAX_LENGTH 7",
        "CREATE PROFILE p LIMIT PASSWORD_MAX_LENGTH 513",
        "CREATE PROFILE p LIMIT PASSWORD_MAX_LENGTH 8 PASSWORD_MIN_LENGTH 9",
        "ALTER PROFILE",
        'ALTER PROFILE "DEFAULT" LIMIT PASSWORD_MIN_LENGTH 1',
        "ALTER PROFILE DEFAULT RENAME TO p",
        "ALTER PROFILE p RENAME TO DEFAULT",
        'ALTER PROFILE p RENAME TO "DEFAULT"',
        "ALTER PROFILE p RENAME p2",
        "ALTER PROFILE p LIMIT",
        "DROP PROFILE",
        "DROP PROFILE DEFAULT",
        'DROP PROFILE "DEFAULT"',
        "DROP PROFILE p,",
        "DROP PROFILE p RESTRICT",
        "DROP IF EXISTS PROFILE p",
        "DROP PROFILE p IF EXISTS",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_recognized_invalid_profile_syntax_fails_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'CREATE "PROFILE" p LIMIT PASSWORD_MIN_LENGTH 8',
        "CREATE PROF\u0131LE p LIMIT PASSWORD_MIN_LENGTH 8",
        'CREATE PROFILE p "LIMIT" PASSWORD_MIN_LENGTH 8',
        'CREATE PROFILE p LIMIT "PASSWORD_MIN_LENGTH" 8',
        'ALTER PROFILE p "RENAME" TO p2',
        'ALTER PROFILE p RENAME "TO" p2',
        'ALTER PROFILE p LIMIT PASSWORD_MIN_LENGTH "UNLIMITED"',
        'DROP PROFILE "p" "CASCADE"',
        'DROP PROFILE "IF" EXISTS p',
    ],
)
def test_profile_keyword_provenance_is_exact(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_profile_identifiers_share_utf8_and_tokenizer_contract() -> None:
    exact = f"a{'é' * 63}b"
    assert len(exact.encode()) == 128
    assert_roundtrip(f"CREATE PROFILE {exact} LIMIT PASSWORD_MIN_LENGTH 8")
    with pytest.raises(ParseError):
        parse_one(f"CREATE PROFILE {exact}é LIMIT PASSWORD_MIN_LENGTH 8", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE PROFILE SELECT LIMIT PASSWORD_MIN_LENGTH 8", read="vertica")
    assert_roundtrip('CREATE PROFILE "SELECT" LIMIT PASSWORD_MIN_LENGTH 8')
    with pytest.raises(ParseError):
        parse_one("CREATE PROFILE app.p LIMIT PASSWORD_MIN_LENGTH 8", read="vertica")

    surrogate = chr(0xD800)
    with pytest.raises(ParseError):
        parse_one(f'CREATE PROFILE "{surrogate}" LIMIT PASSWORD_MIN_LENGTH 8', read="vertica")
    with pytest.raises(UnsupportedError):
        _strict(
            vexp.CreateProfile(
                this=_identifier(surrogate, quoted=True),
                kind="PROFILE",
                limit=_limit(_parameter("PASSWORD_MIN_LENGTH", exp.Literal.number("8"))),
            )
        )


def test_huge_values_are_validated_lexically() -> None:
    huge = "9" * 10000
    with pytest.raises(ParseError):
        parse_one(f"CREATE PROFILE p LIMIT PASSWORD_MAX_LENGTH {huge}", read="vertica")
    expression = parse_one(f"CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH {huge}", read="vertica")
    assert huge in _strict(expression)


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "sql",
    [
        "CREATE PROFILE p LIMIT PASSWORD_MIN_LENGTH 8",
        "ALTER PROFILE p RENAME TO p2",
        "DROP PROFILE p, p2 CASCADE",
    ],
)
def test_profile_roots_fail_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        parse_one(sql, read="vertica").sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateProfile(this=_identifier("p"), kind="TABLE", limit=_limit()),
        vexp.CreateProfile(this=_identifier("p"), kind="PROFILE"),
        vexp.CreateProfile(this=_identifier("DEFAULT"), kind="PROFILE", limit=_limit()),
        vexp.CreateProfile(this=_identifier("p"), kind="PROFILE", limit=exp.var("x")),
        vexp.CreateProfile(this=_identifier("p"), kind="PROFILE", limit=_limit()),
        vexp.AlterProfile(this=_identifier("p"), kind="PROFILE", actions=[]),
        vexp.AlterProfile(this=_identifier("p"), kind="PROFILE", actions=_limit()),
        vexp.AlterProfile(this=_identifier("p"), kind="PROFILE", actions=[_limit(), _limit()]),
        vexp.AlterProfile(
            this=_identifier("DEFAULT"),
            kind="PROFILE",
            actions=[exp.AlterRename(this=_identifier("p"))],
        ),
        vexp.DropProfiles(kind="PROFILE"),
        vexp.DropProfiles(this=_identifier("DEFAULT"), kind="PROFILE"),
        vexp.DropProfiles(this=_identifier("p"), expressions={}, kind="PROFILE"),
        vexp.DropProfiles(this=_identifier("p"), kind="PROFILE", exists="yes"),
        _limit(),
        _limit(exp.var("bad")),
        _limit(_parameter("UNKNOWN", exp.Literal.number("1"))),
        _limit(_parameter("PASSWORD_LIFE_TIME", exp.Literal.number("0"))),
        _limit(_parameter("PASSWORD_MAX_LENGTH", exp.Literal.number("513"))),
        _limit(_parameter("PASSWORD_MIN_LENGTH", exp.Literal.string("1"))),
        _limit(_parameter("PASSWORD_MIN_LENGTH", exp.var("DEFAULT"))),
        _set_arg(
            _parameter("PASSWORD_MIN_LENGTH", exp.Literal.number("1")),
            "bogus",
            [],
        ),
    ],
)
def test_malformed_programmatic_profile_asts_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_profile_detached_leaves_fail_atomically_in_foreign_dialects() -> None:
    leaves: tuple[exp.Expr, ...] = (
        _parameter("PASSWORD_MIN_LENGTH", exp.Literal.number("8")),
        _limit(_parameter("PASSWORD_MIN_LENGTH", exp.Literal.number("8"))),
    )
    for leaf in leaves:
        for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
            with pytest.raises((UnsupportedError, ValueError)):
                leaf.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_excluded_profile_families_remain_outside_p01() -> None:
    with pytest.raises(ParseError):
        parse_one("PROFILE SELECT 1", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE USER analyst PROFILE p", read="vertica")
