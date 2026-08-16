"""Inherited core SQL kept under Vertica-specific regression coverage."""

from __future__ import annotations

import pytest
from sqlglot import exp

from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "node_type"),
    [
        (
            "INSERT INTO sales(id, amount) VALUES (1, 10.5), (2, 20.0)",
            exp.Insert,
        ),
        (
            "INSERT INTO archive SELECT * FROM sales WHERE ts < CURRENT_DATE",
            exp.Insert,
        ),
        (
            "UPDATE target AS t SET amount = s.amount FROM source AS s WHERE t.id = s.id",
            exp.Update,
        ),
        (
            "DELETE FROM target WHERE id IN (SELECT id FROM source)",
            exp.Delete,
        ),
        (
            "MERGE INTO t2 USING t1 ON t1.a = t2.a "
            "WHEN MATCHED THEN UPDATE SET b = t1.b "
            "WHEN NOT MATCHED THEN INSERT (a, b) VALUES (t1.a, t1.b)",
            exp.Merge,
        ),
    ],
)
def test_core_dml_is_semantic(sql: str, node_type: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, node_type)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE SCHEMA IF NOT EXISTS analytics",
        "CREATE SEQUENCE IF NOT EXISTS public.ids",
        "CREATE OR REPLACE VIEW public.v (id, amount) AS SELECT id, amount FROM sales",
        "DROP VIEW IF EXISTS public.v",
        "TRUNCATE TABLE staging",
    ],
)
def test_core_ddl_is_semantic(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert not isinstance(expression, exp.Command)
