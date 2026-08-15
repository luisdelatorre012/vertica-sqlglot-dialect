"""Vertica role and resource-pool lifecycle regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _keyword(name: str, quoted: bool = False) -> vexp.ResourcePoolKeyword:
    return vexp.ResourcePoolKeyword(this=exp.var(name), quoted=quoted)


def _parameter(name: str, value: exp.Expr) -> vexp.ResourcePoolParameter:
    return vexp.ResourcePoolParameter(this=exp.var(name), value=value)


def _create_pool(*parameters: vexp.ResourcePoolParameter) -> vexp.CreateResourcePool:
    return vexp.CreateResourcePool(
        this=exp.to_identifier("rp"),
        kind="RESOURCE POOL",
        properties=exp.Properties(expressions=list(parameters)) if parameters else None,
    )


def _generate_strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_role_lifecycle_uses_canonical_roots() -> None:
    create = assert_roundtrip("CREATE ROLE analyst")
    alter = assert_roundtrip("ALTER ROLE analyst RENAME TO reporting")
    drop = assert_roundtrip("DROP ROLE IF EXISTS analyst CASCADE")

    assert type(create) is exp.Create
    assert create.kind == "ROLE"
    assert isinstance(create.this, exp.Identifier)
    assert type(alter) is exp.Alter
    assert alter.kind == "ROLE"
    assert isinstance(alter.actions[0], exp.AlterRename)
    assert alter.actions[0].parent is alter
    assert type(drop) is exp.Drop
    assert drop.kind == "ROLE"
    assert drop.args["exists"] is True
    assert drop.args["cascade"] is True


def test_multi_role_drop_has_atomic_custom_root() -> None:
    sql = 'DROP ROLE IF EXISTS analyst, reader, "Sales Role" CASCADE'
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.DropRoles)
    assert expression.name == "analyst"
    assert [role.name for role in expression.expressions] == ["reader", "Sales Role"]
    assert all(role.parent is expression for role in expression.expressions)

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_canonical_role_roots_generate_in_postgres() -> None:
    statements = [
        "CREATE ROLE analyst",
        "ALTER ROLE analyst RENAME TO reporting",
        "DROP ROLE IF EXISTS analyst CASCADE",
    ]
    for sql in statements:
        expression = parse_one(sql, read="vertica")
        assert expression.sql(dialect="postgres") == sql


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("CREATE ROLE", "requires an unqualified name"),
        ("CREATE OR REPLACE ROLE r", "OR REPLACE ROLE"),
        ("CREATE ROLE IF NOT EXISTS r", "does not support IF NOT EXISTS"),
        ("CREATE ROLE app.reader", "cannot be schema-qualified"),
        ("CREATE ROLE r EXTRA", "Unexpected CREATE ROLE clause"),
        ("ALTER ROLE", "requires an unqualified name"),
        ("ALTER ROLE r", "requires RENAME TO"),
        ("ALTER ROLE r RENAME", "RENAME requires TO"),
        ("ALTER ROLE r RENAME TO", "requires an unqualified name"),
        ("ALTER ROLE app.r RENAME TO x", "cannot be schema-qualified"),
        ("ALTER ROLE r RENAME TO app.x", "cannot be schema-qualified"),
        ("ALTER ROLE r RENAME TO x CASCADE", "Unexpected ALTER ROLE clause"),
        ("DROP ROLE", "requires an unqualified name"),
        ("DROP ROLE app.r", "cannot be schema-qualified"),
        ("DROP ROLE r,", "requires a name after each comma"),
        ("DROP ROLE r RESTRICT", "does not support RESTRICT"),
        ("DROP ROLE r CASCADE, x", "Unexpected DROP ROLE clause"),
    ],
)
def test_role_lifecycle_rejects_invalid_scope_and_options(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "expression",
    [
        exp.Create(this=exp.to_table("app.r"), kind="ROLE"),
        exp.Create(this=exp.to_identifier("r"), kind="ROLE", exists=True),
        exp.Alter(this=exp.to_identifier("r"), kind="ROLE", actions=[]),
        exp.Alter(
            this=exp.to_table("app.r"),
            kind="ROLE",
            actions=[exp.AlterRename(this=exp.to_identifier("r2"))],
        ),
        exp.Alter(
            this=exp.to_identifier("r"),
            kind="ROLE",
            actions=[exp.AlterRename(this=exp.to_table("app.r2"))],
        ),
        exp.Alter(
            this=exp.to_identifier("r"),
            kind="ROLE",
            actions=[exp.AlterRename(this=exp.to_identifier("r2"))],
            cascade=True,
        ),
        exp.Drop(this=exp.to_table("app.r"), kind="ROLE"),
        exp.Drop(this=exp.to_identifier("r"), kind="ROLE", restrict=True),
        exp.Drop(this=exp.to_identifier("r"), kind="ROLE", purge=True),
        exp.Drop(
            this=exp.to_identifier("r"),
            expressions=[exp.to_identifier("r2")],
            kind="ROLE",
        ),
        vexp.DropRoles(this=exp.to_identifier("r"), kind="ROLE"),
    ],
)
def test_programmatic_role_ast_rejects_invalid_shapes(expression: exp.Expr) -> None:
    with pytest.raises(UnsupportedError):
        _generate_strict(expression)


def test_create_resource_pool_full_parameter_surface() -> None:
    sql = (
        "CREATE RESOURCE POOL rp FOR CURRENT SUBCLUSTER "
        "CASCADE TO spill "
        "CPUAFFINITYSET '0-3' CPUAFFINITYMODE EXCLUSIVE "
        "EXECUTIONPARALLELISM AUTO MAXCONCURRENCY NONE "
        "MAXMEMORYSIZE '20G' MAXQUERYMEMORYSIZE '25%' MEMORYSIZE '10G' "
        "PLANNEDCONCURRENCY 4 PRIORITY -10 QUEUETIMEOUT '5 minutes' "
        "RUNTIMECAP NONE RUNTIMEPRIORITY HIGH RUNTIMEPRIORITYTHRESHOLD 3 "
        "SINGLEINITIATOR FALSE"
    )
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateResourcePool)
    assert expression.kind == "RESOURCE POOL"
    assert isinstance(expression.this, exp.Identifier)
    subcluster = expression.args["subcluster"]
    assert isinstance(subcluster, vexp.ResourcePoolSubcluster)
    assert subcluster.args["current"] is True
    assert subcluster.parent is expression

    properties = expression.args["properties"]
    assert isinstance(properties, exp.Properties)
    assert properties.parent is expression
    parameters = properties.expressions
    assert [parameter.name for parameter in parameters] == [
        "CASCADE TO",
        "CPUAFFINITYSET",
        "CPUAFFINITYMODE",
        "EXECUTIONPARALLELISM",
        "MAXCONCURRENCY",
        "MAXMEMORYSIZE",
        "MAXQUERYMEMORYSIZE",
        "MEMORYSIZE",
        "PLANNEDCONCURRENCY",
        "PRIORITY",
        "QUEUETIMEOUT",
        "RUNTIMECAP",
        "RUNTIMEPRIORITY",
        "RUNTIMEPRIORITYTHRESHOLD",
        "SINGLEINITIATOR",
    ]
    assert all(isinstance(parameter, vexp.ResourcePoolParameter) for parameter in parameters)
    assert all(parameter.parent is properties for parameter in parameters)
    assert all(parameter.args["value"].parent is parameter for parameter in parameters)
    assert "\nCPUAFFINITYSET" in expression.sql(dialect="vertica", pretty=True)


def test_resource_pool_minimal_and_subcluster_targets() -> None:
    create = assert_roundtrip("CREATE RESOURCE POOL rp")
    named = assert_roundtrip("CREATE RESOURCE POOL rp FOR SUBCLUSTER analytics MEMORYSIZE '10G'")
    alter = assert_roundtrip("ALTER RESOURCE POOL rp FOR CURRENT SUBCLUSTER MEMORYSIZE '20%'")
    drop_global = assert_roundtrip("DROP RESOURCE POOL rp")
    drop_named = assert_roundtrip("DROP RESOURCE POOL rp FOR SUBCLUSTER analytics")
    drop_current = assert_roundtrip("DROP RESOURCE POOL rp FOR CURRENT SUBCLUSTER")

    assert isinstance(create, vexp.CreateResourcePool)
    assert create.args.get("properties") is None
    assert isinstance(named.args["subcluster"].this, exp.Identifier)
    assert isinstance(alter, vexp.AlterResourcePool)
    assert len(alter.actions) == 1
    assert alter.actions[0].parent is alter
    assert isinstance(drop_global, vexp.DropResourcePool)
    assert isinstance(drop_named.args["subcluster"], vexp.ResourcePoolSubcluster)
    assert drop_current.args["subcluster"].args["current"] is True


@pytest.mark.parametrize(
    ("clauses", "expected"),
    [
        ("CPUAFFINITYSET '0,2,4' CPUAFFINITYMODE SHARED", None),
        ("CPUAFFINITYSET '0-7' CPUAFFINITYMODE EXCLUSIVE", None),
        ("CPUAFFINITYSET '50%' CPUAFFINITYMODE SHARED", None),
        ("CPUAFFINITYSET NONE CPUAFFINITYMODE ANY", None),
        ("EXECUTIONPARALLELISM 0", None),
        ("EXECUTIONPARALLELISM 8", None),
        ("EXECUTIONPARALLELISM auto", "EXECUTIONPARALLELISM AUTO"),
        ("MAXCONCURRENCY 12", None),
        ("MAXCONCURRENCY none", "MAXCONCURRENCY NONE"),
        ("MAXMEMORYSIZE NONE", None),
        ("MAXMEMORYSIZE '20g'", None),
        ("MAXQUERYMEMORYSIZE NONE", None),
        ("MAXQUERYMEMORYSIZE '25%'", None),
        ("MEMORYSIZE '1024M'", None),
        ("PLANNEDCONCURRENCY AUTO", None),
        ("PLANNEDCONCURRENCY 1", None),
        ("PRIORITY HOLD", None),
        ("PRIORITY -100", None),
        ("PRIORITY +100", "PRIORITY 100"),
        ("QUEUETIMEOUT 0", None),
        ("QUEUETIMEOUT '01:30:00'", None),
        ("QUEUETIMEOUT 'none'", "QUEUETIMEOUT 'NONE'"),
        ("RUNTIMECAP NONE", None),
        ("RUNTIMECAP '3 minutes'", None),
        ("RUNTIMEPRIORITY LOW", None),
        ("RUNTIMEPRIORITY MEDIUM", None),
        ("RUNTIMEPRIORITY HIGH", None),
        ("RUNTIMEPRIORITYTHRESHOLD 0", None),
        ("SINGLEINITIATOR TRUE", None),
        ("SINGLEINITIATOR FALSE", None),
        ("CASCADE TO spill", None),
    ],
)
def test_resource_pool_create_parameter_domains(clauses: str, expected: str | None) -> None:
    expected_sql = f"CREATE RESOURCE POOL rp {expected or clauses}"
    assert_roundtrip(f"CREATE RESOURCE POOL rp {clauses}", expected_sql)


def test_alter_resource_pool_accepts_default_for_every_parameter() -> None:
    sql = (
        "ALTER RESOURCE POOL rp "
        "CASCADE TO DEFAULT "
        "CPUAFFINITYSET DEFAULT CPUAFFINITYMODE DEFAULT "
        "EXECUTIONPARALLELISM DEFAULT MAXCONCURRENCY DEFAULT "
        "MAXMEMORYSIZE DEFAULT MAXQUERYMEMORYSIZE DEFAULT MEMORYSIZE DEFAULT "
        "PLANNEDCONCURRENCY DEFAULT PRIORITY DEFAULT QUEUETIMEOUT DEFAULT "
        "RUNTIMECAP DEFAULT RUNTIMEPRIORITY DEFAULT "
        "RUNTIMEPRIORITYTHRESHOLD DEFAULT SINGLEINITIATOR DEFAULT"
    )
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.AlterResourcePool)
    assert len(expression.actions) == 15
    assert all(
        isinstance(parameter.args["value"], vexp.ResourcePoolKeyword)
        and parameter.args["value"].name == "DEFAULT"
        for parameter in expression.actions
    )


def test_resource_pool_parameter_order_is_preserved() -> None:
    sql = "CREATE RESOURCE POOL rp PRIORITY 5 MEMORYSIZE '1G' MAXCONCURRENCY 2"
    expression = assert_roundtrip(sql)
    properties = expression.args["properties"]
    assert [parameter.name for parameter in properties.expressions] == [
        "PRIORITY",
        "MEMORYSIZE",
        "MAXCONCURRENCY",
    ]


def test_resource_pool_keyword_nodes_preserve_quoted_none_semantics() -> None:
    expression = assert_roundtrip("CREATE RESOURCE POOL rp MAXMEMORYSIZE NONE QUEUETIMEOUT 'NONE'")
    parameters = expression.args["properties"].expressions
    bare_none = parameters[0].args["value"]
    quoted_none = parameters[1].args["value"]

    assert isinstance(bare_none, vexp.ResourcePoolKeyword)
    assert bare_none.args["quoted"] is False
    assert isinstance(quoted_none, vexp.ResourcePoolKeyword)
    assert quoted_none.args["quoted"] is True
    assert quoted_none.this.parent is quoted_none


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE RESOURCE POOL rp",
        "CREATE RESOURCE POOL rp FOR SUBCLUSTER analytics MEMORYSIZE '1G'",
        "ALTER RESOURCE POOL rp PRIORITY HOLD",
        "DROP RESOURCE POOL rp FOR CURRENT SUBCLUSTER",
    ],
)
def test_resource_pool_roots_fail_atomically_in_foreign_dialects(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("CREATE RESOURCE POOL", "requires an unqualified name"),
        ("CREATE OR REPLACE RESOURCE POOL rp", "OR REPLACE RESOURCE POOL"),
        ("CREATE RESOURCE POOL IF NOT EXISTS rp", "does not support IF NOT EXISTS"),
        ("CREATE RESOURCE POOL app.rp", "cannot be schema-qualified"),
        (
            "CREATE RESOURCE POOL rp MEMORYSIZE '1G' FOR SUBCLUSTER sc",
            "selector must precede parameters",
        ),
        ("CREATE RESOURCE POOL rp FOR", "requires SUBCLUSTER or CURRENT SUBCLUSTER"),
        ("CREATE RESOURCE POOL rp FOR CURRENT", "FOR CURRENT requires SUBCLUSTER"),
        ("CREATE RESOURCE POOL rp FOR SUBCLUSTER", "requires an unqualified name"),
        (
            "CREATE RESOURCE POOL rp FOR SUBCLUSTER app.sc",
            "cannot be schema-qualified",
        ),
        ("CREATE RESOURCE POOL rp UNKNOWN 1", "Unsupported RESOURCE POOL parameter"),
        (
            "CREATE RESOURCE POOL rp MEMORYSIZE '1G', PRIORITY 1",
            "spaces, not commas",
        ),
        (
            "CREATE RESOURCE POOL rp PRIORITY 1 PRIORITY 2",
            "Duplicate RESOURCE POOL parameter PRIORITY",
        ),
        ("CREATE RESOURCE POOL rp CASCADE", "CASCADE requires TO"),
        ("CREATE RESOURCE POOL rp CASCADE TO DEFAULT", "DEFAULT values are only valid"),
        ("CREATE RESOURCE POOL rp MEMORYSIZE DEFAULT", "DEFAULT values are only valid"),
        ("CREATE RESOURCE POOL rp CPUAFFINITYSET NONE", "must be set together"),
        ("CREATE RESOURCE POOL rp CPUAFFINITYMODE ANY", "must be set together"),
        (
            "CREATE RESOURCE POOL rp CPUAFFINITYSET '0-3' CPUAFFINITYMODE ANY",
            "ANY requires CPUAFFINITYSET NONE",
        ),
        (
            "CREATE RESOURCE POOL rp CPUAFFINITYSET 'cpu0' CPUAFFINITYMODE SHARED",
            "quoted CPU list",
        ),
        (
            "CREATE RESOURCE POOL rp CPUAFFINITYSET NONE CPUAFFINITYMODE INVALID",
            "requires one of",
        ),
        ("CREATE RESOURCE POOL rp EXECUTIONPARALLELISM -1", "must be at least 0"),
        ("CREATE RESOURCE POOL rp EXECUTIONPARALLELISM 'AUTO'", "requires an integer"),
        ("CREATE RESOURCE POOL rp MAXCONCURRENCY -1", "must be at least 0"),
        ("CREATE RESOURCE POOL rp MAXMEMORYSIZE 'NONE'", "quoted integer percentage"),
        ("CREATE RESOURCE POOL rp MEMORYSIZE NONE", "requires a string literal"),
        ("CREATE RESOURCE POOL rp MEMORYSIZE '1.5G'", "quoted integer percentage"),
        ("CREATE RESOURCE POOL rp PLANNEDCONCURRENCY 0", "must be at least 1"),
        ("CREATE RESOURCE POOL rp PRIORITY -101", "must be at least -100"),
        ("CREATE RESOURCE POOL rp PRIORITY 101", "must be at most 100"),
        ("CREATE RESOURCE POOL rp QUEUETIMEOUT NONE", "requires an integer"),
        ("CREATE RESOURCE POOL rp QUEUETIMEOUT -1", "must be at least 0"),
        ("CREATE RESOURCE POOL rp RUNTIMECAP AUTO", "requires a string literal"),
        ("CREATE RESOURCE POOL rp RUNTIMEPRIORITY URGENT", "requires one of"),
        (
            "CREATE RESOURCE POOL rp RUNTIMEPRIORITYTHRESHOLD -1",
            "must be at least 0",
        ),
        ("CREATE RESOURCE POOL rp SINGLEINITIATOR 1", "requires TRUE or FALSE"),
        ("ALTER RESOURCE POOL rp", "requires at least one parameter"),
        ("ALTER RESOURCE POOL rp PRIORITY 101", "must be at most 100"),
        ("ALTER RESOURCE POOL SYSQUERY PRIORITY 111", "must be at most 110"),
        ("DROP RESOURCE POOL", "requires an unqualified name"),
        ("DROP RESOURCE POOL IF EXISTS rp", "does not support IF EXISTS"),
        ("DROP RESOURCE POOL app.rp", "cannot be schema-qualified"),
        ("DROP RESOURCE POOL rp, other", "accepts exactly one pool"),
        ("DROP RESOURCE POOL rp CASCADE", "does not support CASCADE or RESTRICT"),
        ("DROP RESOURCE POOL rp RESTRICT", "does not support CASCADE or RESTRICT"),
        ("DROP RESOURCE POOL rp FOR CURRENT", "FOR CURRENT requires SUBCLUSTER"),
    ],
)
def test_resource_pool_rejects_malformed_or_conflicting_syntax(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


def test_programmatic_resource_pool_roots_validate_statement_shape() -> None:
    invalid_roots: list[exp.Expr] = [
        vexp.CreateResourcePool(this=exp.to_identifier("rp"), kind="TABLE"),
        vexp.CreateResourcePool(this=exp.to_table("app.rp"), kind="RESOURCE POOL"),
        vexp.CreateResourcePool(this=exp.to_identifier("rp"), kind="RESOURCE POOL", exists=True),
        vexp.CreateResourcePool(
            this=exp.to_identifier("rp"),
            kind="RESOURCE POOL",
            properties=exp.Properties(expressions=[exp.Property(this="x", value="y")]),
        ),
        vexp.AlterResourcePool(this=exp.to_identifier("rp"), kind="RESOURCE POOL", actions=[]),
        vexp.AlterResourcePool(
            this=exp.to_identifier("rp"),
            kind="RESOURCE POOL",
            actions=[_parameter("PRIORITY", exp.Literal.number(1))],
            cascade=True,
        ),
        vexp.DropResourcePool(this=exp.to_identifier("rp"), kind="RESOURCE POOL", exists=True),
        vexp.DropResourcePool(
            this=exp.to_identifier("rp"),
            expressions=[exp.to_identifier("other")],
            kind="RESOURCE POOL",
        ),
        vexp.DropResourcePool(this=exp.to_identifier("rp"), kind="RESOURCE POOL", restrict=True),
        vexp.DropResourcePool(this=exp.to_identifier("rp"), kind="RESOURCE POOL", purge=True),
        vexp.DropResourcePool(
            this=exp.to_identifier("rp"),
            kind="RESOURCE POOL",
            subcluster=vexp.ResourcePoolSubcluster(),
        ),
        vexp.DropResourcePool(
            this=exp.to_identifier("rp"),
            kind="RESOURCE POOL",
            subcluster=vexp.ResourcePoolSubcluster(this=exp.to_identifier("sc"), current=True),
        ),
        vexp.DropResourcePool(
            this=exp.to_identifier("rp"),
            kind="RESOURCE POOL",
            subcluster=vexp.ResourcePoolSubcluster(this=exp.to_table("app.sc")),
        ),
    ]
    for expression in invalid_roots:
        with pytest.raises(UnsupportedError):
            _generate_strict(expression)


@pytest.mark.parametrize(
    "parameters",
    [
        [_parameter("UNKNOWN", exp.Literal.number(1))],
        [_parameter("CASCADE TO", exp.Literal.string("spill"))],
        [
            _parameter("PRIORITY", exp.Literal.number(1)),
            _parameter("PRIORITY", exp.Literal.number(2)),
        ],
        [_parameter("MEMORYSIZE", _keyword("DEFAULT"))],
        [_parameter("MEMORYSIZE", _keyword("NONE"))],
        [_parameter("MEMORYSIZE", exp.Literal.string("1.5G"))],
        [_parameter("CPUAFFINITYSET", _keyword("NONE"))],
        [
            _parameter("CPUAFFINITYSET", exp.Literal.string("0-3")),
            _parameter("CPUAFFINITYMODE", _keyword("ANY")),
        ],
        [
            _parameter("CPUAFFINITYSET", exp.Literal.string("cpu0")),
            _parameter("CPUAFFINITYMODE", _keyword("SHARED")),
        ],
        [_parameter("EXECUTIONPARALLELISM", exp.Literal.number(-1))],
        [_parameter("PLANNEDCONCURRENCY", exp.Literal.number(0))],
        [_parameter("PRIORITY", exp.Literal.number(101))],
        [_parameter("QUEUETIMEOUT", _keyword("NONE"))],
        [_parameter("RUNTIMECAP", _keyword("AUTO"))],
        [_parameter("RUNTIMEPRIORITY", _keyword("URGENT"))],
        [_parameter("SINGLEINITIATOR", exp.Literal.number(1))],
    ],
)
def test_programmatic_resource_pool_parameters_reject_invalid_values(
    parameters: list[vexp.ResourcePoolParameter],
) -> None:
    with pytest.raises(UnsupportedError):
        _generate_strict(_create_pool(*parameters))


def test_programmatic_resource_pool_ast_generates_valid_sql() -> None:
    expression = _create_pool(
        _parameter("MEMORYSIZE", exp.Literal.string("2G")),
        _parameter("PRIORITY", _keyword("HOLD")),
        _parameter("QUEUETIMEOUT", _keyword("NONE", quoted=True)),
    )
    expression.set("subcluster", vexp.ResourcePoolSubcluster(this=exp.to_identifier("analytics")))

    sql = _generate_strict(expression)
    assert sql == (
        "CREATE RESOURCE POOL rp FOR SUBCLUSTER analytics "
        "MEMORYSIZE '2G' PRIORITY HOLD QUEUETIMEOUT 'NONE'"
    )
    assert parse_one(sql, read="vertica") == expression


@pytest.mark.parametrize(
    "expression",
    [
        vexp.ResourcePoolParameter(this=exp.var("PRIORITY")),
        vexp.ResourcePoolKeyword(),
    ],
)
def test_programmatic_resource_pool_leaf_nodes_require_complete_shape(
    expression: exp.Expr,
) -> None:
    with pytest.raises(UnsupportedError):
        _generate_strict(expression)
