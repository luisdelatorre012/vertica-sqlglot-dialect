"""Vertica projection DDL regressions."""

from __future__ import annotations

from sqlglot import exp

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_create_projection_full_design() -> None:
    expression = assert_roundtrip(
        "CREATE OR REPLACE PROJECTION analytics.orders_p "
        "(customer_id ENCODING RLE, "
        "GROUPED(order_id ENCODING DELTAVAL, amount), "
        "created_at ACCESSRANK 1) "
        "AS SELECT customer_id, order_id, amount, created_at FROM analytics.orders "
        "ORDER BY customer_id, created_at "
        "SEGMENTED BY HASH(customer_id) ALL NODES OFFSET 0 KSAFE 1",
        "CREATE OR REPLACE PROJECTION analytics.orders_p "
        "(customer_id ENCODING RLE, "
        "GROUPED(order_id ENCODING DELTAVAL, amount), "
        "created_at ACCESSRANK 1) "
        "AS SELECT customer_id, order_id, amount, created_at FROM analytics.orders "
        "ORDER BY customer_id, created_at "
        "SEGMENTED BY HASH(customer_id) ALL NODES OFFSET 0 KSAFE 1",
    )
    assert isinstance(expression, vexp.CreateProjection)
    assert len(expression.args["columns"]) == 3
    assert isinstance(expression.args["segmentation"], vexp.ProjectionSegmentation)


def test_create_unsegmented_projection() -> None:
    assert_roundtrip(
        "CREATE PROJECTION IF NOT EXISTS p AS SELECT id FROM source UNSEGMENTED ALL NODES",
        "CREATE PROJECTION IF NOT EXISTS p AS SELECT id FROM source UNSEGMENTED ALL NODES",
    )


def test_projection_explicit_nodes() -> None:
    assert_roundtrip(
        "CREATE PROJECTION p AS SELECT id FROM source SEGMENTED BY HASH(id) NODES node1, node2",
        "CREATE PROJECTION p AS SELECT id FROM source SEGMENTED BY HASH(id) NODES node1, node2",
    )


def test_drop_projection() -> None:
    expression = assert_roundtrip(
        "DROP PROJECTION IF EXISTS analytics.orders_p CASCADE",
        "DROP PROJECTION IF EXISTS analytics.orders_p CASCADE",
    )
    assert isinstance(expression, exp.Drop)
    assert expression.args["kind"] == "PROJECTION"
