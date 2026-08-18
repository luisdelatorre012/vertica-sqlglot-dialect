"""Milestone 1 acceptance gate: realistic multi-statement analysis workloads.

These scripts combine the statement families delivered across Q01-Q07 --
plain, recursive, and materialization-hinted CTEs; scoped and unscoped
temporary CTAS; definition-form temporary tables; ``INSERT ... SELECT`` and
``INSERT ... WITH``; ``SELECT ... INTO`` temporary targets; and multi-target
``DROP TABLE`` cleanup -- into the kind of end-to-end scripts an analysis
workload actually runs, rather than the isolated single-statement cases each
family's own test module already covers. This module introduces no new
grammar; it only proves the surface holds together across statement
boundaries and through the optimizer.
"""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify

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


def test_staging_pipeline_parses_generates_and_reparses() -> None:
    assert_script_roundtrip(STAGING_PIPELINE, STAGING_PIPELINE_TYPES)


def test_recursive_archive_pipeline_parses_generates_and_reparses() -> None:
    assert_script_roundtrip(RECURSIVE_ARCHIVE_PIPELINE, RECURSIVE_ARCHIVE_PIPELINE_TYPES)


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
