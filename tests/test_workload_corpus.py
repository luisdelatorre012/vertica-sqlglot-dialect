"""Milestone 1 acceptance and recertification analysis workloads.

These scripts combine the statement families delivered across Q01-Q07 --
plain, recursive, and materialization-hinted CTEs; scoped and unscoped
temporary CTAS; definition-form temporary tables; ``INSERT ... SELECT`` and
``INSERT ... WITH``; ``SELECT ... INTO`` temporary targets; and multi-target
``DROP TABLE`` cleanup -- into the kind of end-to-end scripts an analysis
workload actually runs, rather than the isolated single-statement cases each
family's own test module already covers. Q23 extends that proof through the
Q09--Q22 remediation surface. This module introduces no new grammar; it only
proves the surface holds together across statement boundaries and through the
public analysis APIs.
"""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_script_roundtrip

# A staging -> aggregate -> promote -> cleanup pipeline: a definition-form
# temporary table populated by INSERT ... SELECT, a scoped (LOCAL) temporary
# CTAS whose own query carries a plain CTE, a SELECT ... INTO temporary
# target, and ordered multi-target DROP TABLE cleanup.
STAGING_PIPELINE = """
CREATE LOCAL TEMPORARY TABLE staging_orders
    (order_id BIGINT, customer_id BIGINT, amount DECIMAL(10, 2))
    ON COMMIT PRESERVE ROWS;
INSERT INTO staging_orders (order_id, customer_id, amount)
SELECT order_id, customer_id, amount
FROM raw_orders
WHERE amount > 0;
CREATE LOCAL TEMPORARY TABLE customer_totals ON COMMIT PRESERVE ROWS AS
WITH filtered AS (
    SELECT customer_id, amount FROM staging_orders WHERE amount > 0
)
SELECT customer_id, SUM(amount) AS total_amount
FROM filtered
GROUP BY customer_id;
SELECT customer_id, total_amount
INTO LOCAL TEMP TABLE top_customers ON COMMIT PRESERVE ROWS
FROM customer_totals
WHERE total_amount > 1000;
DROP TABLE staging_orders, customer_totals, top_customers;
""".strip()

STAGING_PIPELINE_TYPES: list[type[exp.Expr]] = [
    exp.Create,
    exp.Insert,
    exp.Create,
    vexp.SelectInto,
    vexp.DropTables,
]

# An unscoped temporary CTAS built from a plain CTE, a second unscoped
# temporary CTAS built from a recursive CTE, an archival INSERT ... WITH
# carrying a materialization hint, and multi-target DROP TABLE ... IF EXISTS
# cleanup.
RECURSIVE_ARCHIVE_PIPELINE = """
CREATE TEMPORARY TABLE ranked_orders ON COMMIT PRESERVE ROWS AS
WITH ranked AS (
    SELECT order_id, customer_id, amount,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_id DESC) AS rn
    FROM raw_orders
)
SELECT order_id, customer_id, amount
FROM ranked
WHERE rn <= 3;
CREATE TEMPORARY TABLE employee_hierarchy ON COMMIT PRESERVE ROWS AS
WITH RECURSIVE org AS (
    SELECT employee_id, manager_id, 1 AS depth
    FROM employees
    WHERE manager_id IS NULL
    UNION ALL
    SELECT e.employee_id, e.manager_id, org.depth + 1
    FROM employees AS e
    JOIN org ON e.manager_id = org.employee_id
)
SELECT employee_id, manager_id, depth
FROM org;
INSERT INTO archived_orders
WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ cutoff AS (
    SELECT MAX(order_id) AS max_id FROM ranked_orders
)
SELECT ranked_orders.order_id, ranked_orders.customer_id, ranked_orders.amount
FROM ranked_orders, cutoff
WHERE ranked_orders.order_id <= cutoff.max_id;
DROP TABLE IF EXISTS ranked_orders, employee_hierarchy;
""".strip()

RECURSIVE_ARCHIVE_PIPELINE_TYPES: list[type[exp.Expr]] = [
    exp.Create,
    exp.Create,
    exp.Insert,
    vexp.DropTables,
]

# Q23's recertification workload composes every remediated query family with
# the temporary-table lifecycle. It deliberately keeps catalog-dependent
# validity out of scope: the fixture proves syntax, AST shape, regeneration,
# and analysis traversal only.
RECERTIFICATION_PIPELINE = """
CREATE LOCAL TEMPORARY TABLE staging_sales
    (sale_id BIGINT, customer_id BIGINT, region VARCHAR(20), amount DECIMAL(10, 2))
    ON COMMIT PRESERVE ROWS;
INSERT INTO staging_sales (sale_id, customer_id, region, amount)
SELECT r.sale_id, r.customer_id, c.region, r.amount
FROM raw_sales AS r
JOIN customers AS c ON r.customer_id = c.customer_id
WHERE r.amount > 0;
CREATE GLOBAL TEMPORARY TABLE customer_rollups ON COMMIT PRESERVE ROWS AS
WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ base AS (
    WITH positive AS (
        SELECT customer_id, region, amount FROM staging_sales WHERE amount > 0
    )
    SELECT customer_id, region, amount FROM positive
),
aggregated AS (
    SELECT region, customer_id, SUM(amount) AS total_amount
    FROM base
    GROUP BY ROLLUP(region), CUBE(customer_id), GROUPING SETS(())
)
SELECT region, customer_id, total_amount FROM aggregated;
CREATE TEMPORARY TABLE region_levels ON COMMIT PRESERVE ROWS AS
WITH RECURSIVE levels (region, depth) AS (
    SELECT region, 1 AS depth FROM customer_rollups
    UNION ALL
    SELECT region, depth + 1 FROM levels WHERE depth < 2
)
SELECT region, depth FROM levels;
AT TIME '2026-08-21 00:00:00'
WITH snapshot_sales AS (
    SELECT customer_id FROM staging_sales
)
SELECT s.customer_id /* historical projection */, c.region
FROM snapshot_sales AS s
LEFT OUTER JOIN customers AS c ON s.customer_id = c.customer_id
ORDER BY s.customer_id LIMIT 5 OFFSET 1 FOR UPDATE;
AT EPOCH LATEST
SELECT customer_id, total_amount FROM customer_rollups
UNION ALL
(SELECT customer_id, total_amount FROM customer_rollups
 ORDER BY total_amount DESC LIMIT 1)
ORDER BY total_amount DESC LIMIT 10 OFFSET 0;
SELECT customer_id, total_amount
INTO LOCAL TEMP TABLE promoted_customers ON COMMIT PRESERVE ROWS
FROM customer_rollups
WHERE total_amount > 1000;
/* recertification cleanup */
DROP TABLE staging_sales, customer_rollups, region_levels, promoted_customers;
""".strip()

RECERTIFICATION_PIPELINE_TYPES: list[type[exp.Expr]] = [
    exp.Create,
    exp.Insert,
    exp.Create,
    exp.Create,
    vexp.AtEpochSelect,
    vexp.AtEpochUnion,
    vexp.SelectInto,
    vexp.DropTables,
]

ALL_PARSE_LEVELS = tuple(ErrorLevel)
FOREIGN_DIALECTS = ("postgres", "duckdb", "mysql", "sqlite")
ALL_UNSUPPORTED_LEVELS = (ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE)


def test_staging_pipeline_parses_generates_and_reparses() -> None:
    assert_script_roundtrip(STAGING_PIPELINE, STAGING_PIPELINE_TYPES)


def test_recursive_archive_pipeline_parses_generates_and_reparses() -> None:
    assert_script_roundtrip(RECURSIVE_ARCHIVE_PIPELINE, RECURSIVE_ARCHIVE_PIPELINE_TYPES)


def test_recertification_pipeline_parses_generates_and_reparses() -> None:
    statements = assert_script_roundtrip(RECERTIFICATION_PIPELINE, RECERTIFICATION_PIPELINE_TYPES)
    generated = "\n".join(statement.sql(dialect="vertica") for statement in statements)
    assert "historical projection" in generated
    assert "recertification cleanup" in generated


def test_recertification_pipeline_statement_shapes() -> None:
    (
        define_staging,
        insert_staging,
        create_rollups,
        create_recursive,
        historical_select,
        historical_union,
        select_into,
        drop,
    ) = parse(RECERTIFICATION_PIPELINE, read="vertica")

    assert isinstance(define_staging, exp.Create)
    assert isinstance(insert_staging, exp.Insert)
    insert_query = insert_staging.expression
    assert isinstance(insert_query, exp.Select)
    join = insert_query.args["joins"][0]
    assert isinstance(join, exp.Join)
    assert join.args["on"] is not None

    assert isinstance(create_rollups, exp.Create)
    rollup_query = create_rollups.expression
    assert isinstance(rollup_query, exp.Select)
    outer_with = rollup_query.args["with_"]
    assert isinstance(outer_with, vexp.WithHint)
    assert [cte.alias for cte in outer_with.expressions] == ["base", "aggregated"]
    base_query = outer_with.expressions[0].this
    assert isinstance(base_query, exp.Select)
    assert isinstance(base_query.args["with_"], exp.With)
    group = outer_with.expressions[1].this.args["group"]
    assert isinstance(group, vexp.VerticaGroup)
    assert [type(item) for item in group.expressions] == [
        exp.Rollup,
        exp.Cube,
        exp.GroupingSets,
    ]

    assert isinstance(create_recursive, exp.Create)
    recursive_with = create_recursive.expression.args["with_"]
    assert isinstance(recursive_with, exp.With)
    assert recursive_with.args["recursive"] is True
    assert isinstance(recursive_with.expressions[0].this, exp.Union)

    assert isinstance(historical_select, vexp.AtEpochSelect)
    assert isinstance(historical_select.args["with_"], exp.With)
    assert isinstance(historical_select.args["limit"], exp.Limit)
    assert isinstance(historical_select.args["offset"], exp.Offset)
    assert len(historical_select.args["locks"]) == 1

    assert isinstance(historical_union, vexp.AtEpochUnion)
    assert historical_union.args["distinct"] is False
    assert isinstance(historical_union.expression, exp.Subquery)
    assert isinstance(historical_union.args["limit"], exp.Limit)
    assert isinstance(historical_union.args["offset"], exp.Offset)

    assert isinstance(select_into, vexp.SelectInto)
    assert isinstance(select_into.args["into"], vexp.IntoTableClause)
    assert select_into.args["into"].this.name == "promoted_customers"

    assert isinstance(drop, vexp.DropTables)
    assert [drop.this.name, *[target.name for target in drop.expressions]] == [
        "staging_sales",
        "customer_rollups",
        "region_levels",
        "promoted_customers",
    ]


def test_staging_pipeline_statement_shapes() -> None:
    define_staging, insert_staging, create_totals, select_into, drop = parse(
        STAGING_PIPELINE, read="vertica"
    )

    assert isinstance(define_staging, exp.Create)
    assert isinstance(define_staging.this, exp.Schema)
    assert define_staging.this.this.name == "staging_orders"
    assert [type(prop).__name__ for prop in define_staging.args["properties"].expressions] == [
        "LocalProperty",
        "TemporaryProperty",
        "OnCommitProperty",
    ]

    assert isinstance(insert_staging, exp.Insert)
    assert isinstance(insert_staging.this, exp.Schema)
    assert insert_staging.this.this.name == "staging_orders"

    assert isinstance(create_totals, exp.Create)
    assert create_totals.this.name == "customer_totals"
    totals_query = create_totals.expression
    assert isinstance(totals_query, exp.Select)
    assert type(totals_query.args["with_"]) is exp.With
    assert totals_query.args["with_"].expressions[0].alias == "filtered"

    assert isinstance(select_into, vexp.SelectInto)
    into_clause = select_into.args["into"]
    assert isinstance(into_clause, vexp.IntoTableClause)
    assert into_clause.this.name == "top_customers"
    assert into_clause.args["scope"] == "LOCAL"
    assert into_clause.args["on_commit"] == "PRESERVE"

    assert isinstance(drop, vexp.DropTables)
    assert [drop.this.name, *[target.name for target in drop.expressions]] == [
        "staging_orders",
        "customer_totals",
        "top_customers",
    ]
    assert drop.args["exists"] is False


def test_recursive_archive_pipeline_statement_shapes() -> None:
    create_ranked, create_hierarchy, insert_archive, drop = parse(
        RECURSIVE_ARCHIVE_PIPELINE, read="vertica"
    )

    assert isinstance(create_ranked, exp.Create)
    ranked_query = create_ranked.expression
    assert isinstance(ranked_query, exp.Select)
    assert type(ranked_query.args["with_"]) is exp.With
    assert ranked_query.args["with_"].args["recursive"] is None

    assert isinstance(create_hierarchy, exp.Create)
    hierarchy_query = create_hierarchy.expression
    assert isinstance(hierarchy_query, exp.Select)
    assert type(hierarchy_query.args["with_"]) is exp.With
    assert hierarchy_query.args["with_"].args["recursive"] is True
    assert isinstance(hierarchy_query.args["with_"].expressions[0].this, exp.Union)

    assert isinstance(insert_archive, exp.Insert)
    assert insert_archive.this.name == "archived_orders"
    archive_query = insert_archive.expression
    assert isinstance(archive_query, exp.Select)
    archive_with = archive_query.args["with_"]
    assert isinstance(archive_with, vexp.WithHint)
    assert archive_with.expressions[0].alias == "cutoff"

    assert isinstance(drop, vexp.DropTables)
    assert [drop.this.name, *[target.name for target in drop.expressions]] == [
        "ranked_orders",
        "employee_hierarchy",
    ]
    assert drop.args["exists"] is True


def test_leading_comment_survives_a_multi_statement_script_boundary() -> None:
    script = (
        "CREATE LOCAL TEMPORARY TABLE t (id BIGINT) ON COMMIT PRESERVE ROWS;\n"
        "/* pipeline cleanup */ DROP TABLE t;"
    )
    define_t, drop_t = parse(script, read="vertica")

    assert isinstance(define_t, exp.Create)
    assert isinstance(drop_t, exp.Drop)
    assert "pipeline cleanup" in drop_t.sql(dialect="vertica")


def test_select_into_target_qualifies_against_an_intermediate_temporary_table() -> None:
    """Optimizer traversal: ``qualify`` resolves the ``SELECT ... INTO``
    target's columns against the preceding temporary table's own schema, and
    preserves the ``SelectInto``/``IntoTableClause`` contract through
    ``dump()``/``load()``."""

    statements = parse(STAGING_PIPELINE, read="vertica")
    select_into = statements[3]
    assert isinstance(select_into, vexp.SelectInto)

    schema = {"customer_totals": {"customer_id": "BIGINT", "total_amount": "DECIMAL"}}
    qualified = qualify(select_into.copy(), dialect="vertica", schema=schema)

    assert isinstance(qualified, vexp.SelectInto)
    columns = {column.name: column.table for column in qualified.find_all(exp.Column)}
    assert columns == {"customer_id": "customer_totals", "total_amount": "customer_totals"}
    assert qualified.args["into"].this.name == "top_customers"

    restored = exp.Expr.load(qualified.dump())
    assert restored == qualified


def test_lineage_smoke_traces_through_the_temporary_table_and_cte_chain() -> None:
    """Column-level lineage smoke across a CTE/temporary-table chain: the
    ``SELECT ... INTO`` target's ``customer_id`` is traced through
    ``customer_totals``'s own CTAS query -- itself built from a CTE
    (``filtered``) -- down to the definition-form ``staging_orders``
    temporary table's declared column, proving downstream lineage tooling can
    follow an analysis pipeline built entirely from this milestone's
    statement families."""

    statements = parse(STAGING_PIPELINE, read="vertica")
    create_totals = statements[2]
    select_into = statements[3]
    assert isinstance(create_totals, exp.Create)
    assert isinstance(select_into, vexp.SelectInto)

    schema = {
        "staging_orders": {"order_id": "BIGINT", "customer_id": "BIGINT", "amount": "DECIMAL"},
    }

    node = lineage(
        "customer_id",
        select_into,
        schema=schema,
        sources={"customer_totals": create_totals.expression},
        dialect="vertica",
    )
    names = {downstream.name for downstream in node.walk()}
    assert names >= {
        "customer_id",
        "customer_totals.customer_id",
        "filtered.customer_id",
        "staging_orders.customer_id",
    }


def test_optimize_is_stable_across_the_staging_pipeline_select_into() -> None:
    statements = parse(STAGING_PIPELINE, read="vertica")
    select_into = statements[3]
    assert isinstance(select_into, vexp.SelectInto)

    schema = {
        "staging_orders": {"order_id": "BIGINT", "customer_id": "BIGINT", "amount": "DECIMAL"},
        "customer_totals": {"customer_id": "BIGINT", "total_amount": "DECIMAL"},
    }
    optimized = optimize(select_into.copy(), dialect="vertica", schema=schema)

    assert isinstance(optimized, vexp.SelectInto)
    assert isinstance(optimized.args["into"], vexp.IntoTableClause)
    restored = exp.Expr.load(optimized.dump())
    assert restored == optimized


def test_recertification_public_query_roots_support_analysis() -> None:
    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")
    historical_select = statements[4]
    historical_union = statements[5]
    assert isinstance(historical_select, vexp.AtEpochSelect)
    assert isinstance(historical_union, vexp.AtEpochUnion)

    schema = {
        "staging_sales": {
            "sale_id": "BIGINT",
            "customer_id": "BIGINT",
            "region": "VARCHAR",
            "amount": "DECIMAL",
        },
        "customers": {"customer_id": "BIGINT", "region": "VARCHAR"},
        "customer_rollups": {
            "region": "VARCHAR",
            "customer_id": "BIGINT",
            "total_amount": "DECIMAL",
        },
    }

    for expression, expected_type in (
        (historical_select, vexp.AtEpochSelect),
        (historical_union, vexp.AtEpochUnion),
    ):
        assert list(traverse_scope(expression))
        qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
        optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
        for analyzed in (qualified, optimized):
            assert isinstance(analyzed, expected_type)
            assert list(traverse_scope(analyzed))
            assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    historical_lineage = lineage("customer_id", historical_union, schema=schema, dialect="vertica")
    assert {node.name for node in historical_lineage.walk()} >= {
        "ATEPOCHUNION",
        "customer_rollups.customer_id",
    }


def test_recertification_lineage_reaches_the_raw_source_query() -> None:
    """Trace SELECT INTO through CTAS/CTEs and the INSERT-populated table."""

    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")
    insert_staging = statements[1]
    create_rollups = statements[2]
    select_into = statements[6]
    assert isinstance(insert_staging, exp.Insert)
    assert isinstance(create_rollups, exp.Create)
    assert isinstance(select_into, vexp.SelectInto)
    assert isinstance(insert_staging.expression, exp.Query)
    assert isinstance(create_rollups.expression, exp.Query)

    raw_schema = {
        "raw_sales": {
            "sale_id": "BIGINT",
            "customer_id": "BIGINT",
            "amount": "DECIMAL",
        },
        "customers": {"customer_id": "BIGINT", "region": "VARCHAR"},
    }
    expanded_rollups = exp.expand(
        create_rollups.expression,
        {"staging_sales": insert_staging.expression},
        dialect="vertica",
    )
    node = lineage(
        "customer_id",
        select_into,
        schema=raw_schema,
        sources={"customer_rollups": expanded_rollups},
        dialect="vertica",
    )
    names = {downstream.name for downstream in node.walk()}
    assert names >= {
        "customer_id",
        "customer_rollups.customer_id",
        "aggregated.customer_id",
        "base.customer_id",
        "positive.customer_id",
        "staging_sales.customer_id",
        "r.customer_id",
    }


def test_recertification_copy_transform_and_parent_metadata() -> None:
    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")
    historical_union = statements[5]
    assert isinstance(historical_union, vexp.AtEpochUnion)

    transformed = historical_union.copy().transform(
        lambda node: (
            exp.column("client_id", table=node.table)
            if isinstance(node, exp.Column) and node.name == "customer_id"
            else node
        )
    )
    assert isinstance(transformed, vexp.AtEpochUnion)
    assert transformed.this.parent is transformed
    assert transformed.this.arg_key == "this"
    assert transformed.expression.parent is transformed
    assert transformed.expression.arg_key == "expression"
    assert transformed.args["at_epoch_kind"].parent is transformed
    assert transformed.args["at_epoch_value"].parent is transformed
    assert all(column.name != "customer_id" for column in transformed.find_all(exp.Column))
    assert parse_one(transformed.sql(dialect="vertica"), read="vertica") == transformed


@pytest.mark.parametrize(
    "malformed",
    [
        "SELECT * FROM t PIVOT(SUM(x) FOR y IN (1))",
        "WITH c AS (INSERT INTO t SELECT 1) SELECT * FROM c",
        "CREATE LOCAL TABLE t (id BIGINT)",
        "INSERT target SELECT 1",
        "SELECT a FROM t INTO TABLE misplaced",
        "SELECT * FROM t TIMESERIES slice_time AS '1 minute' OVER ()",
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_recertification_negative_scripts_fail_without_swallowing_the_suffix(
    malformed: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse(
            f"{malformed}; SELECT 2023 AS following_statement",
            read="vertica",
            error_level=error_level,
        )

    following = parse_one(
        "SELECT 2023 AS following_statement", read="vertica", error_level=error_level
    )
    assert following.sql(dialect="vertica") == "SELECT 2023 AS following_statement"


@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_at_epoch_with_parenthesized_set_branch_composes(
    error_level: ErrorLevel,
) -> None:
    sql = (
        "AT EPOCH LATEST WITH c AS (SELECT a FROM t) "
        "SELECT a FROM c UNION ALL (SELECT a FROM u ORDER BY a LIMIT 1)"
    )
    expression = parse_one(sql, read="vertica", error_level=error_level)
    assert isinstance(expression, vexp.AtEpochUnion)
    assert expression.args.get("with_") is not None
    assert isinstance(expression.expression, exp.Subquery)
    assert expression.sql(dialect="vertica") == sql


def test_at_epoch_with_leading_comment_is_generation_stable() -> None:
    expression = parse_one(
        "/* lead */ AT EPOCH LATEST WITH c AS (SELECT a FROM t) SELECT a FROM c",
        read="vertica",
    )
    generated = expression.sql(dialect="vertica")
    reparsed = parse_one(generated, read="vertica")

    assert reparsed == expression
    assert generated.startswith("/* lead */ AT EPOCH LATEST")
    assert reparsed.sql(dialect="vertica") == generated


def test_for_update_of_target_is_recertification_analysis_safe() -> None:
    expression = parse_one("SELECT a FROM t FOR UPDATE OF t", read="vertica")
    for analysis in (qualify, optimize):
        analyzed = analysis(expression.copy(), dialect="vertica", schema={"t": {"a": "INT"}})
        assert analyzed.sql(dialect="vertica").endswith('FOR UPDATE OF "t"')
        assert list(traverse_scope(analyzed))

    node = lineage("a", expression, dialect="vertica", schema={"t": {"a": "INT"}})
    assert {downstream.name for downstream in node.walk()} == {"a", "t.a"}


def test_recertification_programmatic_ast_mutations_fail_atomically() -> None:
    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")
    create_rollups = statements[2].copy()
    historical_union = statements[5].copy()
    select_into = statements[6].copy()
    assert isinstance(create_rollups, exp.Create)
    assert isinstance(historical_union, vexp.AtEpochUnion)
    assert isinstance(select_into, vexp.SelectInto)

    create_rollups.set("replace", True)
    historical_union.set("by_name", False)
    select_into.args["into"].set("unlogged", True)

    for malformed in (create_rollups, historical_union, select_into):
        with pytest.raises(UnsupportedError):
            malformed.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_recertification_custom_roots_fail_atomically_in_foreign_dialects(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")
    custom_roots = [statements[index] for index in (4, 5, 6, 7)]

    for expression in custom_roots:
        with pytest.raises((UnsupportedError, ValueError)):
            expression.sql(dialect=dialect, unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("unsupported_level", ALL_UNSUPPORTED_LEVELS)
def test_recertification_historical_roots_fail_when_nested_in_foreign_queries(
    dialect: str, unsupported_level: ErrorLevel
) -> None:
    statements = parse(RECERTIFICATION_PIPELINE, read="vertica")

    for historical in (statements[4], statements[5]):
        nested = exp.select("*").from_(historical.copy().subquery("historical"))
        with pytest.raises((UnsupportedError, ValueError)):
            nested.sql(dialect=dialect, unsupported_level=unsupported_level)
