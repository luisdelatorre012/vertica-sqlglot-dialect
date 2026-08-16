"""Vertica workload-routing lifecycle and session-control regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _identifier(name: str) -> exp.Identifier:
    return exp.to_identifier(name)


def _target(name: str = "rule", workload: bool = False) -> vexp.RoutingRuleTarget:
    return vexp.RoutingRuleTarget(this=_identifier(name), workload=workload)


def _action(name: str, value: exp.Expr | None = None) -> vexp.RoutingRuleAction:
    return vexp.RoutingRuleAction(this=exp.var(name), expression=value)


def _set_session(name: str, value: exp.Expr) -> vexp.SetSessionRouting:
    assignment = exp.EQ(this=exp.column(name), expression=value)
    return vexp.SetSessionRouting(
        expressions=[exp.SetItem(this=assignment, kind="SESSION")],
        unset=False,
        tag=False,
    )


def _assert_parent_links(expression: exp.Expr) -> None:
    for parent in expression.walk():
        for child in parent.iter_expressions():
            assert child.parent is parent


@pytest.mark.parametrize(
    ("sql", "mode", "name", "destinations", "priority"),
    [
        (
            "CREATE ROUTING RULE client_net ROUTE '192.0.2.0/24' TO reporting",
            "ADDRESS",
            "client_net",
            ["reporting"],
            None,
        ),
        (
            "CREATE ROUTING RULE route ROUTE '2001:db8::/32' TO group_name",
            "ADDRESS",
            "route",
            ["group_name"],
            None,
        ),
        (
            "CREATE ROUTING RULE ROUTE WORKLOAD analytics TO SUBCLUSTER sc1, sc2 PRIORITY 7",
            "WORKLOAD",
            None,
            ["sc1", "sc2"],
            7,
        ),
        (
            "CREATE ROUTING RULE analytic_rule ROUTE WORKLOAD analytics TO SUBCLUSTER "
            "my_subcluster",
            "WORKLOAD",
            "analytic_rule",
            ["my_subcluster"],
            None,
        ),
        (
            'CREATE ROUTING RULE "Routing Rule" ROUTE WORKLOAD "Workload" TO SUBCLUSTER "SC One"',
            "WORKLOAD",
            "Routing Rule",
            ["SC One"],
            None,
        ),
    ],
)
def test_create_routing_rule_forms_are_typed_and_stable(
    sql: str,
    mode: str,
    name: str | None,
    destinations: list[str],
    priority: int | None,
) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.CreateRoutingRule)
    assert expression.kind == "ROUTING RULE"
    assert expression.name == (name or "")

    route = expression.args["route"]
    assert isinstance(route, vexp.RoutingRuleSpec)
    assert route.args["mode"].name == mode
    assert [destination.name for destination in route.expressions] == destinations
    parsed_priority = route.args.get("priority")
    assert (
        int(parsed_priority.this) if isinstance(parsed_priority, exp.Literal) else None
    ) == priority
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "action_type", "action_name"),
    [
        ("ALTER ROUTING RULE r RENAME TO r2", exp.AlterRename, "r2"),
        (
            "ALTER ROUTING RULE r SET ROUTE TO '198.51.100.0/24'",
            vexp.RoutingRuleAction,
            "SET ROUTE",
        ),
        ("ALTER ROUTING RULE r SET GROUP TO readers", vexp.RoutingRuleAction, "SET GROUP"),
        (
            "ALTER ROUTING RULE r SET WORKLOAD TO analytics",
            vexp.RoutingRuleAction,
            "SET WORKLOAD",
        ),
        (
            "ALTER ROUTING RULE FOR WORKLOAD analytics SET SUBCLUSTER TO sc1, sc2",
            vexp.RoutingRuleAction,
            "SET SUBCLUSTER",
        ),
        (
            "ALTER ROUTING RULE FOR WORKLOAD analytics SET PRIORITY TO 0",
            vexp.RoutingRuleAction,
            "SET PRIORITY",
        ),
        (
            "ALTER ROUTING RULE analytic_rule SET PRIORITY TO 1",
            vexp.RoutingRuleAction,
            "SET PRIORITY",
        ),
        (
            "ALTER ROUTING RULE FOR WORKLOAD analytics ADD SUBCLUSTER sc1, sc2",
            vexp.RoutingRuleAction,
            "ADD SUBCLUSTER",
        ),
        (
            "ALTER ROUTING RULE FOR WORKLOAD analytics REMOVE SUBCLUSTER sc2",
            vexp.RoutingRuleAction,
            "REMOVE SUBCLUSTER",
        ),
    ],
)
def test_every_alter_routing_rule_action_is_structured(
    sql: str, action_type: type[exp.Expr], action_name: str
) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.AlterRoutingRule)
    assert isinstance(expression.this, vexp.RoutingRuleTarget)
    assert len(expression.actions) == 1
    action = expression.actions[0]
    assert isinstance(action, action_type)
    assert action.name.upper() == action_name.upper()
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "exists", "workload"),
    [
        ("DROP ROUTING RULE client_net", False, False),
        ("DROP ROUTING RULE IF EXISTS client_net", True, False),
        ("DROP ROUTING RULE FOR WORKLOAD analytics", False, True),
        ("DROP ROUTING RULE IF EXISTS FOR WORKLOAD analytics", True, True),
    ],
)
def test_drop_routing_rule_targets_roundtrip(sql: str, exists: bool, workload: bool) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.DropRoutingRule)
    assert expression.args.get("exists") is exists
    assert isinstance(expression.this, vexp.RoutingRuleTarget)
    assert bool(expression.this.args.get("workload")) is workload
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "expected", "name", "value_type", "value"),
    [
        (
            "SET SESSION WORKLOAD analytics",
            "SET SESSION WORKLOAD TO analytics",
            "WORKLOAD",
            exp.Identifier,
            "analytics",
        ),
        (
            "SET SESSION WORKLOAD TO DEFAULT",
            "SET SESSION WORKLOAD TO DEFAULT",
            "WORKLOAD",
            exp.Var,
            "DEFAULT",
        ),
        (
            "SET SESSION WORKLOAD NONE",
            "SET SESSION WORKLOAD TO NONE",
            "WORKLOAD",
            exp.Var,
            "NONE",
        ),
        (
            'SET SESSION WORKLOAD TO "NONE"',
            'SET SESSION WORKLOAD TO "NONE"',
            "WORKLOAD",
            exp.Identifier,
            "NONE",
        ),
        (
            "SET SESSION RESOURCE_POOL = realtime",
            "SET SESSION RESOURCE_POOL = realtime",
            "RESOURCE_POOL",
            exp.Identifier,
            "realtime",
        ),
        (
            "SET SESSION RESOURCE_POOL = DEFAULT",
            "SET SESSION RESOURCE_POOL = DEFAULT",
            "RESOURCE_POOL",
            exp.Var,
            "DEFAULT",
        ),
        (
            'SET SESSION RESOURCE_POOL = "DEFAULT"',
            'SET SESSION RESOURCE_POOL = "DEFAULT"',
            "RESOURCE_POOL",
            exp.Identifier,
            "DEFAULT",
        ),
    ],
)
def test_set_session_routing_preserves_canonical_set_children(
    sql: str,
    expected: str,
    name: str,
    value_type: type[exp.Expr],
    value: str,
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, vexp.SetSessionRouting)
    assert len(expression.expressions) == 1
    item = expression.expressions[0]
    assert isinstance(item, exp.SetItem)
    assert item.args["kind"] == "SESSION"
    assignment = item.this
    assert isinstance(assignment, exp.EQ)
    assert isinstance(assignment.this, exp.Column)
    assert assignment.this.name == name
    assert isinstance(assignment.expression, value_type)
    assert assignment.expression.name == value
    _assert_parent_links(expression)


@pytest.mark.parametrize(
    ("sql", "available"),
    [("SHOW WORKLOAD", False), ("SHOW AVAILABLE WORKLOADS", True)],
)
def test_show_workload_is_semantic_despite_command_tokenization(sql: str, available: bool) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.ShowWorkload)
    assert expression.this.name == "WORKLOAD"
    assert bool(expression.args.get("available")) is available


@pytest.mark.parametrize(
    ("sql", "expected", "comments"),
    [
        ("SHOW /*inside*/ WORKLOAD", "SHOW WORKLOAD /* inside */", ["inside"]),
        (
            "SHOW AVAILABLE /*inside*/ WORKLOADS",
            "SHOW AVAILABLE WORKLOADS /* inside */",
            ["inside"],
        ),
        ("SHOW\nAVAILABLE\nWORKLOADS", "SHOW AVAILABLE WORKLOADS", []),
        (
            "/*lead*/ SHOW /*inside*/ WORKLOAD /*tail*/",
            "SHOW WORKLOAD /* lead */ /* inside */ /* tail */",
            ["lead", "inside", "tail"],
        ),
        (
            "/*same*/ SHOW /*same*/ WORKLOAD /*same*/",
            "SHOW WORKLOAD /* same */ /* same */ /* same */",
            ["same", "same", "same"],
        ),
    ],
)
def test_show_workload_preserves_comments_and_whitespace(
    sql: str, expected: str, comments: list[str]
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, vexp.ShowWorkload)
    assert expression.comments == comments or (not comments and expression.comments is None)


def test_show_workload_command_boundary_does_not_capture_identifiers() -> None:
    expression = parse_one("SHOW AVAILABLE WORKLOADS_EXTRA", read="vertica")
    assert isinstance(expression, exp.Command)


@pytest.mark.parametrize(
    ("sql", "expected", "statement_type"),
    [
        (
            "GRANT USAGE ON ROUTING RULE analytics TO analyst",
            "GRANT USAGE ON WORKLOAD analytics TO analyst",
            exp.Grant,
        ),
        (
            "REVOKE USAGE ON ROUTING RULE analytics FROM analyst",
            "REVOKE USAGE ON WORKLOAD analytics FROM analyst",
            exp.Revoke,
        ),
        (
            "GRANT USAGE ON WORKLOAD analytics TO analyst",
            "GRANT USAGE ON WORKLOAD analytics TO analyst",
            exp.Grant,
        ),
    ],
)
def test_routing_rule_privilege_alias_normalizes_to_workload(
    sql: str, expected: str, statement_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, statement_type)
    target = expression.args["securable"]
    assert isinstance(target, vexp.VerticaPrivilegeTarget)
    assert target.args["kind"] == "WORKLOAD"
    assert len(target.expressions) == 1


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE ROUTING",
        "CREATE ROUTING RULE",
        "CREATE OR REPLACE ROUTING RULE r ROUTE 'x' TO g",
        "CREATE IF NOT EXISTS ROUTING RULE r ROUTE 'x' TO g",
        "CREATE ROUTING RULE IF NOT EXISTS r ROUTE 'x' TO g",
        "CREATE TEMPORARY ROUTING RULE r ROUTE 'x' TO g",
        "CREATE GLOBAL TEMPORARY ROUTING RULE r ROUTE 'x' TO g",
        "CREATE MATERIALIZED ROUTING RULE r ROUTE 'x' TO g",
        "CREATE UNLOGGED ROUTING RULE r ROUTE 'x' TO g",
        "CREATE TRANSIENT ROUTING RULE r ROUTE 'x' TO g",
        "CREATE VOLATILE ROUTING RULE r ROUTE 'x' TO g",
        "CREATE SECURE ROUTING RULE r ROUTE 'x' TO g",
        "CREATE PRIVATE ROUTING RULE r ROUTE 'x' TO g",
        "CREATE MULTISET ROUTING RULE r ROUTE 'x' TO g",
        "CREATE SET ROUTING RULE r ROUTE 'x' TO g",
        "CREATE ICEBERG ROUTING RULE r ROUTE 'x' TO g",
        "CREATE DYNAMIC ROUTING RULE r ROUTE 'x' TO g",
        "CREATE HYBRID ROUTING RULE r ROUTE 'x' TO g",
        "CREATE OR REFRESH ROUTING RULE r ROUTE 'x' TO g",
        "CREATE NONCLUSTERED COLUMNSTORE ROUTING RULE r ROUTE 'x' TO g",
        "CREATE CONCURRENTLY ROUTING RULE r ROUTE 'x' TO g",
        "CREATE ROUTING RULE ROUTE 'x' TO g",
        "CREATE ROUTING RULE r 'x' TO g",
        "CREATE ROUTING RULE r ROUTE 192 TO g",
        "CREATE ROUTING RULE r ROUTE 'x' g",
        "CREATE ROUTING RULE r ROUTE 'x' TO",
        "CREATE ROUTING RULE r ROUTE 'x' TO app.g",
        "CREATE ROUTING RULE r ROUTE 'x' TO g, h",
        "CREATE ROUTING RULE ROUTE WORKLOAD TO SUBCLUSTER sc",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO sc",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER sc,",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER sc PRIORITY",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER sc PRIORITY -1",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER sc PRIORITY 1.5",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER sc EXTRA",
        "CREATE ROUTING RULE 'r' ROUTE 'x' TO g",
        "CREATE ROUTING RULE 1 ROUTE 'x' TO g",
        "CREATE ROUTING RULE r ROUTE 'x' TO 'g'",
        "CREATE ROUTING RULE ROUTE WORKLOAD NULL TO SUBCLUSTER sc",
        "CREATE ROUTING RULE ROUTE WORKLOAD w TO SUBCLUSTER TRUE, 1",
    ],
)
def test_create_routing_rule_rejects_structural_errors(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER ROUTING",
        "ALTER ROUTING RULE",
        "ALTER ROUTING RULE app.r RENAME TO r2",
        "ALTER ROUTING RULE r",
        "ALTER ROUTING RULE r RENAME",
        "ALTER ROUTING RULE r RENAME x",
        "ALTER ROUTING RULE r RENAME TO",
        "ALTER ROUTING RULE r RENAME TO app.r2",
        "ALTER ROUTING RULE r SET",
        "ALTER ROUTING RULE r SET UNKNOWN TO x",
        "ALTER ROUTING RULE r SET ROUTE x",
        "ALTER ROUTING RULE r SET ROUTE TO x",
        "ALTER ROUTING RULE r SET GROUP readers",
        "ALTER ROUTING RULE r SET GROUP TO",
        "ALTER ROUTING RULE r SET SUBCLUSTER TO",
        "ALTER ROUTING RULE r SET SUBCLUSTER TO sc,",
        "ALTER ROUTING RULE FOR WORKLOAD w SET PRIORITY 1",
        "ALTER ROUTING RULE FOR WORKLOAD w SET PRIORITY TO -1",
        "ALTER ROUTING RULE FOR WORKLOAD w SET PRIORITY TO 1.5",
        "ALTER ROUTING RULE r ADD x",
        "ALTER ROUTING RULE r ADD SUBCLUSTER",
        "ALTER ROUTING RULE r REMOVE SUBCLUSTER sc EXTRA",
        "ALTER ROUTING RULE r RENAME TO r2, SET GROUP TO g",
        "ALTER ONLY ROUTING RULE r RENAME TO r2",
        "ALTER MATERIALIZED ROUTING RULE r RENAME TO r2",
        "ALTER CONCURRENTLY ROUTING RULE r RENAME TO r2",
        "ALTER ROUTING RULE 1 RENAME TO r2",
        "ALTER ROUTING RULE r RENAME TO 'r2'",
    ],
)
def test_alter_routing_rule_rejects_structural_errors(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP ROUTING",
        "DROP ROUTING RULE",
        "DROP IF EXISTS ROUTING RULE r",
        "DROP ROUTING RULE app.r",
        "DROP ROUTING RULE r, r2",
        "DROP ROUTING RULE r CASCADE",
        "DROP ROUTING RULE r RESTRICT",
        "DROP ROUTING RULE r EXTRA",
        "DROP ROUTING RULE IF EXISTS",
        "DROP ROUTING RULE FOR WORKLOAD",
        "DROP TEMPORARY ROUTING RULE r",
        "DROP MATERIALIZED ROUTING RULE r",
        "DROP ICEBERG ROUTING RULE r",
        "DROP CONCURRENTLY ROUTING RULE r",
        "DROP CASCADE ROUTING RULE r",
        "DROP ROUTING RULE FOR",
        "DROP ROUTING RULE 'r'",
        "DROP ROUTING RULE 1",
    ],
)
def test_drop_routing_rule_rejects_structural_errors(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SET SESSION WORKLOAD",
        "SET SESSION WORKLOAD TO",
        "SET SESSION WORKLOAD = analytics",
        "SET SESSION WORKLOAD TO app.analytics",
        "SET SESSION WORKLOAD analytics, reporting",
        "SET SESSION WORKLOAD TO 'analytics'",
        "SET SESSION WORKLOAD TO 1",
        "SET SESSION WORKLOAD TO NULL",
        "SET SESSION WORKLOAD TO TRUE",
        "SET SESSION RESOURCE_POOL",
        "SET SESSION RESOURCE_POOL realtime",
        "SET SESSION RESOURCE_POOL TO realtime",
        "SET SESSION RESOURCE_POOL =",
        "SET SESSION RESOURCE_POOL = NONE",
        "SET SESSION RESOURCE_POOL = app.realtime",
        "SET SESSION RESOURCE_POOL = realtime, batch",
        "SET SESSION RESOURCE_POOL = 'realtime'",
        "SET SESSION RESOURCE_POOL = 1.5",
        "SET SESSION RESOURCE_POOL = FALSE",
        "SHOW WORKLOAD EXTRA",
        "SHOW AVAILABLE WORKLOAD",
        "SHOW AVAILABLE WORKLOADS EXTRA",
    ],
)
def test_session_workload_commands_reject_wrong_operators_and_shape(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "GRANT SELECT ON ROUTING RULE analytics TO analyst",
        "GRANT USAGE ON ROUTING RULE analytics, reporting TO analyst",
        "GRANT USAGE ON ROUTING RULE analytics TO analyst, reader",
        "GRANT USAGE ON ROUTING RULE analytics TO analyst WITH GRANT OPTION",
        "REVOKE GRANT OPTION FOR USAGE ON ROUTING RULE analytics FROM analyst",
        "REVOKE USAGE ON ROUTING RULE analytics FROM analyst CASCADE",
        "GRANT USAGE ON ROUTING analytics TO analyst",
        "GRANT USAGE, USAGE ON ROUTING RULE analytics TO analyst",
        "GRANT USAGE ON ROUTING RULE app.analytics TO analyst",
        "REVOKE USAGE ON WORKLOAD db.app.analytics FROM analyst",
    ],
)
def test_routing_rule_privilege_alias_keeps_workload_invariants(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE ROUTING RULE r ROUTE 'x' TO g",
        "ALTER ROUTING RULE r RENAME TO r2",
        "DROP ROUTING RULE r",
        "SET SESSION WORKLOAD TO analytics",
        "SHOW WORKLOAD",
    ],
)
def test_workload_routing_roots_fail_atomically_in_foreign_dialects(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.RoutingRuleSpec(
            mode=exp.var("WORKLOAD"),
            this=_identifier("w"),
            expressions=[_identifier("sc")],
        ),
        _target(),
        _action("SET GROUP", _identifier("g")),
    ],
)
def test_workload_routing_leaf_nodes_fail_in_foreign_dialects(expression: exp.Expr) -> None:
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_workload_routing_ast_generates_valid_sql() -> None:
    route = vexp.RoutingRuleSpec(
        mode=exp.var("WORKLOAD"),
        this=_identifier("analytics"),
        expressions=[_identifier("sc1"), _identifier("sc2")],
        priority=exp.Literal.number(3),
    )
    create = vexp.CreateRoutingRule(kind="ROUTING RULE", route=route)
    alter = vexp.AlterRoutingRule(
        this=_target("analytics", workload=True),
        kind="ROUTING RULE",
        actions=[
            vexp.RoutingRuleAction(
                this=exp.var("SET SUBCLUSTER"),
                expressions=[_identifier("sc1"), _identifier("sc2")],
            )
        ],
    )
    drop = vexp.DropRoutingRule(
        this=_target("analytics", workload=True), kind="ROUTING RULE", exists=True
    )

    assert _strict(create) == (
        "CREATE ROUTING RULE ROUTE WORKLOAD analytics TO SUBCLUSTER sc1, sc2 PRIORITY 3"
    )
    assert _strict(alter) == (
        "ALTER ROUTING RULE FOR WORKLOAD analytics SET SUBCLUSTER TO sc1, sc2"
    )
    assert _strict(drop) == "DROP ROUTING RULE IF EXISTS FOR WORKLOAD analytics"
    assert _strict(_set_session("WORKLOAD", exp.var("NONE"))) == ("SET SESSION WORKLOAD TO NONE")
    assert _strict(vexp.ShowWorkload(this=exp.var("WORKLOAD"), available=True)) == (
        "SHOW AVAILABLE WORKLOADS"
    )


@pytest.mark.parametrize(
    "sql",
    ["SET SESSION WORKLOAD analytics", "SET SESSION RESOURCE_POOL = realtime"],
)
def test_set_session_routing_survives_optimizer_identifier_normalization(sql: str) -> None:
    optimized = optimize(parse_one(sql, read="vertica"), dialect="vertica")
    assert isinstance(optimized, vexp.SetSessionRouting)
    generated = _strict(optimized)
    assert isinstance(parse_one(generated, read="vertica"), vexp.SetSessionRouting)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.CreateRoutingRule(kind="TABLE"),
        vexp.CreateRoutingRule(kind="ROUTING RULE", replace=True),
        vexp.CreateRoutingRule(this=exp.to_table("app.r"), kind="ROUTING RULE"),
        vexp.CreateRoutingRule(this=_identifier("r"), kind="ROUTING RULE"),
        vexp.CreateRoutingRule(
            kind="ROUTING RULE",
            route=vexp.RoutingRuleSpec(
                mode=exp.var("ADDRESS"),
                this=exp.Literal.string("x"),
                expressions=[_identifier("g")],
            ),
        ),
        vexp.AlterRoutingRule(this=_target(), kind="TABLE", actions=[]),
        vexp.AlterRoutingRule(this=_target(), kind="ROUTING RULE", actions=[]),
        vexp.AlterRoutingRule(
            this=_target(),
            kind="ROUTING RULE",
            actions=[
                exp.AlterRename(this=_identifier("x")),
                _action("SET GROUP", _identifier("g")),
            ],
        ),
        vexp.AlterRoutingRule(
            this=_identifier("r"),
            kind="ROUTING RULE",
            actions=[exp.AlterRename(this=_identifier("x"))],
        ),
        vexp.AlterRoutingRule(
            this=_target(), kind="ROUTING RULE", actions=[exp.Drop(this=_identifier("x"))]
        ),
        vexp.DropRoutingRule(this=_target(), kind="TABLE"),
        vexp.DropRoutingRule(this=_identifier("r"), kind="ROUTING RULE"),
        vexp.DropRoutingRule(this=_target(), kind="ROUTING RULE", cascade=True),
        vexp.DropRoutingRule(this=_target(), kind="ROUTING RULE", exists="yes"),
    ],
)
def test_programmatic_routing_statement_roots_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.RoutingRuleSpec(
            mode=exp.var("UNKNOWN"), this=_identifier("w"), expressions=[_identifier("sc")]
        ),
        vexp.RoutingRuleSpec(
            mode=exp.var("ADDRESS"), this=_identifier("x"), expressions=[_identifier("g")]
        ),
        vexp.RoutingRuleSpec(mode=exp.var("ADDRESS"), this=exp.Literal.string("x"), expressions=[]),
        vexp.RoutingRuleSpec(
            mode=exp.var("ADDRESS"),
            this=exp.Literal.string("x"),
            expressions=[_identifier("g")],
            priority=exp.Literal.number(1),
        ),
        vexp.RoutingRuleSpec(
            mode=exp.var("WORKLOAD"), this=exp.Literal.string("w"), expressions=[]
        ),
        vexp.RoutingRuleSpec(
            mode=exp.var("WORKLOAD"),
            this=_identifier("w"),
            expressions=[exp.to_table("app.sc")],
        ),
        vexp.RoutingRuleSpec(
            mode=exp.var("WORKLOAD"),
            this=_identifier("w"),
            expressions=[_identifier("sc")],
            priority=exp.Literal.number(-1),
        ),
        vexp.RoutingRuleTarget(this=exp.to_table("app.r")),
        vexp.RoutingRuleTarget(this=_identifier("r"), workload="yes"),
        vexp.RoutingRuleAction(this=_identifier("SET GROUP"), expression=_identifier("g")),
        vexp.RoutingRuleAction(this=exp.var("SET GROUP")),
        vexp.RoutingRuleAction(this=exp.var("SET ROUTE"), expression=_identifier("x")),
        vexp.RoutingRuleAction(this=exp.var("SET PRIORITY"), expression=exp.Literal.number(-1)),
        vexp.RoutingRuleAction(this=exp.var("SET SUBCLUSTER"), expression=_identifier("sc")),
        vexp.RoutingRuleAction(this=exp.var("ADD SUBCLUSTER"), expressions=[]),
        vexp.RoutingRuleAction(
            this=exp.var("REMOVE SUBCLUSTER"), expressions=[exp.to_table("app.sc")]
        ),
        vexp.RoutingRuleAction(this=exp.var("UNKNOWN"), expression=_identifier("x")),
    ],
)
def test_programmatic_routing_leaf_nodes_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "expression",
    [
        vexp.SetSessionRouting(expressions=[]),
        vexp.SetSessionRouting(expressions=[exp.var("x")]),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(this=exp.EQ(this=exp.column("WORKLOAD"), expression=_identifier("w")))
            ]
        ),
        vexp.SetSessionRouting(expressions=[exp.SetItem(this=exp.var("x"), kind="SESSION")]),
        _set_session("OTHER", _identifier("x")),
        _set_session("WORKLOAD", exp.Literal.string("x")),
        _set_session("RESOURCE_POOL", exp.var("NONE")),
        _set_session("RESOURCE_POOL", _identifier("NONE")),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(
                    this=exp.EQ(
                        this=exp.Column(this=exp.to_identifier("OTHER", quoted=True)),
                        expression=_identifier("w"),
                    ),
                    kind="SESSION",
                )
            ]
        ),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(
                    this=exp.EQ(
                        this=exp.column("WORKLOAD", table="s"), expression=_identifier("w")
                    ),
                    kind="SESSION",
                )
            ]
        ),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(
                    this=exp.EQ(this=exp.column("WORKLOAD"), expression=_identifier("w")),
                    kind="SESSION",
                )
            ],
            unset=True,
        ),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(
                    this=exp.EQ(this=exp.column("WORKLOAD"), expression=_identifier("w")),
                    kind="SESSION",
                )
            ],
            unset=0,
        ),
        vexp.SetSessionRouting(
            expressions=[
                exp.SetItem(
                    this=exp.EQ(this=exp.column("WORKLOAD"), expression=_identifier("w")),
                    kind="SESSION",
                )
            ],
            tag="",
        ),
        vexp.ShowWorkload(this=exp.var("OTHER")),
        vexp.ShowWorkload(this=exp.var("WORKLOAD"), available="yes"),
        vexp.ShowWorkload(this=exp.var("WORKLOAD"), where=exp.true()),
    ],
)
def test_programmatic_session_roots_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)


@pytest.mark.parametrize(
    "identifier",
    [
        exp.Identifier(this=""),
        exp.Identifier(this="app.rule"),
        exp.Identifier(this="1rule"),
        exp.Identifier(this="x; DROP TABLE y"),
    ],
)
def test_programmatic_routing_identifiers_must_be_nonempty_and_safely_quoted(
    identifier: exp.Identifier,
) -> None:
    expressions: list[exp.Expr] = [
        vexp.CreateRoutingRule(
            this=identifier.copy(),
            kind="ROUTING RULE",
            route=vexp.RoutingRuleSpec(
                mode=exp.var("ADDRESS"),
                this=exp.Literal.string("x"),
                expressions=[_identifier("g")],
            ),
        ),
        vexp.RoutingRuleSpec(
            mode=exp.var("WORKLOAD"),
            this=identifier.copy(),
            expressions=[_identifier("sc")],
        ),
        vexp.RoutingRuleTarget(this=identifier.copy()),
        _action("SET GROUP", identifier.copy()),
        _set_session("WORKLOAD", identifier.copy()),
    ]
    for expression in expressions:
        with pytest.raises(UnsupportedError):
            _strict(expression)


def test_programmatic_quoted_routing_identifiers_are_escaped_safely() -> None:
    unusual = exp.Identifier(this='x"; DROP TABLE y', quoted=True)
    expression = vexp.DropRoutingRule(
        this=vexp.RoutingRuleTarget(this=unusual), kind="ROUTING RULE"
    )
    assert _strict(expression) == 'DROP ROUTING RULE "x""; DROP TABLE y"'


def _workload_target(
    target: exp.Expr | None = None, **kwargs: object
) -> vexp.VerticaPrivilegeTarget:
    return vexp.VerticaPrivilegeTarget(
        kind="WORKLOAD",
        expressions=[target or exp.to_table("analytics")],
        **kwargs,
    )


def _workload_grant(
    *,
    privileges: list[exp.Expr] | None = None,
    target: vexp.VerticaPrivilegeTarget | None = None,
    principals: list[exp.Expr] | None = None,
    **kwargs: object,
) -> exp.Grant:
    grant_option = kwargs.pop("grant_option", False)
    return exp.Grant(
        privileges=(
            privileges if privileges is not None else [exp.GrantPrivilege(this=exp.var("USAGE"))]
        ),
        securable=target or _workload_target(),
        principals=(
            principals
            if principals is not None
            else [exp.GrantPrincipal(this=_identifier("analyst"))]
        ),
        grant_option=grant_option,
        **kwargs,
    )


@pytest.mark.parametrize(
    "expression",
    [
        _workload_grant(privileges=[]),
        _workload_grant(privileges=[exp.GrantPrivilege(this=exp.var("SELECT"))]),
        _workload_grant(
            privileges=[
                exp.GrantPrivilege(this=exp.var("USAGE")),
                exp.GrantPrivilege(this=exp.var("USAGE")),
            ]
        ),
        _workload_grant(
            privileges=[exp.GrantPrivilege(this=exp.var("USAGE"), expressions=[exp.column("x")])]
        ),
        _workload_grant(target=_workload_target(exp.to_table("app.analytics"))),
        _workload_grant(
            target=_workload_target(
                exp.Table(
                    this=_identifier("analytics"),
                    alias=exp.TableAlias(this=_identifier("w")),
                )
            )
        ),
        _workload_grant(
            target=vexp.VerticaPrivilegeTarget(
                kind="WORKLOAD", expressions=[_identifier("analytics")]
            )
        ),
        _workload_grant(target=_workload_target(subcluster=_identifier("sc"))),
        _workload_grant(principals=[]),
        _workload_grant(
            principals=[
                exp.GrantPrincipal(this=_identifier("a")),
                exp.GrantPrincipal(this=_identifier("b")),
            ]
        ),
        _workload_grant(principals=[exp.GrantPrincipal(this=exp.to_table("app.analyst"))]),
        _workload_grant(kind="TABLE"),
        _workload_grant(grant_option=True),
        _workload_grant(unknown=True),
        _workload_grant(
            target=vexp.VerticaPrivilegeTarget(
                kind="ROUTING RULE", expressions=[exp.to_table("analytics")]
            )
        ),
        _workload_grant(
            target=vexp.VerticaPrivilegeTarget(
                kind="workload", expressions=[exp.to_table("analytics")]
            )
        ),
        _workload_grant(
            target=vexp.VerticaPrivilegeTarget(
                kind="WORKLOAD ", expressions=[exp.to_table("analytics")]
            )
        ),
        _workload_grant(
            target=vexp.VerticaPrivilegeTarget(
                kind=exp.var("WORKLOAD"), expressions=[exp.to_table("analytics")]
            )
        ),
        exp.Revoke(
            privileges=[exp.GrantPrivilege(this=exp.var("USAGE"))],
            securable=_workload_target(),
            principals=[exp.GrantPrincipal(this=_identifier("analyst"))],
            grant_option=False,
            cascade="CASCADE",
        ),
    ],
)
def test_programmatic_workload_privileges_are_guarded(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _strict(expression)
