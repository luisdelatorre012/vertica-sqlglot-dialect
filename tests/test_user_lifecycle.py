"""Security-conscious semantic Vertica USER lifecycle regressions."""

from __future__ import annotations

import logging

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "names"),
    [
        ("CREATE USER analyst PROFILE DEFAULT", ["PROFILE"]),
        (
            "CREATE USER analyst PROFILE security, RESOURCE POOL general",
            ["PROFILE", "RESOURCE POOL"],
        ),
        (
            "CREATE USER analyst RESOURCE POOL general FOR SUBCLUSTER etl",
            ["RESOURCE POOL"],
        ),
        ("ALTER USER analyst PROFILE security", ["PROFILE"]),
        (
            "ALTER USER analyst RESOURCE POOL general FOR SUBCLUSTER etl",
            ["RESOURCE POOL"],
        ),
        (
            'ALTER USER analyst RESOURCE POOL general, PROFILE "strict profile", '
            'RESOURCE POOL "etl pool" FOR SUBCLUSTER "etl sc", ACCOUNT LOCK, PASSWORD EXPIRE',
            ["RESOURCE POOL", "PROFILE", "RESOURCE POOL", "ACCOUNT LOCK", "PASSWORD EXPIRE"],
        ),
    ],
)
def test_user_profile_and_resource_pool_assignments_are_typed_and_ordered(
    sql: str, names: list[str]
) -> None:
    expression = assert_roundtrip(sql)
    actions = expression.args.get("parameters") or expression.args.get("actions")
    actions = actions if isinstance(actions, list) else [actions]
    assert all(isinstance(action, (vexp.UserAction, vexp.UserParameter)) for action in actions)
    assert [action.this.name for action in actions] == names
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER analyst PROFILE 'secret'",
        "CREATE USER analyst PROFILE security PROFILE other",
        "CREATE USER analyst PROFILE security, PROFILE other",
        "CREATE USER analyst RESOURCE POOL general RESOURCE POOL other",
        "CREATE USER analyst RESOURCE POOL general, RESOURCE POOL other",
        (
            "CREATE USER analyst RESOURCE POOL etl FOR SUBCLUSTER sc, "
            "RESOURCE POOL other FOR SUBCLUSTER other_sc"
        ),
        "CREATE USER analyst RESOURCE POOL general FOR etl",
        "ALTER USER analyst RESOURCE POOL general FOR SUBCLUSTER",
        "ALTER USER analyst PROFILE security,",
        "ALTER USER analyst RENAME TO renamed, PROFILE security",
    ],
)
def test_user_assignments_reject_malformed_or_duplicate_parameters(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str, quoted: bool = False) -> exp.Identifier:
    return exp.to_identifier(name, quoted=quoted)


def _action(name: str) -> vexp.UserAction:
    return vexp.UserAction(this=exp.var(name))


def _parameter(
    name: str, value: str, *, subcluster: str | None = None, quoted: bool = False
) -> vexp.UserParameter:
    return vexp.UserParameter(
        this=exp.var(name),
        expression=_identifier(value, quoted=quoted),
        subcluster=_identifier(subcluster) if subcluster is not None else None,
    )


def _limit_parameter(name: str, value: exp.Expr, *, scope: str | None = None) -> vexp.UserParameter:
    return vexp.UserParameter(
        this=exp.var(name),
        expression=value,
        scope=exp.var(scope) if scope is not None else None,
    )


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize(
    ("sql", "name", "value", "scope"),
    [
        ("CREATE USER analyst GRACEPERIOD NONE", "GRACEPERIOD", "NONE", None),
        ("CREATE USER analyst GRACEPERIOD '20 days'", "GRACEPERIOD", "20 days", None),
        (
            "ALTER USER analyst IDLESESSIONTIMEOUT '365 days'",
            "IDLESESSIONTIMEOUT",
            "365 days",
            None,
        ),
        ("CREATE USER analyst MAXCONNECTIONS NONE", "MAXCONNECTIONS", "NONE", None),
        (
            "CREATE USER analyst MAXCONNECTIONS 00010 ON DATABASE",
            "MAXCONNECTIONS",
            "00010",
            "DATABASE",
        ),
        (
            "ALTER USER analyst MAXCONNECTIONS 10 ON NODE",
            "MAXCONNECTIONS",
            "10",
            "NODE",
        ),
        ("CREATE USER analyst MEMORYCAP '40%'", "MEMORYCAP", "40%", None),
        ("ALTER USER analyst MEMORYCAP NONE", "MEMORYCAP", "NONE", None),
        ("CREATE USER analyst RUNTIMECAP '1 year'", "RUNTIMECAP", "1 year", None),
        ("ALTER USER analyst TEMPSPACECAP '10G'", "TEMPSPACECAP", "10G", None),
        (
            "ALTER USER analyst SECURITY_ALGORITHM 'SHA512'",
            "SECURITY_ALGORITHM",
            "SHA512",
            None,
        ),
    ],
)
def test_user_time_and_capacity_limits_are_typed(
    sql: str, name: str, value: str, scope: str | None
) -> None:
    expression = assert_roundtrip(sql)
    parameters = expression.args.get("parameters") or expression.args.get("actions")
    assert isinstance(parameters, list)
    parameter = parameters[0]
    assert isinstance(parameter, vexp.UserParameter)
    assert parameter.this.name == name
    assert parameter.expression.name == value
    parsed_scope = parameter.args.get("scope")
    assert (parsed_scope.name if isinstance(parsed_scope, exp.Var) else None) == scope
    _assert_parent_links(expression)


def test_user_limits_preserve_order_and_canonicalize_finite_values() -> None:
    sql = (
        "ALTER USER analyst GRACEPERIOD '1 day 2 hours', MAXCONNECTIONS 12 ON NODE, "
        "MEMORYCAP '010g', RUNTIMECAP '12:30:00', TEMPSPACECAP NONE, "
        "SECURITY_ALGORITHM 'md5'"
    )
    expression = parse_one(sql, read="vertica")
    assert _strict(expression) == (
        "ALTER USER analyst GRACEPERIOD '1 day 2 hours', MAXCONNECTIONS 12 ON NODE, "
        "MEMORYCAP '010G', RUNTIMECAP '12:30:00', TEMPSPACECAP NONE, "
        "SECURITY_ALGORITHM 'MD5'"
    )
    assert parse_one(_strict(expression), read="vertica") == expression
    assert exp.Expr.load(expression.dump()) == expression
    assert expression.copy() == expression
    transformed = expression.transform(
        lambda node: (
            exp.Literal.string("20G")
            if isinstance(node, exp.Literal) and node.is_string and node.this == "010G"
            else node
        )
    )
    assert "MEMORYCAP '20G'" in _strict(transformed)
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterUser)
    assert len(list(optimized.find_all(vexp.UserParameter))) == 6
    annotated = annotate_types(expression, dialect="vertica")
    assert all(
        parameter.type == exp.DType.UNKNOWN.into_expr()
        for parameter in annotated.find_all(vexp.UserParameter)
    )


def test_user_limits_preserve_comments_and_statement_boundaries() -> None:
    expression = assert_roundtrip(
        "/* lead */ CREATE USER analyst GRACEPERIOD '1 hour', "
        "MAXCONNECTIONS 2 ON DATABASE /* tail */"
    )
    assert _strict(expression).count("lead") == 1
    assert _strict(expression).count("tail") == 1
    statements = parse(
        "CREATE USER analyst MEMORYCAP '1G'; "
        "ALTER USER analyst SECURITY_ALGORITHM 'MD5'; "
        "DROP USER analyst",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateUser,
        vexp.AlterUser,
        vexp.DropUsers,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER analyst GRACEPERIOD",
        "CREATE USER analyst GRACEPERIOD DEFAULT",
        "CREATE USER analyst GRACEPERIOD '21 days'",
        "CREATE USER analyst GRACEPERIOD '-1 day'",
        "CREATE USER analyst GRACEPERIOD '1.5 days'",
        "CREATE USER analyst IDLESESSIONTIMEOUT '366 days'",
        "ALTER USER analyst RUNTIMECAP '1 year 1 microsecond'",
        "ALTER USER analyst RUNTIMECAP '24:60:00'",
        "ALTER USER analyst RUNTIMECAP '999999999999999999999 days'",
        "CREATE USER analyst MAXCONNECTIONS",
        "CREATE USER analyst MAXCONNECTIONS -1 ON NODE",
        "CREATE USER analyst MAXCONNECTIONS +1 ON NODE",
        "CREATE USER analyst MAXCONNECTIONS 1",
        "CREATE USER analyst MAXCONNECTIONS 1 ON",
        "CREATE USER analyst MAXCONNECTIONS 1 ON CLUSTER",
        "CREATE USER analyst MAXCONNECTIONS NONE ON NODE",
        "CREATE USER analyst MEMORYCAP 10G",
        "CREATE USER analyst MEMORYCAP '101%'",
        "CREATE USER analyst MEMORYCAP '-1G'",
        "CREATE USER analyst MEMORYCAP '1.5G'",
        "CREATE USER analyst TEMPSPACECAP ''",
        "CREATE USER analyst SECURITY_ALGORITHM 'SHA512'",
        "ALTER USER analyst SECURITY_ALGORITHM SHA512",
        "ALTER USER analyst SECURITY_ALGORITHM 'SHA-512'",
        "ALTER USER analyst SECURITY_ALGORITHM 'BCRYPT'",
        "ALTER USER analyst MEMORYCAP '1G', MEMORYCAP NONE",
        "ALTER USER analyst MAXCONNECTIONS 1 ON NODE, MAXCONNECTIONS NONE",
        "ALTER USER analyst SECURITY_ALGORITHM 'MD5', SECURITY_ALGORITHM 'NONE'",
        "ALTER USER analyst GRACEPERIOD '1 day' GRACEPERIOD NONE",
    ],
)
@pytest.mark.parametrize(
    "error_level", [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]
)
def test_invalid_user_limits_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'CREATE USER analyst "GRACEPERIOD" NONE',
        "CREATE USER analyst GRACEPERİOD NONE",
        'CREATE USER analyst MAXCONNECTIONS 1 "ON" NODE',
        'CREATE USER analyst MAXCONNECTIONS 1 ON "NODE"',
        "ALTER USER analyst \"SECURITY_ALGORITHM\" 'SHA512'",
    ],
)
def test_user_limit_keyword_provenance_is_exact(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_programmatic_user_limits_generate_exact_sql() -> None:
    create = vexp.CreateUser(
        this=_identifier("analyst"),
        kind="USER",
        parameters=[
            _limit_parameter("GRACEPERIOD", exp.Literal.string("2 hours")),
            _limit_parameter("MAXCONNECTIONS", exp.Literal.number("10"), scope="DATABASE"),
            _limit_parameter("MEMORYCAP", exp.Literal.string("25%")),
        ],
    )
    alter = vexp.AlterUser(
        this=_identifier("analyst"),
        kind="USER",
        actions=[
            _limit_parameter("TEMPSPACECAP", exp.var("NONE")),
            _limit_parameter("SECURITY_ALGORITHM", exp.Literal.string("SHA512")),
        ],
    )
    assert _strict(create) == (
        "CREATE USER analyst GRACEPERIOD '2 hours', MAXCONNECTIONS 10 ON DATABASE, MEMORYCAP '25%'"
    )
    assert _strict(alter) == ("ALTER USER analyst TEMPSPACECAP NONE, SECURITY_ALGORITHM 'SHA512'")
    for expression in (create, alter):
        assert parse_one(_strict(expression), read="vertica") == expression
        _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "name", "action"),
    [
        ("CREATE USER analyst", "analyst", None),
        ("CREATE USER analyst ACCOUNT LOCK", "analyst", "ACCOUNT LOCK"),
        ("CREATE USER analyst ACCOUNT UNLOCK", "analyst", "ACCOUNT UNLOCK"),
        ("CREATE USER analyst PASSWORD EXPIRE", "analyst", "PASSWORD EXPIRE"),
        ('CREATE USER "User Name" ACCOUNT LOCK', "User Name", "ACCOUNT LOCK"),
        ("CREATE USER grüppe", "grüppe", None),
        ("CREATE USER case", "case", None),
        ("CREATE USER end", "end", None),
        ("CREATE USER by", "by", None),
        ("CREATE USER group", "group", None),
        ("CREATE USER order", "order", None),
        ("CREATE USER limit", "limit", None),
    ],
)
def test_create_user_is_typed_and_stable(sql: str, name: str, action: str | None) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateUser)
    assert expression.kind == "USER"
    assert isinstance(expression.this, exp.Identifier)
    assert expression.this.name == name
    parsed_action = expression.args.get("action")
    if action is None:
        assert parsed_action is None
    else:
        assert isinstance(parsed_action, vexp.UserAction)
        assert isinstance(parsed_action.this, exp.Var)
        assert parsed_action.this.name == action
    assert not list(expression.find_all(exp.Literal))
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "action_type", "action"),
    [
        ("ALTER USER analyst RENAME TO analyst_new", exp.AlterRename, "analyst_new"),
        ('ALTER USER "User Name" RENAME TO "PASSWORD"', exp.AlterRename, "PASSWORD"),
        ("ALTER USER analyst RENAME TO identified", exp.AlterRename, "identified"),
        ("ALTER USER analyst RENAME TO totpsecret", exp.AlterRename, "totpsecret"),
        ("ALTER USER analyst ACCOUNT LOCK", vexp.UserAction, "ACCOUNT LOCK"),
        ("ALTER USER analyst ACCOUNT UNLOCK", vexp.UserAction, "ACCOUNT UNLOCK"),
        ("ALTER USER analyst PASSWORD EXPIRE", vexp.UserAction, "PASSWORD EXPIRE"),
    ],
)
def test_every_alter_user_action_is_structured(
    sql: str, action_type: type[exp.Expr], action: str
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.AlterUser)
    assert expression.kind == "USER"
    assert len(expression.actions) == 1
    parsed_action = expression.actions[0]
    assert isinstance(parsed_action, action_type)
    if isinstance(parsed_action, exp.AlterRename):
        assert parsed_action.name == action
    else:
        assert isinstance(parsed_action, vexp.UserAction)
        assert isinstance(parsed_action.this, exp.Var)
        assert parsed_action.this.name == action
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "names", "exists", "cascade"),
    [
        ("DROP USER analyst", ["analyst"], False, False),
        ("DROP USER IF EXISTS analyst", ["analyst"], True, False),
        ("DROP USER analyst, loader", ["analyst", "loader"], False, False),
        (
            'DROP USER IF EXISTS analyst, "User Name", grüppe CASCADE',
            ["analyst", "User Name", "grüppe"],
            True,
            True,
        ),
        (
            "DROP USER account, password, expire, identified, by",
            ["account", "password", "expire", "identified", "by"],
            False,
            False,
        ),
    ],
)
def test_drop_users_is_typed_ordered_and_stable(
    sql: str, names: list[str], exists: bool, cascade: bool
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.DropUsers)
    assert expression.kind == "USER"
    assert expression.args.get("exists") is exists
    assert expression.args.get("cascade") is cascade
    targets = [expression.this, *expression.expressions]
    assert [target.name for target in targets] == names
    assert all(isinstance(target, exp.Identifier) for target in targets)
    _assert_parent_links(expression)


def test_programmatic_user_lifecycle_generates_exact_sql() -> None:
    create = vexp.CreateUser(
        this=_identifier("analyst"), kind="USER", action=_action("ACCOUNT LOCK")
    )
    alter = vexp.AlterUser(
        this=_identifier("analyst"),
        kind="USER",
        actions=[exp.AlterRename(this=_identifier("analyst_new"))],
    )
    drop = vexp.DropUsers(
        this=_identifier("analyst_new"),
        expressions=[_identifier("loader")],
        kind="USER",
        exists=True,
        cascade=True,
    )

    assert _strict(create) == "CREATE USER analyst ACCOUNT LOCK"
    assert _strict(alter) == "ALTER USER analyst RENAME TO analyst_new"
    assert _strict(drop) == "DROP USER IF EXISTS analyst_new, loader CASCADE"
    for expression in (create, alter, drop):
        assert parse_one(_strict(expression), read="vertica") == expression
        _assert_parent_links(expression)


def test_programmatic_ordered_user_parameters_generate_exact_sql() -> None:
    create = vexp.CreateUser(
        this=_identifier("analyst"),
        kind="USER",
        parameters=[
            _parameter("PROFILE", "DEFAULT"),
            _parameter("RESOURCE POOL", "general"),
            _parameter("RESOURCE POOL", "etl", subcluster="sc"),
            _action("ACCOUNT LOCK"),
        ],
    )
    alter = vexp.AlterUser(
        this=_identifier("analyst"),
        kind="USER",
        actions=[
            _parameter("PROFILE", "security"),
            _parameter("RESOURCE POOL", "etl", subcluster="sc"),
            _action("PASSWORD EXPIRE"),
        ],
    )
    assert _strict(create) == (
        "CREATE USER analyst PROFILE DEFAULT, RESOURCE POOL general, "
        "RESOURCE POOL etl FOR SUBCLUSTER sc, ACCOUNT LOCK"
    )
    assert _strict(alter) == (
        "ALTER USER analyst PROFILE security, RESOURCE POOL etl FOR SUBCLUSTER sc, PASSWORD EXPIRE"
    )
    for expression in (create, alter):
        assert parse_one(_strict(expression), read="vertica") == expression
        assert exp.Expr.load(expression.dump()) == expression
        _assert_parent_links(expression)


def test_declared_false_statement_defaults_are_harmless() -> None:
    create = vexp.CreateUser(this=_identifier("analyst"), kind="USER", replace=False)
    alter = vexp.AlterUser(
        this=_identifier("analyst"),
        kind="USER",
        actions=[_action("ACCOUNT LOCK")],
        only=False,
    )
    drop = vexp.DropUsers(this=_identifier("analyst"), kind="USER", restrict=False, cascade=False)
    assert [_strict(expression) for expression in (create, alter, drop)] == [
        "CREATE USER analyst",
        "ALTER USER analyst ACCOUNT LOCK",
        "DROP USER analyst",
    ]


def test_copy_transform_serialization_optimizer_types_and_multi_statement_are_lossless() -> None:
    expression = parse_one("ALTER USER analyst RENAME TO analyst_new", read="vertica")
    copied = expression.copy()
    assert copied == expression
    assert copied is not expression
    _assert_parent_links(copied)

    transformed = copied.transform(
        lambda node: (
            _identifier("loader")
            if isinstance(node, exp.Identifier) and node.name == "analyst_new"
            else node
        )
    )
    assert _strict(transformed) == "ALTER USER analyst RENAME TO loader"

    restored = exp.Expr.load(expression.dump())
    assert restored == expression
    assert isinstance(restored, vexp.AlterUser)
    _assert_parent_links(restored)

    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterUser)
    assert _strict(optimized) == 'ALTER USER "analyst" RENAME TO "analyst_new"'
    _assert_parent_links(optimized)

    annotated = annotate_types(
        parse_one("CREATE USER analyst PASSWORD EXPIRE", read="vertica"),
        dialect="vertica",
    )
    action = annotated.find(vexp.UserAction)
    assert action is not None
    assert action.type == exp.DType.UNKNOWN.into_expr()
    assert _strict(annotated) == "CREATE USER analyst PASSWORD EXPIRE"

    statements = parse(
        "CREATE USER analyst ACCOUNT LOCK; "
        "ALTER USER analyst PASSWORD EXPIRE; "
        "CREATE USER loader PROFILE security, RESOURCE POOL general; "
        "ALTER USER loader RESOURCE POOL etl FOR SUBCLUSTER sc; "
        "DROP USER IF EXISTS analyst CASCADE",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateUser,
        vexp.AlterUser,
        vexp.CreateUser,
        vexp.AlterUser,
        vexp.DropUsers,
    ]


def test_user_assignment_copy_transform_optimizer_and_types_are_lossless() -> None:
    expression = parse_one(
        "ALTER USER analyst PROFILE security, RESOURCE POOL etl FOR SUBCLUSTER sc",
        read="vertica",
    )
    copied = expression.copy()
    assert copied == expression
    transformed = copied.transform(
        lambda node: (
            _identifier("batch")
            if isinstance(node, exp.Identifier) and node.name == "etl"
            else node
        )
    )
    assert _strict(transformed) == (
        "ALTER USER analyst PROFILE security, RESOURCE POOL batch FOR SUBCLUSTER sc"
    )
    optimized = optimize(expression, dialect="vertica")
    assert _strict(optimized) == (
        'ALTER USER "analyst" PROFILE "security", RESOURCE POOL "etl" FOR SUBCLUSTER "sc"'
    )
    annotated = annotate_types(expression, dialect="vertica")
    assert all(
        parameter.type == exp.DType.UNKNOWN.into_expr()
        for parameter in annotated.find_all(vexp.UserParameter)
    )
    _assert_parent_links(optimized)
    _assert_parent_links(annotated)


@pytest.mark.parametrize(
    "sql",
    [
        "/* lead */ CREATE USER analyst ACCOUNT LOCK /* tail */",
        ("/* lead */ CREATE USER analyst PROFILE security, RESOURCE POOL general /* tail */"),
    ],
)
def test_comments_survive_structured_roundtrip(sql: str) -> None:
    expression = assert_roundtrip(sql)
    generated = _strict(expression)
    assert generated.count("lead") == 1
    assert generated.count("tail") == 1


def test_user_identifier_utf8_byte_limit_and_unicode_rules() -> None:
    exact_ascii = "a" * 128
    exact_multibyte = f"a{'é' * 63}b"
    assert len(exact_multibyte.encode()) == 128
    for name in (exact_ascii, exact_multibyte):
        assert_roundtrip(f"CREATE USER {name}")
        assert (
            _strict(vexp.CreateUser(this=_identifier(name), kind="USER")) == f"CREATE USER {name}"
        )

    for name in ("a" * 129, f"a{'é' * 64}"):
        with pytest.raises(ParseError):
            parse_one(f"CREATE USER {name}", read="vertica")
        with pytest.raises(UnsupportedError):
            _strict(vexp.CreateUser(this=_identifier(name), kind="USER"))

    with pytest.raises(ParseError):
        parse_one("CREATE USER βeta", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE USER a\u0661", read="vertica")
    assert_roundtrip('CREATE USER "βeta"')

    exact_quoted = "β" * 64
    assert len(exact_quoted.encode()) == 128
    assert_roundtrip(f'CREATE USER "{exact_quoted}"')
    with pytest.raises(ParseError):
        parse_one(f'CREATE USER "{exact_quoted}β"', read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        f"CREATE USER {'a' * 129}",
        f"ALTER USER {'a' * 129} ACCOUNT LOCK",
        f"ALTER USER analyst RENAME TO {'a' * 129}",
        f"DROP USER {'a' * 129}",
        f"DROP USER analyst, {'a' * 129}",
    ],
)
def test_every_user_name_position_enforces_the_utf8_byte_limit(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_user_assignment_identifier_contract_applies_to_every_name_position() -> None:
    exact = "a" * 128
    for sql in (
        f"CREATE USER analyst PROFILE {exact}",
        f"CREATE USER analyst RESOURCE POOL {exact}",
        f"CREATE USER analyst SEARCH_PATH {exact}",
        f"ALTER USER analyst RESOURCE POOL pool FOR SUBCLUSTER {exact}",
        f"ALTER USER analyst SEARCH_PATH namespace.{exact}",
        f"ALTER USER analyst DEFAULT ROLE {exact}",
        'CREATE USER analyst PROFILE "βeta"',
        'CREATE USER analyst SEARCH_PATH "βeta"',
        'ALTER USER analyst RESOURCE POOL "etl pool" FOR SUBCLUSTER "βeta"',
        'ALTER USER analyst DEFAULT ROLE "βeta"',
    ):
        assert_roundtrip(sql)

    too_long = "a" * 129
    for sql in (
        f"CREATE USER analyst PROFILE {too_long}",
        f"CREATE USER analyst RESOURCE POOL {too_long}",
        f"CREATE USER analyst SEARCH_PATH {too_long}",
        f"ALTER USER analyst RESOURCE POOL pool FOR SUBCLUSTER {too_long}",
        f"ALTER USER analyst SEARCH_PATH namespace.{too_long}",
        f"ALTER USER analyst DEFAULT ROLE {too_long}",
    ):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica")


def test_lone_surrogate_identifier_fails_cleanly() -> None:
    surrogate = chr(0xD800)
    with pytest.raises(ParseError):
        parse_one(f'CREATE USER "{surrogate}"', read="vertica")
    with pytest.raises(UnsupportedError):
        _strict(vexp.CreateUser(this=_identifier(surrogate, quoted=True), kind="USER"))


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER",
        "CREATE USER app.analyst",
        "CREATE USER ''",
        'CREATE USER ""',
        "CREATE USER 1",
        "CREATE USER NULL",
        "CREATE USER TRUE",
        "CREATE USER DEFAULT",
        "CREATE USER SELECT",
        "CREATE USER analyst ACCOUNT",
        "CREATE USER analyst ACCOUNT ENABLE",
        "CREATE USER analyst ACCOUNT LOCK PASSWORD EXPIRE",
        "CREATE USER analyst PASSWORD",
        "CREATE USER analyst PASSWORD LOCK",
        "CREATE USER analyst PROFILE",
        "CREATE USER analyst PROFILE security PROFILE other",
        "CREATE USER analyst PROFILE security, PROFILE other",
        "CREATE USER analyst RESOURCE POOL",
        "CREATE USER analyst RESOURCE POOL general FOR etl",
        "CREATE USER analyst RESOURCE POOL general, RESOURCE POOL other",
        "CREATE USER analyst ACCOUNT LOCK, ACCOUNT UNLOCK",
        "CREATE USER analyst SET PARAMETER x = 1",
        "CREATE USER IF NOT EXISTS analyst",
        "ALTER USER",
        "ALTER USER app.analyst ACCOUNT LOCK",
        "ALTER USER analyst",
        "ALTER USER analyst RENAME",
        "ALTER USER analyst RENAME analyst_new",
        "ALTER USER analyst RENAME TO",
        "ALTER USER analyst ACCOUNT",
        "ALTER USER analyst ACCOUNT ENABLE",
        "ALTER USER analyst ACCOUNT LOCK PASSWORD EXPIRE",
        "ALTER USER analyst PASSWORD",
        "ALTER USER analyst PASSWORD LOCK",
        "ALTER USER analyst PROFILE",
        "ALTER USER analyst PROFILE security PROFILE other",
        "ALTER USER analyst PROFILE security, PROFILE other",
        "ALTER USER analyst RESOURCE POOL",
        "ALTER USER analyst RESOURCE POOL general FOR etl",
        "ALTER USER analyst RESOURCE POOL general, RESOURCE POOL other",
        "ALTER USER analyst ACCOUNT LOCK, ACCOUNT UNLOCK",
        "ALTER USER analyst RENAME TO renamed, PROFILE security",
        "ALTER USER analyst SET PARAMETER x = 1",
        "ALTER USER analyst CLEAR PARAMETER x",
        "DROP USER",
        "DROP USER app.analyst",
        "DROP USER analyst,",
        "DROP USER analyst CASCADE loader",
        "DROP USER analyst RESTRICT",
        "DROP USER analyst, loader RESTRICT",
        "DROP IF EXISTS USER analyst",
        "DROP USER analyst IF EXISTS",
    ],
)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_recognized_invalid_or_out_of_scope_user_syntax_fails_closed(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'CREATE "USER" analyst',
        "CREATE 'USER' analyst",
        "CREATE U\u017fer analyst",
        'ALTER "USER" analyst ACCOUNT LOCK',
        "ALTER 'USER' analyst ACCOUNT LOCK",
        "ALTER U\u017fer analyst ACCOUNT LOCK",
        'DROP "USER" analyst',
        "DROP 'USER' analyst",
        "DROP U\u017fer analyst",
        'CREATE USER analyst "ACCOUNT" LOCK',
        "CREATE USER analyst 'ACCOUNT' LOCK",
        'CREATE USER analyst ACCOUNT "LOCK"',
        "CREATE USER analyst ACCOUNT 'LOCK'",
        "CREATE USER analyst PA\u017f\u017fWORD EXPIRE",
        'CREATE USER analyst PASSWORD "EXPIRE"',
        'CREATE USER analyst "PROFILE" security',
        "CREATE USER analyst PRO\u017fILE security",
        'CREATE USER analyst "RESOURCE" POOL general',
        'CREATE USER analyst RESOURCE "POOL" general',
        'CREATE USER analyst RESOURCE POOL general "FOR" SUBCLUSTER sc',
        'CREATE USER analyst RESOURCE POOL general FOR "SUBCLUSTER" sc',
        'ALTER USER analyst "RENAME" TO analyst_new',
        'ALTER USER analyst RENAME "TO" analyst_new',
        "ALTER USER analyst PA\u017f\u017fWORD EXPIRE",
        'ALTER USER analyst ACCOUNT "UNLOCK"',
        'ALTER USER analyst "PROFILE" security',
        'ALTER USER analyst RESOURCE "POOL" general',
        'DROP USER "analyst" "CASCADE"',
        "DROP USER analyst 'CASCADE'",
        'DROP USER "IF" EXISTS analyst',
        'DROP USER IF "EXISTS" analyst',
    ],
)
def test_user_object_and_action_keyword_provenance_is_exact(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TEMP USER analyst",
        "CREATE TEMPORARY USER analyst",
        "CREATE OR REPLACE USER analyst",
        "CREATE OR ALTER USER analyst",
        "CREATE OR REFRESH USER analyst",
        "CREATE IF NOT EXISTS USER analyst",
        "CREATE UNIQUE USER analyst",
        "CREATE CLUSTERED COLUMNSTORE USER analyst",
        "CREATE NONCLUSTERED COLUMNSTORE USER analyst",
        "CREATE FLEX USER analyst",
        "ALTER IF EXISTS USER analyst ACCOUNT LOCK",
        "ALTER ONLY USER analyst ACCOUNT LOCK",
        "ALTER MATERIALIZED USER analyst ACCOUNT LOCK",
        "DROP IF EXISTS USER analyst",
        "DROP TEMPORARY USER analyst",
        "DROP MATERIALIZED USER analyst",
        "DROP CASCADE USER analyst",
    ],
)
def test_unsupported_user_object_modifiers_fail_closed(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE AUTHENTICATION user METHOD 'trust' LOCAL",
        "ALTER AUTHENTICATION user ENABLE",
        "DROP AUTHENTICATION user",
        "CREATE PROFILE user LIMIT PASSWORD_MIN_LENGTH 8",
        "ALTER PROFILE user LIMIT PASSWORD_MIN_LENGTH 9",
        "DROP PROFILE user",
        "CREATE RESOURCE POOL user",
        "ALTER RESOURCE POOL user MAXMEMORYSIZE '1G'",
        "DROP RESOURCE POOL user",
        "CREATE TABLE user (id INT)",
        "ALTER TABLE user ADD COLUMN value INT",
        "DROP TABLE user",
        "CREATE ROLE user",
        "ALTER ROLE user RENAME TO user_new",
        "DROP ROLE user",
    ],
)
def test_user_dispatch_does_not_collide_with_other_object_names(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, (vexp.CreateUser, vexp.AlterUser, vexp.DropUsers))


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "CREATE TEMP USER analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "CREATE \"USER\" analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "CREATE U\u017fer analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "CREATE USER analyst PROFILE E'S3CR3T_DO_NOT_LEAK'",
        "CREATE USER analyst PROFILE U&'S3CR3T_DO_NOT_LEAK'",
        "CREATE USER analyst PROFILE N'S3CR3T_DO_NOT_LEAK'",
        "CREATE USER analyst PROFILE $$S3CR3T_DO_NOT_LEAK$$",
        "ALTER USER analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst PASSWORD 'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst SET PASSWORD = 'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst TOTPSECRET 'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst RENAME TO E'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst ACCOUNT LOCK PROFILE 'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst ACCOUNT LOCK PROFILE E'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst ACCOUNT LOCK PROFILE U&'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst ACCOUNT LOCK PROFILE N'S3CR3T_DO_NOT_LEAK'",
        "ALTER USER analyst ACCOUNT LOCK PROFILE $$S3CR3T_DO_NOT_LEAK$$",
        "CREATE USER analyst MEMORYCAP '1G', IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "CREATE USER analyst TEMPSPACECAP E'S3CR3T_DO_NOT_LEAK'",
        ("ALTER USER analyst RUNTIMECAP '1 hour', IDENTIFIED BY 'hash' SALT 'S3CR3T_DO_NOT_LEAK'"),
        ("ALTER USER analyst SECURITY_ALGORITHM 'SHA512', REPLACE 'S3CR3T_DO_NOT_LEAK'"),
        "CREATE \"USER\" analyst PROFILE E'S3CR3T_DO_NOT_LEAK'",
        "DROP USER analyst IDENTIFIED BY 'S3CR3T_DO_NOT_LEAK'",
        "DROP USER analyst PROFILE E'S3CR3T_DO_NOT_LEAK'",
        "DROP USER analyst PROFILE U&'S3CR3T_DO_NOT_LEAK'",
        "DROP USER analyst PROFILE N'S3CR3T_DO_NOT_LEAK'",
        "DROP USER analyst PROFILE $$S3CR3T_DO_NOT_LEAK$$",
        "DROP USER analyst, E'S3CR3T_DO_NOT_LEAK'",
    ],
)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_tokenizable_secret_bearing_user_input_is_sanitized_at_every_error_level(
    sql: str, error_level: ErrorLevel, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.clear()
    with caplog.at_level(logging.DEBUG), pytest.raises(ParseError) as caught:
        parse_one(sql, read="vertica", error_level=error_level)

    observed = " ".join(
        (
            str(caught.value),
            repr(caught.value),
            repr(caught.value.errors),
            caplog.text,
        )
    )
    assert "S3CR3T_DO_NOT_LEAK" not in observed
    assert str(caught.value) == "Unsupported secret-bearing USER clause"


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER analyst ACCOUNT LOCK",
        "CREATE USER analyst PROFILE security, RESOURCE POOL general",
        "ALTER USER analyst PASSWORD EXPIRE",
        "ALTER USER analyst RESOURCE POOL etl FOR SUBCLUSTER sc",
        "ALTER USER analyst GRACEPERIOD '1 hour', MAXCONNECTIONS 10 ON NODE",
        "DROP USER IF EXISTS analyst, loader CASCADE",
    ],
)
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_user_statement_roots_fail_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_user_action_leaf_fails_atomically_in_foreign_dialects() -> None:
    for leaf in (
        _action("ACCOUNT LOCK"),
        _parameter("PROFILE", "security"),
        _limit_parameter("GRACEPERIOD", exp.Literal.string("1 hour")),
        _limit_parameter("MAXCONNECTIONS", exp.Literal.number("2"), scope="NODE"),
    ):
        for dialect in ("postgres", "duckdb", "mysql", "sqlite"):
            with pytest.raises((UnsupportedError, ValueError)):
                leaf.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateUser(this=_identifier("analyst"), kind="TABLE"),
        vexp.CreateUser(this=_identifier("analyst"), kind=exp.var("USER")),
        vexp.CreateUser(this=_identifier("analyst"), kind=[]),
        vexp.CreateUser(kind="USER"),
        vexp.CreateUser(this=[_identifier("analyst")], kind="USER"),
        vexp.CreateUser(this=exp.to_table("app.analyst"), kind="USER"),
        vexp.CreateUser(this=_identifier(""), kind="USER"),
        vexp.CreateUser(this=_identifier("app.analyst"), kind="USER"),
        vexp.CreateUser(this=_identifier("x; DROP TABLE y"), kind="USER"),
        vexp.CreateUser(this=exp.Identifier(this="analyst", quoted="yes"), kind="USER"),
        vexp.CreateUser(this=_identifier("SELECT"), kind="USER"),
        vexp.CreateUser(this=_identifier("a" * 129), kind="USER"),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", replace=True),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", replace=[]),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", exists={}),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", properties=[]),
        vexp.CreateUser(this=_set_arg(_identifier("analyst"), "bogus", []), kind="USER"),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", action=exp.var("LOCK")),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", action=[_action("ACCOUNT LOCK")]),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", action=_action("LOCK")),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", parameters=[]),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", parameters={}),
        vexp.CreateUser(
            this=_identifier("analyst"),
            kind="USER",
            action=_action("ACCOUNT LOCK"),
            parameters=[_parameter("PROFILE", "security")],
        ),
        vexp.CreateUser(this=_identifier("analyst"), kind="USER", parameters=[exp.var("PROFILE")]),
        vexp.CreateUser(
            this=_identifier("analyst"),
            kind="USER",
            parameters=[_parameter("PROFILE", "security"), _parameter("PROFILE", "other")],
        ),
        vexp.CreateUser(
            this=_identifier("analyst"),
            kind="USER",
            parameters=[
                _parameter("RESOURCE POOL", "etl", subcluster="sc"),
                _parameter("RESOURCE POOL", "other", subcluster="other_sc"),
            ],
        ),
        vexp.AlterUser(this=_identifier("analyst"), kind="TABLE", actions=[]),
        vexp.AlterUser(this=_identifier("analyst"), kind=exp.var("USER"), actions=[]),
        vexp.AlterUser(this={}, kind="USER", actions=[_action("ACCOUNT LOCK")]),
        vexp.AlterUser(this=_identifier("analyst"), kind="USER", actions=[]),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[_action("ACCOUNT LOCK"), _action("ACCOUNT UNLOCK")],
        ),
        vexp.AlterUser(this=_identifier("analyst"), kind="USER", actions=_action("ACCOUNT LOCK")),
        vexp.AlterUser(this=_identifier("analyst"), kind="USER", actions={}),
        vexp.AlterUser(this=_identifier("analyst"), kind="USER", actions=[exp.var("LOCK")]),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[
                exp.AlterRename(this=_identifier("renamed")),
                _parameter("PROFILE", "security"),
            ],
        ),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[_parameter("RESOURCE POOL", "one"), _parameter("RESOURCE POOL", "two")],
        ),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[_action("ACCOUNT LOCK")],
            only=[],
        ),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[exp.AlterRename(this=exp.to_table("app.new_name"))],
        ),
        vexp.AlterUser(
            this=_identifier("analyst"),
            kind="USER",
            actions=[_set_arg(exp.AlterRename(this=_identifier("new_name")), "bogus", [])],
        ),
        vexp.DropUsers(kind="USER"),
        vexp.DropUsers(this=_identifier("analyst"), kind="TABLE"),
        vexp.DropUsers(this=_identifier("analyst"), kind=exp.var("USER")),
        vexp.DropUsers(this=[_identifier("analyst")], kind="USER"),
        vexp.DropUsers(this=_identifier("analyst"), expressions=_identifier("loader"), kind="USER"),
        vexp.DropUsers(this=_identifier("analyst"), expressions={}, kind="USER"),
        vexp.DropUsers(this=_identifier("analyst"), kind="USER", exists="yes"),
        vexp.DropUsers(this=_identifier("analyst"), kind="USER", cascade="yes"),
        vexp.DropUsers(this=_identifier("analyst"), kind="USER", purge=True),
        vexp.DropUsers(this=_identifier("analyst"), kind="USER", restrict=[]),
        vexp.DropUsers(this=_identifier("analyst"), kind="USER", temporary={}),
        vexp.UserAction(this=exp.Var(this="")),
        _action("LOCK"),
        _action("PA\u017f\u017fWORD EXPIRE"),
        vexp.UserAction(this=_identifier("ACCOUNT LOCK")),
        vexp.UserAction(this=[exp.var("ACCOUNT LOCK")]),
        _set_arg(_action("ACCOUNT LOCK"), "bogus", _identifier("x")),
        _set_arg(_action("ACCOUNT LOCK"), "bogus", []),
        _set_arg(_action("ACCOUNT LOCK"), "bogus", False),
        _set_arg(_action("ACCOUNT LOCK"), "this", exp.Var(this="ACCOUNT LOCK", bogus=True)),
        _set_arg(_action("ACCOUNT LOCK"), "this", exp.Var(this="ACCOUNT LOCK", bogus={})),
        vexp.UserParameter(this=exp.var("PROFILE")),
        vexp.UserParameter(this=exp.var("UNKNOWN"), expression=_identifier("value")),
        vexp.UserParameter(this=exp.var("PRO\u017fILE"), expression=_identifier("value")),
        vexp.UserParameter(this=_identifier("PROFILE"), expression=_identifier("value")),
        vexp.UserParameter(this=exp.var("PROFILE"), expression=exp.var("DEFAULT")),
        _parameter("PROFILE", "DEFAULT", quoted=True),
        _parameter("PROFILE", "security", subcluster="sc"),
        vexp.UserParameter(this=exp.var("RESOURCE POOL"), expression=exp.to_table("app.pool")),
        vexp.UserParameter(
            this=exp.var("RESOURCE POOL"), expression=_identifier("pool"), subcluster=exp.var("sc")
        ),
        _set_arg(_parameter("PROFILE", "security"), "bogus", True),
        _limit_parameter("GRACEPERIOD", exp.Literal.number("1")),
        _limit_parameter("GRACEPERIOD", exp.Literal.string("21 days")),
        _limit_parameter("GRACEPERIOD", exp.var("DEFAULT")),
        _limit_parameter("GRACEPERIOD", exp.Literal.string("1 day"), scope="NODE"),
        _limit_parameter("MAXCONNECTIONS", exp.Literal.number("1")),
        _limit_parameter("MAXCONNECTIONS", exp.Literal.number("-1"), scope="NODE"),
        _limit_parameter("MAXCONNECTIONS", exp.Literal.string("1"), scope="NODE"),
        _limit_parameter("MAXCONNECTIONS", exp.Literal.number("1"), scope="CLUSTER"),
        _limit_parameter("MAXCONNECTIONS", exp.var("NONE"), scope="NODE"),
        _limit_parameter("MEMORYCAP", exp.Literal.string("101%")),
        _limit_parameter("MEMORYCAP", exp.Literal.string("1g")),
        _limit_parameter("TEMPSPACECAP", exp.Literal.number("10")),
        _limit_parameter("SECURITY_ALGORITHM", exp.Literal.string("sha512")),
        _limit_parameter("SECURITY_ALGORITHM", exp.var("NONE")),
        vexp.UserParameter(
            this=exp.var("MEMORYCAP"),
            expression=exp.Literal.string("1G"),
            subcluster=_identifier("sc"),
        ),
        vexp.CreateUser(
            this=_identifier("analyst"),
            kind="USER",
            parameters=[_limit_parameter("SECURITY_ALGORITHM", exp.Literal.string("SHA512"))],
        ),
    ],
)
def test_malformed_programmatic_user_asts_fail_atomically(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "name",
    [
        "FROM",
        "WHERE",
        "CREATE",
        "ALTER",
        "DROP",
        "GRANT",
        "REVOKE",
        "JOIN",
        "ON",
        "AND",
        "OR",
        "NOT",
        "WHEN",
        "THEN",
        "ELSE",
        "AS",
        "HAVING",
        "UNION",
    ],
)
def test_programmatic_unquoted_user_names_match_parser_keyword_domain(name: str) -> None:
    with pytest.raises(ParseError):
        parse_one(f"CREATE USER {name}", read="vertica")
    with pytest.raises(UnsupportedError):
        _strict(vexp.CreateUser(this=_identifier(name), kind="USER"))
    quoted = vexp.CreateUser(this=_identifier(name, quoted=True), kind="USER")
    assert _strict(quoted) == f'CREATE USER "{name}"'


@pytest.mark.parametrize(
    ("sql", "default", "schemas"),
    [
        ("CREATE USER analyst SEARCH_PATH DEFAULT", True, []),
        ("ALTER USER analyst SEARCH_PATH public", False, ["public"]),
        (
            'CREATE USER analyst SEARCH_PATH "$user", public, analytics',
            False,
            ['"$user"', "public", "analytics"],
        ),
        (
            'ALTER USER analyst SEARCH_PATH tenant.reporting, "Case Schema"',
            False,
            ["tenant.reporting", '"Case Schema"'],
        ),
    ],
)
def test_user_search_paths_are_typed_ordered_lists(
    sql: str, default: bool, schemas: list[str]
) -> None:
    expression = assert_roundtrip(sql)
    parameters = expression.args.get("parameters") or expression.args.get("actions")
    assert isinstance(parameters, list)
    parameter = parameters[0]
    assert isinstance(parameter, vexp.UserParameter)
    assert parameter.this.name == "SEARCH_PATH"
    search_path = parameter.expression
    assert isinstance(search_path, vexp.UserSearchPath)
    assert bool(search_path.args.get("default")) is default
    assert [schema.sql(dialect="vertica") for schema in search_path.expressions] == schemas
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "mode", "roles"),
    [
        ("ALTER USER analyst DEFAULT ROLE NONE", "NONE", []),
        ("ALTER USER analyst DEFAULT ROLE ALL", "ALL", []),
        ("ALTER USER analyst DEFAULT ROLE reporting", "ROLES", ["reporting"]),
        (
            'ALTER USER analyst DEFAULT ROLE reporting, "Case Role"',
            "ROLES",
            ["reporting", "Case Role"],
        ),
        (
            "ALTER USER analyst DEFAULT ROLE ALL EXCEPT restricted, auditors",
            "ALL EXCEPT",
            ["restricted", "auditors"],
        ),
    ],
)
def test_user_default_roles_are_typed_exclusive_lists(
    sql: str, mode: str, roles: list[str]
) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterUser)
    parameter = expression.actions[0]
    assert isinstance(parameter, vexp.UserParameter)
    default_roles = parameter.expression
    assert isinstance(default_roles, vexp.UserDefaultRoles)
    assert default_roles.args["mode"].name == mode
    assert [role.name for role in default_roles.expressions] == roles
    _assert_parent_links(expression)


def test_search_path_commas_remain_distinct_from_outer_parameter_commas() -> None:
    sql = (
        "ALTER USER analyst SEARCH_PATH tenant.reporting, public, PROFILE strict, "
        "MAXCONNECTIONS 4 ON NODE"
    )
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterUser)
    assert [parameter.this.name for parameter in expression.actions] == [
        "SEARCH_PATH",
        "PROFILE",
        "MAXCONNECTIONS",
    ]
    search_path = expression.actions[0].expression
    assert isinstance(search_path, vexp.UserSearchPath)
    assert [schema.sql(dialect="vertica") for schema in search_path.expressions] == [
        "tenant.reporting",
        "public",
    ]


def test_user_name_lists_serialize_transform_optimize_and_annotate() -> None:
    expression = parse_one(
        'ALTER USER analyst SEARCH_PATH tenant.reporting, "Case Schema", PROFILE strict',
        read="vertica",
    )
    assert exp.Expr.load(expression.dump()) == expression
    assert expression.copy() == expression
    transformed = expression.transform(
        lambda node: (
            _identifier("warehouse")
            if isinstance(node, exp.Identifier) and node.name == "reporting"
            else node
        )
    )
    assert "tenant.warehouse" in _strict(transformed)
    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.AlterUser)
    assert len(list(optimized.find_all(vexp.UserSearchPath))) == 1
    annotated = annotate_types(expression, dialect="vertica")
    assert isinstance(annotated.find(vexp.UserSearchPath), vexp.UserSearchPath)


def test_user_name_lists_preserve_comments_and_statement_boundaries() -> None:
    expression = assert_roundtrip(
        "/* lead */ CREATE USER analyst SEARCH_PATH tenant.reporting, public /* tail */"
    )
    assert _strict(expression).count("lead") == 1
    assert _strict(expression).count("tail") == 1
    statements = parse(
        "CREATE USER analyst SEARCH_PATH DEFAULT; "
        "ALTER USER analyst DEFAULT ROLE ALL EXCEPT restricted; "
        "DROP USER analyst",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateUser,
        vexp.AlterUser,
        vexp.DropUsers,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE USER analyst SEARCH_PATH",
        "CREATE USER analyst SEARCH_PATH DEFAULT public",
        "CREATE USER analyst SEARCH_PATH public,",
        "CREATE USER analyst SEARCH_PATH public,, analytics",
        "CREATE USER analyst SEARCH_PATH tenant.reporting.extra",
        "CREATE USER analyst SEARCH_PATH public, PUBLIC",
        "CREATE USER analyst SEARCH_PATH 'public'",
        "CREATE USER analyst SEARCH_PATH NULL",
        "CREATE USER analyst SEARCH_PATH DEFAULT, SEARCH_PATH public",
        "CREATE USER analyst DEFAULT ROLE reporting",
        "ALTER USER analyst DEFAULT ROLE",
        "ALTER USER analyst DEFAULT ROLE ALL EXCEPT",
        "ALTER USER analyst DEFAULT ROLE NONE, reporting",
        "ALTER USER analyst DEFAULT ROLE ALL, reporting",
        "ALTER USER analyst DEFAULT ROLE app.reporting",
        "ALTER USER analyst DEFAULT ROLE reporting, REPORTING",
        "ALTER USER analyst ACCOUNT LOCK, DEFAULT ROLE reporting",
        "ALTER USER analyst DEFAULT ROLE reporting ACCOUNT LOCK",
        "ALTER USER analyst DEFAULT ROLE reporting, ACCOUNT LOCK",
    ],
)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_invalid_user_search_paths_and_default_roles_fail_closed(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        'CREATE USER analyst "SEARCH_PATH" public',
        'ALTER USER analyst "DEFAULT" ROLE reporting',
        'ALTER USER analyst DEFAULT "ROLE" reporting',
        "ALTER USER analyst DEFAULT RO" + chr(0x131) + "E reporting",
        'ALTER USER analyst DEFAULT ROLE "ALL"',
        'ALTER USER analyst DEFAULT ROLE "NONE"',
    ],
)
def test_user_list_keyword_provenance_and_identifier_collisions(sql: str) -> None:
    if sql.endswith('"ALL"') or sql.endswith('"NONE"'):
        expression = assert_roundtrip(sql)
        roles = expression.actions[0].expression
        assert isinstance(roles, vexp.UserDefaultRoles)
        assert roles.args["mode"].name == "ROLES"
    else:
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica")


def _search_path_parameter(*schemas: exp.Expr, default: object = False) -> vexp.UserParameter:
    return vexp.UserParameter(
        this=exp.var("SEARCH_PATH"),
        expression=vexp.UserSearchPath(expressions=list(schemas) or None, default=default),
    )


def _default_roles_parameter(mode: object, *roles: exp.Expr) -> vexp.UserParameter:
    return vexp.UserParameter(
        this=exp.var("DEFAULT ROLE"),
        expression=vexp.UserDefaultRoles(
            expressions=list(roles) or None,
            mode=exp.var(mode) if isinstance(mode, str) else mode,
        ),
    )


@pytest.mark.parametrize(
    "parameter",
    [
        _search_path_parameter(),
        _search_path_parameter(_identifier("public"), default=True),
        _search_path_parameter(_identifier("public"), default="yes"),
        _search_path_parameter(exp.Literal.string("public")),
        _search_path_parameter(exp.to_table("db.namespace.schema")),
        _search_path_parameter(_identifier("public"), _identifier("PUBLIC")),
        _default_roles_parameter("NONE", _identifier("reporting")),
        _default_roles_parameter("ROLES"),
        _default_roles_parameter("ALL EXCEPT"),
        _default_roles_parameter("UNKNOWN", _identifier("reporting")),
        _default_roles_parameter("ROLES", exp.to_table("app.reporting")),
        _default_roles_parameter("ROLES", _identifier("reporting"), _identifier("REPORTING")),
    ],
)
def test_malformed_programmatic_user_name_lists_fail_atomically(
    parameter: vexp.UserParameter,
) -> None:
    root = vexp.AlterUser(this=_identifier("analyst"), kind="USER", actions=[parameter])
    with pytest.raises(UnsupportedError):
        _strict(root)


def test_programmatic_default_role_is_alter_only_and_isolated() -> None:
    default_role = _default_roles_parameter("ROLES", _identifier("reporting"))
    with pytest.raises(UnsupportedError):
        _strict(
            vexp.CreateUser(this=_identifier("analyst"), kind="USER", parameters=[default_role])
        )
    with pytest.raises(UnsupportedError):
        _strict(
            vexp.AlterUser(
                this=_identifier("analyst"),
                kind="USER",
                actions=[default_role, _action("ACCOUNT LOCK")],
            )
        )


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize(
    "expression",
    [
        vexp.UserSearchPath(expressions=[_identifier("public")], default=False),
        vexp.UserDefaultRoles(expressions=[_identifier("reporting")], mode=exp.var("ROLES")),
        parse_one("CREATE USER analyst SEARCH_PATH public", read="vertica"),
        parse_one("ALTER USER analyst DEFAULT ROLE ALL", read="vertica"),
    ],
)
def test_user_name_lists_fail_atomically_in_foreign_dialects(
    dialect: str, expression: exp.Expr
) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
