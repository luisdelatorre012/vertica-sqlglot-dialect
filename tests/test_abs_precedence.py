"""ABS function and prefix-operator precedence regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from tests.helpers import assert_roundtrip

VBUDDY_SKEW_SUMMARY = (
    "SELECT /*+label(vBuddyLite)*/ anchor_table_name, MAX(skew_percent) AS "
    "max_skew_percent FROM (SELECT anchor_table_schema ||'.'|| anchor_table_name AS "
    "anchor_table_name, projection_schema ||'.'|| projection_name AS projection_name, "
    "node_name, row_count, TO_CHAR(ABS((row_count - (SUM(row_count) OVER (PARTITION BY "
    "projection_id))/(COUNT(row_count) OVER (PARTITION BY projection_id)))/(SUM(row_count) "
    "OVER (PARTITION BY projection_id))*100),'9,990.99') AS skew_percent FROM "
    "projection_storage WHERE anchor_table_schema || '.' || anchor_table_name IN (SELECT "
    "table_name FROM (SELECT DISTINCT projection_schema || '.' || anchor_table_name AS "
    "table_name, row_count FROM projections INNER JOIN (SELECT DISTINCT projection_id, "
    "SUM(row_count) OVER (PARTITION BY projection_id) AS row_count FROM projection_storage) "
    "AS storage ON storage.projection_id = projections.projection_id ORDER BY row_count DESC "
    "LIMIT 10) AS aa)) AS bb GROUP BY anchor_table_name ORDER BY 2 DESC,1"
)

VBUDDY_SKEW_DETAIL = (
    "SELECT /*+label(vBuddyLite)*/ anchor_table_name, projection_name, node_name, "
    "MAX(skew_percent) AS skew_percent FROM (SELECT anchor_table_schema ||'.'|| "
    "anchor_table_name AS anchor_table_name, projection_schema ||'.'|| projection_name AS "
    "projection_name, node_name, row_count, TO_CHAR(ABS((row_count - (SUM(row_count) OVER "
    "(PARTITION BY projection_id))/(COUNT(row_count) OVER (PARTITION BY "
    "projection_id)))/(SUM(row_count) OVER (PARTITION BY projection_id))*100),'9,990.99') AS "
    "skew_percent FROM projection_storage WHERE anchor_table_schema || '.' || "
    "anchor_table_name IN (SELECT table_name FROM (SELECT DISTINCT projection_schema || '.' "
    "|| anchor_table_name AS table_name, row_count FROM projections INNER JOIN (SELECT "
    "DISTINCT projection_id, SUM(row_count) OVER (PARTITION BY projection_id) AS row_count "
    "FROM projection_storage) AS storage ON storage.projection_id = projections.projection_id "
    "ORDER BY row_count DESC LIMIT 10) AS aa)) AS bb WHERE skew_percent > 0 GROUP BY "
    "anchor_table_name, projection_name, node_name ORDER BY 4 DESC,1,2,3 LIMIT 20"
)


@pytest.mark.parametrize(
    ("sql", "expected", "operand_type"),
    [
        ("SELECT ABS(x)", "SELECT ABS(x)", exp.Column),
        ("SELECT @ x", "SELECT ABS(x)", exp.Column),
        ("SELECT ABS(-x)", "SELECT ABS(-x)", exp.Neg),
        ("SELECT ABS(CAST(x AS FLOAT))", "SELECT ABS(CAST(x AS DOUBLE PRECISION))", exp.Cast),
        ("SELECT ABS((x + y))", "SELECT ABS((x + y))", exp.Paren),
        ("SELECT ABS(x + y)", "SELECT ABS(x + y)", exp.Add),
        ("SELECT ABS(x * y)", "SELECT ABS(x * y)", exp.Mul),
        ("SELECT ABS(x / y)", "SELECT ABS(x / y)", exp.Div),
        ("SELECT ABS(x // y)", "SELECT ABS(x // y)", exp.IntDiv),
        ("SELECT ABS(x % y)", "SELECT ABS(x % y)", exp.Mod),
        ("SELECT ABS(x ^ y)", "SELECT ABS(POWER(x, y))", exp.Pow),
        (
            "SELECT ABS(CASE WHEN x > 0 THEN x ELSE y END)",
            "SELECT ABS(CASE WHEN x > 0 THEN x ELSE y END)",
            exp.Case,
        ),
        ("SELECT ABS(COALESCE(x, y))", "SELECT ABS(COALESCE(x, y))", exp.Coalesce),
        ("SELECT ABS(ABS(x + y))", "SELECT ABS(ABS(x + y))", exp.Abs),
    ],
)
def test_abs_operand_precedence_matrix(
    sql: str, expected: str, operand_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    absolute = expression.find(exp.Abs)

    assert absolute is not None
    assert isinstance(absolute.this, operand_type)
    assert absolute.this.parent is absolute
    assert absolute.this.arg_key == "this"


@pytest.mark.parametrize("error_level", tuple(ErrorLevel))
@pytest.mark.parametrize(
    ("sql", "expected_root"),
    [
        ("SELECT ABS((x - y) / z * 100)", exp.Abs),
        ("SELECT @ ((x - y) / z * 100)", exp.Abs),
        ("SELECT @ x + y", exp.Add),
    ],
)
def test_abs_source_spellings_are_stable_at_every_parser_level(
    sql: str, expected_root: type[exp.Expr], error_level: ErrorLevel
) -> None:
    expression = parse_one(sql, read="vertica", error_level=error_level)
    generated = expression.sql(dialect="vertica")
    reparsed = parse_one(generated, read="vertica", error_level=error_level)

    assert type(expression.expressions[0]) is expected_root
    assert expression == reparsed
    assert "@" not in generated


def test_abs_compound_operand_regression() -> None:
    expression = assert_roundtrip("SELECT ABS((x - y) / z * 100)")
    absolute = expression.expressions[0]

    assert isinstance(absolute, exp.Abs)
    assert isinstance(absolute.this, exp.Mul)
    assert isinstance(absolute.this.this, exp.Div)
    assert expression.sql(dialect="vertica") == "SELECT ABS((x - y) / z * 100)"


@pytest.mark.parametrize("sql", [VBUDDY_SKEW_SUMMARY, VBUDDY_SKEW_DETAIL])
def test_public_vbuddy_data_skew_queries_preserve_abs_owner(sql: str) -> None:
    expression = assert_roundtrip(sql)
    absolute = expression.find(exp.Abs)

    assert absolute is not None
    assert isinstance(absolute.this, exp.Mul)
    assert isinstance(absolute.this.this, exp.Div)
    assert absolute.find(exp.Window) is not None
    assert expression.find(exp.TimeToStr) is not None
    assert expression.find(exp.Join) is not None
    assert expression.find(exp.Group) is not None
    assert expression.args.get("order") is not None


def test_abs_comments_and_tree_operations_are_stable() -> None:
    expression = assert_roundtrip(
        "SELECT /* before */ @ (x + y) /* after */ FROM t",
        "/* before */ SELECT ABS((x + y) /* after */) FROM t",
    )
    absolute = expression.find(exp.Abs)
    assert absolute is not None

    copied = expression.copy()
    transformed = expression.transform(lambda node: node)
    restored = exp.Expr.load(expression.dump())

    for candidate in (copied, transformed, restored):
        candidate_abs = candidate.find(exp.Abs)
        assert candidate_abs is not None
        assert isinstance(candidate_abs.this, exp.Paren)
        assert candidate_abs.this.parent is candidate_abs
        assert candidate_abs.this.arg_key == "this"


def test_abs_survives_public_analysis_paths() -> None:
    sql = "SELECT ABS((t.x - t.y) / t.z * 100) AS skew FROM t"
    schema = {"t": {"x": "DOUBLE", "y": "DOUBLE", "z": "DOUBLE"}}
    expression = parse_one(sql, read="vertica")
    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    optimized_twice = optimize(optimized.copy(), dialect="vertica", schema=schema)
    annotated = annotate_types(expression.copy(), dialect="vertica", schema=schema)

    for candidate in (qualified, optimized, optimized_twice, annotated):
        absolute = candidate.find(exp.Abs)
        assert absolute is not None
        assert isinstance(absolute.this, exp.Mul)

    scopes = list(traverse_scope(expression))
    assert len(scopes) == 1
    assert lineage("skew", expression, dialect="vertica", schema=schema).name == "skew"


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("unsupported_level", tuple(ErrorLevel))
@pytest.mark.parametrize(
    "absolute",
    [
        exp.Abs(),
        exp.Abs(this="x"),
        exp.Abs(this=exp.column("x"), unexpected=False),
    ],
)
def test_malformed_programmatic_abs_fails_atomically(
    absolute: exp.Abs, unsupported_level: ErrorLevel, nested: bool
) -> None:
    expression: exp.Expr = exp.select(absolute) if nested else absolute

    with pytest.raises((UnsupportedError, ValueError), match="Vertica ABS requires one expression"):
        expression.sql(dialect="vertica", unsupported_level=unsupported_level)


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
@pytest.mark.parametrize("nested", [False, True])
def test_abs_keeps_canonical_foreign_generation(dialect: str, nested: bool) -> None:
    absolute = exp.Abs(this=exp.column("x") + exp.column("y"))
    expression: exp.Expr = exp.select(absolute) if nested else absolute

    expected = "SELECT ABS(x + y)" if nested else "ABS(x + y)"
    assert expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE) == expected


def test_adjacent_prefix_and_postfix_operators_are_unchanged() -> None:
    expression = assert_roundtrip(
        "SELECT |/ 25.0, ||/ 27.0, !! 5, 4.98!, SIGN(-2)",
        "SELECT SQRT(25.0), CBRT(27.0), 5!, 4.98!, SIGN(-2)",
    )

    assert isinstance(expression.expressions[0], exp.Sqrt)
    assert isinstance(expression.expressions[1], exp.Cbrt)
    assert isinstance(expression.expressions[2], exp.Factorial)
    assert isinstance(expression.expressions[3], exp.Factorial)
    assert isinstance(expression.expressions[4], exp.Sign)
