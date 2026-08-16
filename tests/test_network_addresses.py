"""Semantic Vertica NETWORK ADDRESS lifecycle regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str, quoted: bool = False) -> exp.Identifier:
    return exp.to_identifier(name, quoted=quoted)


def _port(value: str) -> exp.Literal:
    return exp.Literal(this=value, is_string=False)


def _spec(
    address: str = "10.20.110.21",
    *,
    node: str = "v_node0001",
    port: str | None = None,
    state: str | None = None,
) -> vexp.NetworkAddressSpec:
    return vexp.NetworkAddressSpec(
        this=exp.Literal.string(address),
        node=_identifier(node),
        port=_port(port) if port is not None else None,
        state=exp.var(state) if state is not None else None,
    )


def _action(
    action: str,
    *,
    address: str | None = None,
    port: str | None = None,
) -> vexp.NetworkAddressAction:
    return vexp.NetworkAddressAction(
        this=exp.var(action),
        expression=exp.Literal.string(address) if address is not None else None,
        port=_port(port) if port is not None else None,
    )


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize(
    ("sql", "name", "node", "address", "port", "state"),
    [
        (
            "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH '10.20.110.21'",
            "addr01",
            "v_node0001",
            "10.20.110.21",
            None,
            None,
        ),
        (
            "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH '10.20.110.21' PORT 5434",
            "addr01",
            "v_node0001",
            "10.20.110.21",
            "5434",
            None,
        ),
        (
            "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH '10.20.110.21' ENABLED",
            "addr01",
            "v_node0001",
            "10.20.110.21",
            None,
            "ENABLED",
        ),
        (
            "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH '10.20.110.21' PORT 0 DISABLED",
            "addr01",
            "v_node0001",
            "10.20.110.21",
            "0",
            "DISABLED",
        ),
        (
            "CREATE NETWORK ADDRESS node1_ipv6 ON v_node0001 WITH '2001:0DB8:7D5F:7433::'",
            "node1_ipv6",
            "v_node0001",
            "2001:0DB8:7D5F:7433::",
            None,
            None,
        ),
        (
            "CREATE NETWORK ADDRESS node1_nat ON v_node0001 WITH 'router.example.com' PORT 5435",
            "node1_nat",
            "v_node0001",
            "router.example.com",
            "5435",
            None,
        ),
        (
            'CREATE NETWORK ADDRESS "External Address" ON "Node One" WITH \'203.0.113.10\'',
            "External Address",
            "Node One",
            "203.0.113.10",
            None,
            None,
        ),
        (
            "CREATE NETWORK ADDRESS empty_host ON v_node0001 WITH ''",
            "empty_host",
            "v_node0001",
            "",
            None,
            None,
        ),
    ],
)
def test_create_network_address_is_typed_and_stable(
    sql: str,
    name: str,
    node: str,
    address: str,
    port: str | None,
    state: str | None,
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateNetworkAddress)
    assert expression.kind == "NETWORK ADDRESS"
    assert isinstance(expression.this, exp.Identifier)
    assert expression.this.name == name
    spec = expression.args.get("spec")
    assert isinstance(spec, vexp.NetworkAddressSpec)
    assert isinstance(spec.args.get("node"), exp.Identifier)
    assert spec.args["node"].name == node
    assert isinstance(spec.this, exp.Literal)
    assert spec.this.this == address
    parsed_port = spec.args.get("port")
    parsed_state = spec.args.get("state")
    assert (parsed_port.this if isinstance(parsed_port, exp.Literal) else None) == port
    assert (parsed_state.name if isinstance(parsed_state, exp.Var) else None) == state
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "action_type", "action", "address", "port"),
    [
        (
            "ALTER NETWORK ADDRESS addr01 RENAME TO addr_external",
            exp.AlterRename,
            "addr_external",
            None,
            None,
        ),
        (
            "ALTER NETWORK ADDRESS addr01 SET TO '192.168.1.200'",
            vexp.NetworkAddressAction,
            "SET",
            "192.168.1.200",
            None,
        ),
        (
            "ALTER NETWORK ADDRESS addr01 SET TO 'router.example.com' PORT 4000",
            vexp.NetworkAddressAction,
            "SET",
            "router.example.com",
            "4000",
        ),
        (
            "ALTER NETWORK ADDRESS addr01 ENABLE",
            vexp.NetworkAddressAction,
            "ENABLE",
            None,
            None,
        ),
        (
            "ALTER NETWORK ADDRESS addr01 DISABLE",
            vexp.NetworkAddressAction,
            "DISABLE",
            None,
            None,
        ),
    ],
)
def test_every_alter_network_address_action_is_structured(
    sql: str,
    action_type: type[exp.Expr],
    action: str,
    address: str | None,
    port: str | None,
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.AlterNetworkAddress)
    assert expression.kind == "NETWORK ADDRESS"
    assert len(expression.actions) == 1
    parsed_action = expression.actions[0]
    assert isinstance(parsed_action, action_type)
    if isinstance(parsed_action, exp.AlterRename):
        assert parsed_action.name == action
    else:
        assert isinstance(parsed_action, vexp.NetworkAddressAction)
        assert parsed_action.name == action
        parsed_address = parsed_action.args.get("expression")
        parsed_port = parsed_action.args.get("port")
        assert (parsed_address.this if isinstance(parsed_address, exp.Literal) else None) == address
        assert (parsed_port.this if isinstance(parsed_port, exp.Literal) else None) == port
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "exists", "cascade"),
    [
        ("DROP NETWORK ADDRESS addr01", False, False),
        ("DROP NETWORK ADDRESS IF EXISTS addr01", True, False),
        ("DROP NETWORK ADDRESS addr01 CASCADE", False, True),
        ('DROP NETWORK ADDRESS IF EXISTS "External Address" CASCADE', True, True),
    ],
)
def test_drop_network_address_is_typed_and_stable(sql: str, exists: bool, cascade: bool) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.DropNetworkAddress)
    assert expression.kind == "NETWORK ADDRESS"
    assert expression.args.get("exists") is exists
    assert expression.args.get("cascade") is cascade
    assert isinstance(expression.this, exp.Identifier)
    _assert_parent_links(expression)


def test_omitted_create_defaults_remain_omitted() -> None:
    expression = parse_one(
        "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH '10.20.110.21'",
        read="vertica",
    )
    assert isinstance(expression, vexp.CreateNetworkAddress)
    spec = expression.args.get("spec")
    assert isinstance(spec, vexp.NetworkAddressSpec)
    assert spec.args.get("port") is None
    assert spec.args.get("state") is None
    assert "PORT" not in _strict(expression)
    assert "ENABLED" not in _strict(expression)


def test_programmatic_lifecycle_ast_generates_exact_sql() -> None:
    create = vexp.CreateNetworkAddress(
        this=_identifier("node1_nat"),
        kind="NETWORK ADDRESS",
        spec=_spec("router.example.com", port="5435", state="DISABLED"),
    )
    alter = vexp.AlterNetworkAddress(
        this=_identifier("node1_nat"),
        kind="NETWORK ADDRESS",
        actions=[_action("SET", address="203.0.113.10", port="443")],
    )
    drop = vexp.DropNetworkAddress(
        this=_identifier("node1_nat"),
        kind="NETWORK ADDRESS",
        exists=True,
        cascade=True,
    )

    assert _strict(create) == (
        "CREATE NETWORK ADDRESS node1_nat ON v_node0001 "
        "WITH 'router.example.com' PORT 5435 DISABLED"
    )
    assert _strict(alter) == ("ALTER NETWORK ADDRESS node1_nat SET TO '203.0.113.10' PORT 443")
    assert _strict(drop) == "DROP NETWORK ADDRESS IF EXISTS node1_nat CASCADE"
    for expression in (create, alter, drop):
        assert parse_one(_strict(expression), read="vertica") == expression
        _assert_parent_links(expression)


def test_copy_transform_serialization_optimizer_and_multi_statement_are_lossless() -> None:
    expression = parse_one(
        "CREATE NETWORK ADDRESS addr01 ON v_node0001 WITH 'host.example' PORT 5433 ENABLED",
        read="vertica",
    )
    copied = expression.copy()
    assert copied == expression
    assert copied is not expression
    _assert_parent_links(copied)

    renamed = copied.transform(
        lambda node: (
            _identifier("v_node0002")
            if isinstance(node, exp.Identifier) and node.name == "v_node0001"
            else node
        )
    )
    assert _strict(renamed) == (
        "CREATE NETWORK ADDRESS addr01 ON v_node0002 WITH 'host.example' PORT 5433 ENABLED"
    )
    restored = exp.Expr.load(expression.dump())
    assert restored == expression
    assert isinstance(restored, vexp.CreateNetworkAddress)

    optimized = optimize(expression, dialect="vertica")
    assert isinstance(optimized, vexp.CreateNetworkAddress)
    assert _strict(optimized) == (
        'CREATE NETWORK ADDRESS "addr01" ON "v_node0001" WITH \'host.example\' PORT 5433 ENABLED'
    )
    assert isinstance(parse_one(_strict(optimized), read="vertica"), vexp.CreateNetworkAddress)
    _assert_parent_links(optimized)

    statements = parse(
        "CREATE NETWORK ADDRESS a ON n WITH 'host'; "
        "ALTER NETWORK ADDRESS a ENABLE; "
        "DROP NETWORK ADDRESS a CASCADE",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateNetworkAddress,
        vexp.AlterNetworkAddress,
        vexp.DropNetworkAddress,
    ]


def test_comments_survive_structured_roundtrip() -> None:
    expression = assert_roundtrip(
        "/* lead */ CREATE NETWORK ADDRESS a ON n WITH 'host' PORT 5433 ENABLED /* tail */"
    )
    generated = _strict(expression)
    assert generated.count("lead") == 1
    assert generated.count("tail") == 1


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE NETWORK ADDRESS",
        "CREATE NETWORK ADDRESS a",
        "CREATE NETWORK ADDRESS a ON",
        "CREATE NETWORK ADDRESS a ON n",
        "CREATE NETWORK ADDRESS a ON n WITH",
        "CREATE NETWORK ADDRESS a n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS a ON n '10.0.0.1'",
        "CREATE NETWORK ADDRESS a ON n WITH 10",
        "CREATE NETWORK ADDRESS a ON n WITH NULL",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT '5433'",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT -1",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT +1",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT 1.5",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' PORT 1e3",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' ENABLE",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' DISABLED PORT 5433",
        "CREATE NETWORK ADDRESS a ON n WITH '10.0.0.1' ENABLED DISABLED",
        "CREATE NETWORK ADDRESS app.a ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS a ON app.n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS \"\" ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS a ON \"\" WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS 'a' ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS 1 ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS NULL ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS a ON TRUE WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS βeta ON n WITH '10.0.0.1'",
        "CREATE NETWORK ADDRESS a\u0661 ON n WITH '10.0.0.1'",
    ],
)
def test_create_rejects_structurally_invalid_syntax(sql: str) -> None:
    for error_level in (ErrorLevel.IMMEDIATE, ErrorLevel.RAISE):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER NETWORK ADDRESS",
        "ALTER NETWORK ADDRESS a",
        "ALTER NETWORK ADDRESS a RENAME",
        "ALTER NETWORK ADDRESS a RENAME b",
        "ALTER NETWORK ADDRESS a RENAME TO",
        "ALTER NETWORK ADDRESS a RENAME TO app.b",
        "ALTER NETWORK ADDRESS a SET",
        "ALTER NETWORK ADDRESS a SET '10.0.0.2'",
        "ALTER NETWORK ADDRESS a SET TO",
        "ALTER NETWORK ADDRESS a SET TO 10",
        "ALTER NETWORK ADDRESS a SET TO '10.0.0.2' PORT",
        "ALTER NETWORK ADDRESS a SET TO '10.0.0.2' PORT -1",
        "ALTER NETWORK ADDRESS a SET TO '10.0.0.2' PORT '4000'",
        "ALTER NETWORK ADDRESS a SET TO '10.0.0.2' ENABLE",
        "ALTER NETWORK ADDRESS a PORT 4000",
        "ALTER NETWORK ADDRESS a SET PORT 4000",
        "ALTER NETWORK ADDRESS a ENABLED",
        "ALTER NETWORK ADDRESS a DISABLED",
        "ALTER NETWORK ADDRESS a RENAME TO b DISABLE",
        "ALTER NETWORK ADDRESS a SET NODE TO n2",
        "ALTER NETWORK ADDRESS app.a ENABLE",
        'ALTER NETWORK ADDRESS "" ENABLE',
        'ALTER NETWORK ADDRESS a RENAME TO ""',
        "ALTER NETWORK ADDRESS 'a' ENABLE",
    ],
)
def test_alter_rejects_structurally_invalid_syntax(sql: str) -> None:
    for error_level in (ErrorLevel.IMMEDIATE, ErrorLevel.RAISE):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP NETWORK ADDRESS",
        "DROP IF EXISTS NETWORK ADDRESS a",
        "DROP NETWORK ADDRESS a, b",
        "DROP NETWORK ADDRESS CASCADE a",
        "DROP NETWORK ADDRESS a RESTRICT",
        "DROP NETWORK ADDRESS a CASCADE EXTRA",
        "DROP NETWORK ADDRESS app.a",
        'DROP NETWORK ADDRESS ""',
        "DROP NETWORK ADDRESS 'a'",
        "DROP NETWORK ADDRESS 1",
    ],
)
def test_drop_rejects_structurally_invalid_syntax(sql: str) -> None:
    for error_level in (ErrorLevel.IMMEDIATE, ErrorLevel.RAISE):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE NETWORK ADDRESS 'a' ON n WITH 'host'",
        "CREATE NETWORK ADDRESS 1 ON n WITH 'host'",
        "CREATE NETWORK ADDRESS a ON 'n' WITH 'host'",
        "ALTER NETWORK ADDRESS 'a' ENABLE",
        "DROP NETWORK ADDRESS 1",
    ],
)
def test_invalid_identifiers_raise_parse_error_in_deferred_error_mode(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE OR REPLACE NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE IF NOT EXISTS NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE TEMP NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE TEMPORARY NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE GLOBAL TEMPORARY NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE MATERIALIZED NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE UNLOGGED NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE FLEX NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE FLEXIBLE NETWORK ADDRESS a ON n WITH 'host'",
        "CREATE EXTERNAL NETWORK ADDRESS a ON n WITH 'host'",
        "ALTER IF EXISTS NETWORK ADDRESS a ENABLE",
        "ALTER ONLY NETWORK ADDRESS a ENABLE",
        "ALTER MATERIALIZED NETWORK ADDRESS a ENABLE",
        "ALTER FLEX NETWORK ADDRESS a ENABLE",
        "DROP IF EXISTS NETWORK ADDRESS a",
        "DROP TEMPORARY NETWORK ADDRESS a",
        "DROP MATERIALIZED NETWORK ADDRESS a",
        "DROP EXTERNAL NETWORK ADDRESS a",
        "CREATE NETWORK \"ADDRESS\" a ON n WITH 'host'",
        "CREATE NETWORK \"INTERFACE\" a ON n WITH 'host'",
        "CREATE NETWORK 'INTERFACE' a ON n WITH 'host'",
        "CREATE \"NETWORK\" ADDRESS a ON n WITH 'host'",
        "CREATE \"NETWORK\" INTERFACE a ON n WITH 'host'",
        "CREATE 'NETWORK' ADDRESS a ON n WITH 'host'",
        'ALTER NETWORK "ADDRESS" a ENABLE',
        'ALTER NETWORK "INTERFACE" a ENABLE',
        'ALTER "NETWORK" ADDRESS a ENABLE',
        'ALTER "NETWORK" INTERFACE a ENABLE',
        'DROP NETWORK "ADDRESS" a',
        'DROP NETWORK "INTERFACE" a',
        'DROP "NETWORK" ADDRESS a',
        'DROP "NETWORK" INTERFACE a',
        "CREATE NETWORK",
        "CREATE NETWORK ADDRESSES",
        "ALTER NETWORK",
        "ALTER NETWORK ADDRESSES",
        "DROP NETWORK",
        "DROP NETWORK ADDRESSES",
    ],
)
def test_compound_kind_dispatch_fails_closed(sql: str) -> None:
    for error_level in (ErrorLevel.IMMEDIATE, ErrorLevel.RAISE):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    ("sql", "expression_type"),
    [
        ("CREATE NETWORK INTERFACE ni ON n WITH '10.0.0.1'", exp.Command),
        ("ALTER NETWORK INTERFACE ni ENABLE", exp.Command),
        ("DROP NETWORK INTERFACE ni", exp.Command),
        ("CREATE TABLE network_address (x INT)", exp.Create),
        ("ALTER TABLE network_address ADD COLUMN x INT", exp.Alter),
        ("DROP TABLE network_address", exp.Drop),
        ("CREATE TABLE t (network INT, address VARCHAR)", exp.Create),
        (
            "CREATE LOAD BALANCE GROUP g WITH ADDRESS network_address",
            vexp.CreateLoadBalanceGroup,
        ),
        (
            "CREATE ROUTING RULE network_address ROUTE 'x' TO g",
            vexp.CreateRoutingRule,
        ),
    ],
)
def test_dispatch_preserves_network_interface_and_unrelated_objects(
    sql: str, expression_type: type[exp.Expr]
) -> None:
    assert isinstance(parse_one(sql, read="vertica"), expression_type)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE NETWORK ADDRESS a ON n WITH 'host' PORT 5433 DISABLED",
        "ALTER NETWORK ADDRESS a SET TO 'host2' PORT 5434",
        "DROP NETWORK ADDRESS IF EXISTS a CASCADE",
    ],
)
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_statement_roots_fail_atomically_in_foreign_dialects(sql: str, dialect: str) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        _spec(port="5433", state="ENABLED"),
        _action("SET", address="host", port="5433"),
        _action("ENABLE"),
    ],
)
def test_leaf_nodes_fail_atomically_in_foreign_dialects(expression: exp.Expr) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateNetworkAddress(this=_identifier("a"), kind="TABLE", spec=_spec()),
        vexp.CreateNetworkAddress(
            this=_identifier("a"), kind=exp.var("NETWORK ADDRESS"), spec=_spec()
        ),
        vexp.CreateNetworkAddress(kind="NETWORK ADDRESS", spec=_spec()),
        vexp.CreateNetworkAddress(this=exp.to_table("app.a"), kind="NETWORK ADDRESS", spec=_spec()),
        vexp.CreateNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS"),
        _set_arg(
            vexp.CreateNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", spec=_spec()),
            "this",
            [_identifier("a")],
        ),
        vexp.CreateNetworkAddress(
            this=_identifier("a"), kind="NETWORK ADDRESS", spec=_spec(), replace=True
        ),
        vexp.AlterNetworkAddress(this=_identifier("a"), kind="TABLE", actions=[]),
        vexp.AlterNetworkAddress(
            this=_identifier("a"), kind=exp.var("NETWORK ADDRESS"), actions=[]
        ),
        vexp.AlterNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", actions=[]),
        vexp.AlterNetworkAddress(
            this=_identifier("a"),
            kind="NETWORK ADDRESS",
            actions=[_action("ENABLE"), _action("DISABLE")],
        ),
        vexp.AlterNetworkAddress(
            this=_identifier("a"), kind="NETWORK ADDRESS", actions=[exp.Drop(this="x")]
        ),
        _set_arg(
            vexp.AlterNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", actions=[]),
            "actions",
            _action("ENABLE"),
        ),
        vexp.AlterNetworkAddress(
            this=_identifier("a"),
            kind="NETWORK ADDRESS",
            actions=[exp.AlterRename(this=exp.to_table("app.b"))],
        ),
        vexp.DropNetworkAddress(this=_identifier("a"), kind="TABLE"),
        vexp.DropNetworkAddress(this=_identifier("a"), kind=exp.var("NETWORK ADDRESS")),
        vexp.DropNetworkAddress(kind="NETWORK ADDRESS"),
        vexp.DropNetworkAddress(this=exp.to_table("app.a"), kind="NETWORK ADDRESS"),
        _set_arg(
            vexp.DropNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS"),
            "this",
            {"name": "a"},
        ),
        vexp.DropNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", exists="yes"),
        vexp.DropNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", cascade="yes"),
        vexp.DropNetworkAddress(this=_identifier("a"), kind="NETWORK ADDRESS", restrict=True),
        vexp.DropNetworkAddress(
            this=_identifier("a"),
            kind="NETWORK ADDRESS",
            expressions=[_identifier("b")],
        ),
    ],
)
def test_programmatic_statement_roots_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.NetworkAddressSpec(node=_identifier("n")),
        vexp.NetworkAddressSpec(this=exp.Literal.string("host")),
        vexp.NetworkAddressSpec(this=exp.var("host"), node=_identifier("n")),
        _set_arg(_spec(), "this", [exp.Literal.string("host")]),
        _set_arg(_spec(), "node", {"name": "n"}),
        vexp.NetworkAddressSpec(this=exp.Literal(this=None, is_string=True), node=_identifier("n")),
        vexp.NetworkAddressSpec(this=exp.Literal.string("host"), node=exp.to_table("app.n")),
        vexp.NetworkAddressSpec(
            this=exp.Literal.string("host"), node=_identifier("n"), port=exp.Literal.string("1")
        ),
        _spec(port="-1"),
        _spec(port="+1"),
        _spec(port="1.5"),
        _spec(port="1e3"),
        _spec(port="\u0661"),
        vexp.NetworkAddressSpec(
            this=exp.Literal.string("host"),
            node=_identifier("n"),
            port=exp.Literal(this=None, is_string=False),
        ),
        vexp.NetworkAddressSpec(
            this=exp.Literal.string("host"), node=_identifier("n"), state=_identifier("ENABLED")
        ),
        _spec(state="UNKNOWN"),
        _set_arg(_spec(), "state", _set_arg(exp.var("ENABLED"), "bogus", exp.true())),
        _set_arg(
            _spec(),
            "this",
            _set_arg(exp.Literal.string("host"), "bogus", _identifier("x")),
        ),
        _set_arg(
            _spec(port="5433"),
            "port",
            _set_arg(_port("5433"), "bogus", _identifier("x")),
        ),
        _set_arg(
            _spec(),
            "node",
            _set_arg(_identifier("n"), "bogus", _identifier("x")),
        ),
        _set_arg(_spec(), "extra", exp.true()),
        vexp.NetworkAddressAction(),
        vexp.NetworkAddressAction(this=_identifier("SET")),
        _action("SET"),
        vexp.NetworkAddressAction(this=exp.var("SET"), expression=exp.var("host")),
        _set_arg(_action("SET", address="host"), "expression", [exp.Literal.string("host")]),
        _action("SET", address="host", port="-1"),
        _action("ENABLE", address="host"),
        _action("DISABLE", port="5433"),
        _action("UNKNOWN"),
        _set_arg(_action("ENABLE"), "this", _set_arg(exp.var("ENABLE"), "bogus", exp.true())),
        _set_arg(_action("ENABLE"), "extra", exp.true()),
    ],
)
def test_programmatic_leaf_nodes_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "name",
    ["", "app.address", "x;DROP_TABLE_y", "white space", "1address", "βeta", "a\u0661"],
)
def test_programmatic_unquoted_identifiers_must_be_safe(name: str) -> None:
    expression = vexp.CreateNetworkAddress(
        this=_identifier(name), kind="NETWORK ADDRESS", spec=_spec()
    )
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_programmatic_identifier_flags_are_strictly_typed() -> None:
    name = _identifier("a")
    name.set("quoted", "yes")
    expression = vexp.CreateNetworkAddress(this=name, kind="NETWORK ADDRESS", spec=_spec())
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_identifier_policy_is_ascii_first_with_unicode_letter_continuations() -> None:
    network = assert_roundtrip("CREATE NETWORK ADDRESS addré ON nœud1 WITH 'router.example.com'")
    group = assert_roundtrip("CREATE LOAD BALANCE GROUP grüppe WITH ADDRESS addré")
    routing = assert_roundtrip("CREATE ROUTING RULE règle ROUTE '0.0.0.0/0' TO grüppe")

    assert _strict(network).startswith("CREATE NETWORK ADDRESS addré ON nœud1")
    assert _strict(group) == "CREATE LOAD BALANCE GROUP grüppe WITH ADDRESS addré"
    assert _strict(routing) == "CREATE ROUTING RULE règle ROUTE '0.0.0.0/0' TO grüppe"


def test_quoted_identifiers_can_use_unicode_initials_and_special_characters() -> None:
    expression = vexp.CreateNetworkAddress(
        this=_identifier("β.External Address", quoted=True),
        kind="NETWORK ADDRESS",
        spec=vexp.NetworkAddressSpec(
            this=exp.Literal.string("host"),
            node=_identifier("\u0661 Node", quoted=True),
        ),
    )
    assert _strict(expression) == (
        'CREATE NETWORK ADDRESS "β.External Address" ON "\u0661 Node" WITH \'host\''
    )


def test_huge_programmatic_port_is_validated_without_integer_conversion() -> None:
    huge_port = "9" * 5000
    expression = vexp.CreateNetworkAddress(
        this=_identifier("a"),
        kind="NETWORK ADDRESS",
        spec=_spec(port=huge_port),
    )
    generated = _strict(expression)
    assert generated.endswith(f" PORT {huge_port}")
