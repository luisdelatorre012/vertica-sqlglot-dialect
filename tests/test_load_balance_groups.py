"""Semantic Vertica LOAD BALANCE GROUP lifecycle regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str, quoted: bool = False) -> exp.Identifier:
    return exp.to_identifier(name, quoted=quoted)


def _spec(
    member_kind: str = "ADDRESS",
    members: tuple[str, ...] = ("addr01",),
    filter_value: exp.Expr | None = None,
    policy: exp.Expr | None = None,
) -> vexp.LoadBalanceGroupSpec:
    return vexp.LoadBalanceGroupSpec(
        this=exp.var(member_kind),
        expressions=[_identifier(member) for member in members],
        filter=filter_value,
        policy=policy,
    )


def _action(
    action: str,
    *,
    member_kind: str | None = None,
    value: exp.Expr | None = None,
    members: tuple[str, ...] = (),
) -> vexp.LoadBalanceGroupAction:
    return vexp.LoadBalanceGroupAction(
        this=exp.var(action),
        member_kind=exp.var(member_kind) if member_kind else None,
        expression=value,
        expressions=[_identifier(member) for member in members],
    )


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


def _set_arg(expression: exp.Expr, key: str, value: object) -> exp.Expr:
    expression.set(key, value)
    return expression


@pytest.mark.parametrize(
    ("sql", "member_kind", "members", "filter_value", "policy"),
    [
        (
            "CREATE LOAD BALANCE GROUP lb_addr WITH ADDRESS addr01",
            "ADDRESS",
            ["addr01"],
            None,
            None,
        ),
        (
            "CREATE LOAD BALANCE GROUP lb_addr WITH ADDRESS addr01, addr02 POLICY 'RANDOM'",
            "ADDRESS",
            ["addr01", "addr02"],
            None,
            "RANDOM",
        ),
        (
            "CREATE LOAD BALANCE GROUP lb_fault WITH FAULT GROUP fg1, fg2 FILTER '0.0.0.0/0'",
            "FAULT GROUP",
            ["fg1", "fg2"],
            "0.0.0.0/0",
            None,
        ),
        (
            "CREATE LOAD BALANCE GROUP lb_sc WITH SUBCLUSTER sc1, sc2 "
            "FILTER 'fd00::/8' POLICY 'NONE'",
            "SUBCLUSTER",
            ["sc1", "sc2"],
            "fd00::/8",
            "NONE",
        ),
        (
            'CREATE LOAD BALANCE GROUP "LB Group" WITH ADDRESS "Address One" POLICY \'ROUNDROBIN\'',
            "ADDRESS",
            ["Address One"],
            None,
            "ROUNDROBIN",
        ),
        (
            'CREATE LOAD BALANCE GROUP g WITH FAULT GROUP "FILTER" FILTER '
            "'not-a-cidr' POLICY 'random'",
            "FAULT GROUP",
            ["FILTER"],
            "not-a-cidr",
            "random",
        ),
    ],
)
def test_create_load_balance_group_is_typed_and_stable(
    sql: str,
    member_kind: str,
    members: list[str],
    filter_value: str | None,
    policy: str | None,
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateLoadBalanceGroup)
    assert expression.kind == "LOAD BALANCE GROUP"
    assert isinstance(expression.this, exp.Identifier)
    spec = expression.args["spec"]
    assert isinstance(spec, vexp.LoadBalanceGroupSpec)
    assert isinstance(spec.this, exp.Var)
    assert spec.this.name == member_kind
    assert [member.name for member in spec.expressions] == members
    parsed_filter = spec.args.get("filter")
    parsed_policy = spec.args.get("policy")
    assert (parsed_filter.this if isinstance(parsed_filter, exp.Literal) else None) == filter_value
    assert (parsed_policy.this if isinstance(parsed_policy, exp.Literal) else None) == policy
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "action_type", "action", "member_kind", "values"),
    [
        (
            "ALTER LOAD BALANCE GROUP lb_addr RENAME TO lb_new",
            exp.AlterRename,
            "lb_new",
            None,
            [],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_fault SET FILTER TO '10.20.0.0/16'",
            vexp.LoadBalanceGroupAction,
            "SET FILTER",
            None,
            ["10.20.0.0/16"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_addr SET POLICY TO 'ROUNDROBIN'",
            vexp.LoadBalanceGroupAction,
            "SET POLICY",
            None,
            ["ROUNDROBIN"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_addr ADD ADDRESS addr02, addr03",
            vexp.LoadBalanceGroupAction,
            "ADD",
            "ADDRESS",
            ["addr02", "addr03"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_fault ADD FAULT GROUP fg2",
            vexp.LoadBalanceGroupAction,
            "ADD",
            "FAULT GROUP",
            ["fg2"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_sc ADD SUBCLUSTER sc2, sc3",
            vexp.LoadBalanceGroupAction,
            "ADD",
            "SUBCLUSTER",
            ["sc2", "sc3"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_addr DROP ADDRESS addr01",
            vexp.LoadBalanceGroupAction,
            "DROP",
            "ADDRESS",
            ["addr01"],
        ),
        (
            "ALTER LOAD BALANCE GROUP lb_fault DROP FAULT GROUP fg1",
            vexp.LoadBalanceGroupAction,
            "DROP",
            "FAULT GROUP",
            ["fg1"],
        ),
        (
            'ALTER LOAD BALANCE GROUP "LB Group" DROP SUBCLUSTER "POLICY"',
            vexp.LoadBalanceGroupAction,
            "DROP",
            "SUBCLUSTER",
            ["POLICY"],
        ),
    ],
)
def test_every_alter_load_balance_group_action_is_structured(
    sql: str,
    action_type: type[exp.Expr],
    action: str,
    member_kind: str | None,
    values: list[str],
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.AlterLoadBalanceGroup)
    assert expression.kind == "LOAD BALANCE GROUP"
    assert len(expression.actions) == 1
    parsed_action = expression.actions[0]
    assert isinstance(parsed_action, action_type)
    if isinstance(parsed_action, exp.AlterRename):
        assert parsed_action.name == action
    else:
        assert isinstance(parsed_action, vexp.LoadBalanceGroupAction)
        assert parsed_action.name == action
        marker = parsed_action.args.get("member_kind")
        assert (marker.name if isinstance(marker, exp.Var) else None) == member_kind
        scalar = parsed_action.args.get("expression")
        parsed_values = (
            [scalar.this]
            if isinstance(scalar, exp.Literal)
            else [member.name for member in parsed_action.expressions]
        )
        assert parsed_values == values
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "exists", "cascade"),
    [
        ("DROP LOAD BALANCE GROUP lb_addr", False, False),
        ("DROP LOAD BALANCE GROUP IF EXISTS lb_addr", True, False),
        ("DROP LOAD BALANCE GROUP lb_addr CASCADE", False, True),
        ('DROP LOAD BALANCE GROUP IF EXISTS "LB Group" CASCADE', True, True),
    ],
)
def test_drop_load_balance_group_is_typed_and_stable(sql: str, exists: bool, cascade: bool) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.DropLoadBalanceGroup)
    assert expression.kind == "LOAD BALANCE GROUP"
    assert expression.args.get("exists") is exists
    assert expression.args.get("cascade") is cascade
    assert isinstance(expression.this, exp.Identifier)
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS FILTER",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS POLICY",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS POLICY POLICY 'NONE'",
        "CREATE LOAD BALANCE GROUP g WITH FAULT GROUP FILTER FILTER 'x'",
        "ALTER LOAD BALANCE GROUP g ADD ADDRESS FILTER",
        "ALTER LOAD BALANCE GROUP g DROP SUBCLUSTER POLICY",
    ],
)
def test_contextual_clause_words_remain_legal_member_names(sql: str) -> None:
    assert_roundtrip(sql)


def test_connection_policy_identifiers_accept_unquoted_unicode_letters() -> None:
    group = assert_roundtrip("CREATE LOAD BALANCE GROUP grüppe WITH ADDRESS addré")
    routing_rule = assert_roundtrip("CREATE ROUTING RULE règle ROUTE '0.0.0.0/0' TO grüppe")

    assert _strict(group) == "CREATE LOAD BALANCE GROUP grüppe WITH ADDRESS addré"
    assert _strict(routing_rule) == ("CREATE ROUTING RULE règle ROUTE '0.0.0.0/0' TO grüppe")


def test_programmatic_lifecycle_ast_generates_exact_sql() -> None:
    create = vexp.CreateLoadBalanceGroup(
        this=_identifier("lb_sc"),
        kind="LOAD BALANCE GROUP",
        spec=_spec(
            "SUBCLUSTER",
            ("sc1", "sc2"),
            exp.Literal.string("fd00::/8"),
            exp.Literal.string("RANDOM"),
        ),
    )
    alter = vexp.AlterLoadBalanceGroup(
        this=_identifier("lb_sc"),
        kind="LOAD BALANCE GROUP",
        actions=[_action("DROP", member_kind="SUBCLUSTER", members=("sc2",))],
    )
    drop = vexp.DropLoadBalanceGroup(
        this=_identifier("lb_sc"),
        kind="LOAD BALANCE GROUP",
        exists=True,
        cascade=True,
    )

    assert _strict(create) == (
        "CREATE LOAD BALANCE GROUP lb_sc WITH SUBCLUSTER sc1, sc2 FILTER 'fd00::/8' POLICY 'RANDOM'"
    )
    assert _strict(alter) == "ALTER LOAD BALANCE GROUP lb_sc DROP SUBCLUSTER sc2"
    assert _strict(drop) == "DROP LOAD BALANCE GROUP IF EXISTS lb_sc CASCADE"
    for expression in (create, alter, drop):
        assert parse_one(_strict(expression), read="vertica") == expression
        _assert_parent_links(expression)


def test_copy_transform_and_multi_statement_traversal_are_lossless() -> None:
    expression = parse_one(
        "CREATE LOAD BALANCE GROUP lb_addr WITH ADDRESS addr01, addr02 POLICY 'RANDOM'",
        read="vertica",
    )
    copied = expression.copy()
    assert copied == expression
    assert copied is not expression
    _assert_parent_links(copied)

    renamed = copied.transform(
        lambda node: (
            _identifier("addr99")
            if isinstance(node, exp.Identifier) and node.name == "addr02"
            else node
        )
    )
    assert _strict(renamed) == (
        "CREATE LOAD BALANCE GROUP lb_addr WITH ADDRESS addr01, addr99 POLICY 'RANDOM'"
    )
    _assert_parent_links(renamed)

    statements = parse(
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a; "
        "ALTER LOAD BALANCE GROUP g ADD ADDRESS b; "
        "DROP LOAD BALANCE GROUP g CASCADE",
        read="vertica",
    )
    assert [type(statement) for statement in statements] == [
        vexp.CreateLoadBalanceGroup,
        vexp.AlterLoadBalanceGroup,
        vexp.DropLoadBalanceGroup,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE LOAD BALANCE GROUP",
        "CREATE LOAD BALANCE GROUP g",
        "CREATE LOAD BALANCE GROUP g WITH",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a,",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a FILTER '0.0.0.0/0'",
        "CREATE LOAD BALANCE GROUP g WITH FAULT GROUP fg",
        "CREATE LOAD BALANCE GROUP g WITH SUBCLUSTER sc",
        "CREATE LOAD BALANCE GROUP g WITH FAULT GROUP fg FILTER 1",
        "CREATE LOAD BALANCE GROUP g WITH SUBCLUSTER sc FILTER NULL",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a POLICY RANDOM",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a POLICY 'INVALID'",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a POLICY 'NONE' EXTRA",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a, POLICY 'NONE'",
        "CREATE LOAD BALANCE GROUP g WITH FAULT GROUP fg, FILTER 'x'",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a SUBCLUSTER sc FILTER 'x'",
        "CREATE LOAD BALANCE GROUP app.g WITH ADDRESS a",
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS app.a",
        'CREATE LOAD BALANCE GROUP "" WITH ADDRESS a',
        'CREATE LOAD BALANCE GROUP g WITH ADDRESS ""',
        "CREATE LOAD BALANCE GROUP g WITH FAULT GROUP \"\" FILTER 'x'",
        "CREATE LOAD BALANCE GROUP 'g' WITH ADDRESS a",
        "CREATE LOAD BALANCE GROUP 1 WITH ADDRESS a",
        "CREATE LOAD BALANCE GROUP NULL WITH ADDRESS a",
        "CREATE LOAD BALANCE GROUP TRUE WITH ADDRESS a",
    ],
)
def test_create_rejects_structurally_invalid_syntax(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER LOAD BALANCE GROUP",
        "ALTER LOAD BALANCE GROUP g",
        "ALTER LOAD BALANCE GROUP g RENAME",
        "ALTER LOAD BALANCE GROUP g RENAME TO",
        "ALTER LOAD BALANCE GROUP g RENAME TO app.h",
        "ALTER LOAD BALANCE GROUP g RENAME TO h SET POLICY TO 'NONE'",
        "ALTER LOAD BALANCE GROUP g SET",
        "ALTER LOAD BALANCE GROUP g SET FILTER '0.0.0.0/0'",
        "ALTER LOAD BALANCE GROUP g SET FILTER TO 1",
        "ALTER LOAD BALANCE GROUP g SET POLICY TO RANDOM",
        "ALTER LOAD BALANCE GROUP g SET POLICY TO 'INVALID'",
        "ALTER LOAD BALANCE GROUP g SET UNKNOWN TO 'x'",
        "ALTER LOAD BALANCE GROUP g ADD",
        "ALTER LOAD BALANCE GROUP g ADD ADDRESS",
        "ALTER LOAD BALANCE GROUP g ADD ADDRESS a,",
        "ALTER LOAD BALANCE GROUP g ADD ADDRESS app.a",
        'ALTER LOAD BALANCE GROUP "" ADD ADDRESS a',
        'ALTER LOAD BALANCE GROUP g RENAME TO ""',
        'ALTER LOAD BALANCE GROUP g ADD ADDRESS ""',
        "ALTER LOAD BALANCE GROUP g REMOVE ADDRESS a",
        "ALTER LOAD BALANCE GROUP g DROP FAULT",
        "ALTER LOAD BALANCE GROUP g DROP SUBCLUSTER sc,",
        "ALTER LOAD BALANCE GROUP app.g ADD ADDRESS a",
        "ALTER LOAD BALANCE GROUP 'g' ADD ADDRESS a",
    ],
)
def test_alter_rejects_structurally_invalid_syntax(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP LOAD BALANCE GROUP",
        "DROP IF EXISTS LOAD BALANCE GROUP g",
        "DROP LOAD BALANCE GROUP g, h",
        "DROP LOAD BALANCE GROUP g RESTRICT",
        "DROP LOAD BALANCE GROUP CASCADE g",
        "DROP LOAD BALANCE GROUP app.g",
        'DROP LOAD BALANCE GROUP ""',
        "DROP LOAD BALANCE GROUP 'g'",
        "DROP LOAD BALANCE GROUP 1",
        "DROP LOAD BALANCE GROUP g CASCADE EXTRA",
    ],
)
def test_drop_rejects_structurally_invalid_syntax(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE OR REPLACE LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE IF NOT EXISTS LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE TEMP LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE TEMPORARY LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE GLOBAL TEMPORARY LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE MATERIALIZED LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE UNLOGGED LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE FLEX LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE FLEXIBLE LOAD BALANCE GROUP g WITH ADDRESS a",
        "CREATE RESOURCE LOAD BALANCE GROUP g WITH ADDRESS a",
        "ALTER IF EXISTS LOAD BALANCE GROUP g RENAME TO h",
        "ALTER ONLY LOAD BALANCE GROUP g RENAME TO h",
        "ALTER MATERIALIZED LOAD BALANCE GROUP g RENAME TO h",
        "ALTER FLEX LOAD BALANCE GROUP g RENAME TO h",
        "DROP IF EXISTS LOAD BALANCE GROUP g",
        "DROP TEMPORARY LOAD BALANCE GROUP g",
        "DROP MATERIALIZED LOAD BALANCE GROUP g",
        "DROP EXTERNAL LOAD BALANCE GROUP g",
        "CREATE LOAD",
        "CREATE LOAD BALANCE",
        "ALTER LOAD",
        "ALTER LOAD BALANCE",
        "DROP LOAD",
        "DROP LOAD BALANCE",
    ],
)
def test_compound_kind_dispatch_fails_closed(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "expression_type"),
    [
        ("CREATE TABLE load_balance_group (x INT)", exp.Create),
        ("ALTER TABLE load_balance_group ADD COLUMN x INT", exp.Alter),
        ("DROP TABLE load_balance_group", exp.Drop),
        ("CREATE TABLE t (load INT, balance INT, group_name INT)", exp.Create),
        (
            "CREATE ROUTING RULE load_rule ROUTE 'x' TO load_balance_group",
            vexp.CreateRoutingRule,
        ),
        (
            "ALTER ROUTING RULE load_rule SET GROUP TO load_balance_group",
            vexp.AlterRoutingRule,
        ),
        ("DROP ROUTING RULE load_rule", vexp.DropRoutingRule),
    ],
)
def test_compound_kind_guard_does_not_collide_with_other_objects(
    sql: str, expression_type: type[exp.Expr]
) -> None:
    assert isinstance(parse_one(sql, read="vertica"), expression_type)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE LOAD BALANCE GROUP g WITH ADDRESS a",
        "ALTER LOAD BALANCE GROUP g SET POLICY TO 'NONE'",
        "DROP LOAD BALANCE GROUP IF EXISTS g CASCADE",
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
        _spec(),
        _action("SET POLICY", value=exp.Literal.string("NONE")),
        _action("ADD", member_kind="ADDRESS", members=("addr01",)),
    ],
)
def test_leaf_nodes_fail_atomically_in_foreign_dialects(expression: exp.Expr) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateLoadBalanceGroup(this=_identifier("g"), kind="TABLE", spec=_spec()),
        vexp.CreateLoadBalanceGroup(
            this=_identifier("g"), kind=exp.var("LOAD BALANCE GROUP"), spec=_spec()
        ),
        vexp.CreateLoadBalanceGroup(kind="LOAD BALANCE GROUP", spec=_spec()),
        vexp.CreateLoadBalanceGroup(
            this=exp.to_table("app.g"), kind="LOAD BALANCE GROUP", spec=_spec()
        ),
        vexp.CreateLoadBalanceGroup(
            this=_identifier("app.g"), kind="LOAD BALANCE GROUP", spec=_spec()
        ),
        vexp.CreateLoadBalanceGroup(this=_identifier("g"), kind="LOAD BALANCE GROUP"),
        vexp.CreateLoadBalanceGroup(
            this=_identifier("g"), kind="LOAD BALANCE GROUP", spec=_spec(), replace=True
        ),
        vexp.AlterLoadBalanceGroup(this=_identifier("g"), kind="TABLE", actions=[]),
        vexp.AlterLoadBalanceGroup(
            this=_identifier("g"), kind=exp.var("LOAD BALANCE GROUP"), actions=[]
        ),
        vexp.AlterLoadBalanceGroup(this=_identifier("g"), kind="LOAD BALANCE GROUP", actions=[]),
        vexp.AlterLoadBalanceGroup(
            this=_identifier("g"),
            kind="LOAD BALANCE GROUP",
            actions=[
                exp.AlterRename(this=_identifier("h")),
                _action("SET POLICY", value=exp.Literal.string("NONE")),
            ],
        ),
        vexp.AlterLoadBalanceGroup(
            this=_identifier("g"),
            kind="LOAD BALANCE GROUP",
            actions=[exp.Drop(this=_identifier("h"))],
        ),
        _set_arg(
            vexp.AlterLoadBalanceGroup(
                this=_identifier("g"), kind="LOAD BALANCE GROUP", actions=[]
            ),
            "actions",
            _action("ADD", member_kind="ADDRESS", members=("a",)),
        ),
        vexp.AlterLoadBalanceGroup(
            this=_identifier("g"),
            kind="LOAD BALANCE GROUP",
            actions=[exp.AlterRename(this=exp.to_table("app.h"))],
        ),
        vexp.DropLoadBalanceGroup(this=_identifier("g"), kind="TABLE"),
        vexp.DropLoadBalanceGroup(this=_identifier("g"), kind=exp.var("LOAD BALANCE GROUP")),
        vexp.DropLoadBalanceGroup(kind="LOAD BALANCE GROUP"),
        vexp.DropLoadBalanceGroup(this=exp.to_table("app.g"), kind="LOAD BALANCE GROUP"),
        vexp.DropLoadBalanceGroup(this=_identifier("g"), kind="LOAD BALANCE GROUP", exists="yes"),
        vexp.DropLoadBalanceGroup(this=_identifier("g"), kind="LOAD BALANCE GROUP", cascade="yes"),
        vexp.DropLoadBalanceGroup(this=_identifier("g"), kind="LOAD BALANCE GROUP", restrict=True),
        vexp.DropLoadBalanceGroup(
            this=_identifier("g"),
            kind="LOAD BALANCE GROUP",
            expressions=[_identifier("h")],
        ),
    ],
)
def test_programmatic_statement_roots_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.LoadBalanceGroupSpec(expressions=[_identifier("a")]),
        vexp.LoadBalanceGroupSpec(this=_identifier("ADDRESS"), expressions=[_identifier("a")]),
        _spec("UNKNOWN"),
        _spec(members=()),
        vexp.LoadBalanceGroupSpec(this=exp.var("ADDRESS"), expressions=[exp.to_table("app.a")]),
        _spec("ADDRESS", filter_value=exp.Literal.string("x")),
        _spec("FAULT GROUP"),
        _spec("SUBCLUSTER", filter_value=exp.Literal.number(1)),
        _spec("ADDRESS", policy=exp.var("NONE")),
        _spec("ADDRESS", policy=exp.Literal.string("INVALID")),
        _set_arg(_spec(), "expressions", _identifier("a")),
        _spec(
            "FAULT GROUP",
            filter_value=exp.Literal(this=None, is_string=True),
        ),
        _spec("ADDRESS", policy=exp.Literal(this=None, is_string=True)),
        vexp.LoadBalanceGroupAction(expression=exp.Literal.string("x")),
        _action("UNKNOWN", value=exp.Literal.string("x")),
        _action("SET FILTER"),
        _action("SET FILTER", value=_identifier("x")),
        _action("SET FILTER", member_kind="ADDRESS", value=exp.Literal.string("x")),
        _action("SET FILTER", value=exp.Literal.string("x"), members=("a",)),
        _action("SET POLICY", value=exp.Literal.string("INVALID")),
        _action("SET POLICY", value=exp.Literal(this=None, is_string=True)),
        _action("ADD", members=("a",)),
        _action("ADD", member_kind="UNKNOWN", members=("a",)),
        _action("ADD", member_kind="ADDRESS"),
        _action(
            "DROP",
            member_kind="ADDRESS",
            value=exp.Literal.string("x"),
            members=("a",),
        ),
        vexp.LoadBalanceGroupAction(
            this=exp.var("ADD"),
            member_kind=exp.var("ADDRESS"),
            expressions=[exp.to_table("app.a")],
        ),
        _set_arg(
            _action("ADD", member_kind="ADDRESS", members=("a",)),
            "expressions",
            _identifier("a"),
        ),
    ],
)
def test_programmatic_leaf_nodes_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "name",
    ["", "app.group", "x;DROP_TABLE_y", "white space", "1group"],
)
def test_programmatic_unquoted_identifiers_must_be_safe(name: str) -> None:
    expression = vexp.CreateLoadBalanceGroup(
        this=_identifier(name), kind="LOAD BALANCE GROUP", spec=_spec()
    )
    with pytest.raises(UnsupportedError):
        _strict(expression)


def test_programmatic_quoted_identifiers_can_contain_special_characters() -> None:
    expression = vexp.CreateLoadBalanceGroup(
        this=_identifier("LB.Group", quoted=True),
        kind="LOAD BALANCE GROUP",
        spec=vexp.LoadBalanceGroupSpec(
            this=exp.var("ADDRESS"),
            expressions=[_identifier("Address One", quoted=True)],
        ),
    )
    assert _strict(expression) == (
        'CREATE LOAD BALANCE GROUP "LB.Group" WITH ADDRESS "Address One"'
    )
