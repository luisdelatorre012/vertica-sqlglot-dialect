"""Offline recertification gate for the attributed public Vertica SQL corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

CORPUS_PATH = Path(__file__).parent / "fixtures" / "public_vertica_corpus.json"
CORPUS: dict[str, Any] = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
ADMITTED = tuple(entry for entry in CORPUS["entries"] if entry["status"] == "admitted")
EXCLUDED = tuple(entry for entry in CORPUS["entries"] if entry["status"] == "excluded")
LABELED = {entry["label"]: entry for entry in ADMITTED if entry["label"]}

EXPECTED_SOURCES = {
    "Vertica-VMart",
    "dbt-vertica",
    "VerticaPy",
    "vertica-python",
    "ODBC-Loader",
    "dblink",
    "vertica-sql-go",
    "vertica.dplyr",
    "vertica-hyperloglog",
    "puppet-vertica",
}

COMPOSED_PUBLIC_WORKLOAD = """
CREATE LOCAL TEMPORARY TABLE public_stage ON COMMIT PRESERVE ROWS AS
SELECT order_number, vendor_key, date_ordered
FROM store.store_orders_fact
WHERE date_ordered < '2012-03-01';

INSERT INTO public_stage
SELECT order_number, vendor_key, date_ordered
FROM store.store_orders_fact
WHERE vendor_key IN (
  SELECT vendor_key FROM public.vendor_dimension WHERE vendor_state = 'MA'
);

WITH vendor_orders AS (
  SELECT vendor_key, COUNT(*) AS order_count
  FROM public_stage
  GROUP BY vendor_key
)
SELECT :minimum_orders AS requested_floor,
       vendor_key,
       ABS((order_count - 10) / 10 * 100) AS variance_percent
FROM vendor_orders
WHERE order_count >= :minimum_orders
ORDER BY variance_percent DESC;

DROP TABLE public_stage;
"""


def _render_script(expressions: list[exp.Expr], *, pretty: bool) -> str:
    return ";\n".join(
        expression.sql(dialect="vertica", pretty=pretty) for expression in expressions
    )


def _assert_parent_metadata(expression: exp.Expr) -> None:
    for node in expression.walk():
        if node is expression:
            assert node.parent is None
        else:
            assert node.parent is not None
            assert node.arg_key is not None


def test_public_corpus_manifest_inventory_is_frozen_and_attributed() -> None:
    assert CORPUS["counts"] == {"total": 370, "admitted": 365, "excluded": 5}
    assert len(CORPUS["entries"]) == 370
    assert len({entry["sql"] for entry in CORPUS["entries"]}) == 370
    assert {entry["source"] for entry in CORPUS["entries"]} == EXPECTED_SOURCES
    assert set(CORPUS["revisions"]) == EXPECTED_SOURCES - {"Vertica-VMart"}

    vmart = [entry for entry in ADMITTED if entry["source"] == "Vertica-VMart"]
    assert len(vmart) == 9
    assert {entry["revision"] for entry in vmart} == {"26.2"}
    assert all(entry["path"].endswith("-sql/") for entry in vmart)


def test_public_corpus_exclusions_are_only_the_five_source_context_non_sql_forms() -> None:
    assert len(EXCLUDED) == 5
    reasons = [entry["exclusion_reason"] for entry in EXCLUDED]
    assert sum("incomplete Python string fragment" in reason for reason in reasons) == 2
    assert sum("prose sentence" in reason for reason in reasons) == 1
    assert sum("$$$ client interpolation" in reason for reason in reasons) == 2
    assert all(entry["adaptation"] == "none" for entry in EXCLUDED)


@pytest.mark.parametrize("entry", ADMITTED, ids=lambda entry: entry["id"])
def test_every_admitted_public_sql_case_is_lossless_and_analyzable(
    entry: dict[str, Any],
) -> None:
    baseline = parse(entry["sql"], read="vertica")
    assert baseline and all(expression is not None for expression in baseline)
    assert all(not isinstance(expression, exp.Command) for expression in baseline)

    for error_level in ErrorLevel:
        assert parse(entry["sql"], read="vertica", error_level=error_level) == baseline

    for pretty in (False, True):
        generated = _render_script(baseline, pretty=pretty)
        assert parse(generated, read="vertica", error_level=ErrorLevel.IMMEDIATE) == baseline

    for expression in baseline:
        restored = exp.Expr.load(expression.dump())
        copied = expression.copy()
        transformed = expression.copy().transform(lambda node: node)
        assert restored == expression
        assert copied == expression
        assert transformed == expression
        _assert_parent_metadata(restored)
        _assert_parent_metadata(copied)
        _assert_parent_metadata(transformed)
        list(traverse_scope(copied))
        annotate_types(expression.copy(), dialect="vertica")


def test_trailing_comment_only_public_scripts_remain_script_lossless() -> None:
    entries = [entry for entry in ADMITTED if entry["sql"].rstrip().endswith("*/")]
    assert len(entries) == 3
    for entry in entries:
        expressions = parse(entry["sql"], read="vertica")
        assert parse(_render_script(expressions, pretty=False), read="vertica") == expressions
        assert parse(_render_script(expressions, pretty=True), read="vertica") == expressions


def test_five_former_public_failures_are_named_and_closed() -> None:
    expected_labels = {
        "vertica-python-named",
        "hyperloglog-ctas-template",
        "hyperloglog-select-template",
        "vbuddy-skew-summary",
        "vbuddy-skew-detail",
    }
    assert expected_labels <= LABELED.keys()

    driver = parse_one(LABELED["vertica-python-named"]["sql"], read="vertica")
    assert [placeholder.this for placeholder in driver.find_all(exp.Placeholder)] == ["a", "b"]
    assert driver.sql(dialect="vertica") == "SELECT :a, :b"

    for label in ("hyperloglog-ctas-template", "hyperloglog-select-template"):
        expression = parse_one(LABELED[label]["sql"], read="vertica")
        generated = expression.sql(dialect="vertica")
        assert ":precision" in generated
        assert "%(precision)s" not in generated
        assert parse_one(generated, read="vertica") == expression

    for label in ("vbuddy-skew-summary", "vbuddy-skew-detail"):
        expression = parse_one(LABELED[label]["sql"], read="vertica")
        absolute = expression.find(exp.Abs)
        assert absolute is not None
        assert isinstance(absolute.this, exp.Mul)
        assert isinstance(absolute.this.this, exp.Div)
        assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression


def test_public_corpus_representative_ast_surface() -> None:
    expressions = [parse_one(entry["sql"], read="vertica") for entry in ADMITTED]

    vmart_tuple = parse_one(LABELED["vmart-03"]["sql"], read="vertica")
    vmart_correlated = parse_one(LABELED["vmart-05"]["sql"], read="vertica")
    vmart_join = parse_one(LABELED["vmart-09"]["sql"], read="vertica")
    assert vmart_tuple.find(exp.Tuple) is not None
    assert vmart_tuple.find(exp.In) is not None
    assert vmart_correlated.find(exp.Exists) is not None
    assert vmart_join.find(exp.Join) is not None

    assert any(entry["source"] == "dbt-vertica" for entry in ADMITTED)
    assert LABELED["verticapy-correlation"]["source"] == "VerticaPy"
    assert parse_one(LABELED["verticapy-correlation"]["sql"], read="vertica").find(exp.Window)
    assert parse_one(LABELED["dblink-join"]["sql"], read="vertica").find(exp.Join)
    assert (
        len(
            list(parse_one(LABELED["dplyr-analysis"]["sql"], read="vertica").find_all(exp.Subquery))
        )
        >= 4
    )
    assert any(expression.find(exp.Hint) for expression in expressions)
    assert any(expression.find(exp.CTE) for expression in expressions)
    assert any(expression.find(exp.SetOperation) for expression in expressions)
    assert any(isinstance(expression, exp.Insert) for expression in expressions)
    assert any(isinstance(expression, exp.Drop) for expression in expressions)


@pytest.mark.parametrize(
    ("label", "schema", "column"),
    [
        (
            "vmart-01",
            {"product_dimension": {"fat_content": "INT", "department_description": "TEXT"}},
            "fat_content",
        ),
        (
            "hyperloglog-select-template",
            {"test_schema": {"agg_clicks": {"client_id": "INT", "synopsis": "VARBINARY"}}},
            "client_id",
        ),
    ],
)
def test_public_cases_with_bounded_schemas_survive_full_analysis(
    label: str, schema: dict[str, Any], column: str
) -> None:
    expression = parse_one(LABELED[label]["sql"], read="vertica")
    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    optimized_twice = optimize(optimized.copy(), dialect="vertica", schema=schema)
    annotated = annotate_types(expression.copy(), dialect="vertica", schema=schema)

    for candidate in (qualified, optimized, optimized_twice, annotated):
        assert not isinstance(candidate, exp.Command)
        reparsed = parse_one(candidate.sql(dialect="vertica"), read="vertica")
        assert not isinstance(reparsed, exp.Command)
        assert parse_one(reparsed.sql(dialect="vertica"), read="vertica") == reparsed
    assert optimized_twice == optimized
    assert list(traverse_scope(expression))
    assert lineage(column, expression, dialect="vertica", schema=schema).name == column


def test_composed_public_temporary_lifecycle_workload() -> None:
    expressions = parse(COMPOSED_PUBLIC_WORKLOAD, read="vertica")
    assert [type(expression) for expression in expressions] == [
        exp.Create,
        exp.Insert,
        exp.Select,
        exp.Drop,
    ]
    assert expressions[2].find(exp.CTE) is not None
    assert expressions[2].find(exp.Placeholder) is not None
    absolute = expressions[2].find(exp.Abs)
    assert absolute is not None and isinstance(absolute.this, exp.Mul)
    assert parse(_render_script(expressions, pretty=False), read="vertica") == expressions
    assert parse(_render_script(expressions, pretty=True), read="vertica") == expressions
