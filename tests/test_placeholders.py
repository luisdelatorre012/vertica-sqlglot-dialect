"""Lossless public Vertica driver-placeholder contracts."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from tests.helpers import assert_roundtrip, assert_script_roundtrip

ALL_PARSE_LEVELS = tuple(ErrorLevel)

HYPERLOGLOG_CREATE = """
CREATE TABLE test_schema.agg_clicks AS
SELECT
  HOUR(TO_TIMESTAMP(click_ts)) AS hour,
  banner_id,
  zone_id,
  client_id,
  network_id,
  HllCreateSynopsis(
    user_id_fast USING PARAMETERS
      hllLeadingBits=:precision,
      bitsPerBucket=:bitsperbucket
  ) AS Synopsis
FROM test_schema.fact_clicks
WHERE client_id > :minrange AND client_id < :maxrange
GROUP BY
  HOUR(TO_TIMESTAMP(click_ts)),
  banner_id,
  zone_id,
  client_id,
  network_id
"""

HYPERLOGLOG_QUERY = """
SELECT
  client_id,
  HllDistinctCount(
    synopsis USING PARAMETERS hllLeadingBits=:precision
  )
FROM test_schema.agg_clicks
GROUP BY client_id
"""


@pytest.mark.parametrize(
    ("sql", "expected_args"),
    [
        ("SELECT :a, :b", [{"this": "a"}, {"this": "b"}]),
        ("SELECT %s, %s", [{"this": None}, {"this": None}]),
        ("SELECT ?", [{"jdbc": True}]),
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_public_driver_placeholder_styles_roundtrip_at_every_error_level(
    sql: str, expected_args: list[dict[str, object]], error_level: ErrorLevel
) -> None:
    expression = parse_one(sql, read="vertica", error_level=error_level)
    assert [
        placeholder.args for placeholder in expression.find_all(exp.Placeholder)
    ] == expected_args
    assert expression.sql(dialect="vertica") == sql
    assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT :value AS projected",
        "SELECT a FROM t WHERE a > :floor AND a < :ceiling",
        "SELECT COALESCE(:value, 0), SUM(a + :delta) FROM t",
        "SELECT custom_udx(a USING PARAMETERS precision=:precision) FROM t",
        "SELECT * FROM (SELECT :nested AS value) q",
        "WITH q AS (SELECT :cte_value AS value) SELECT value FROM q",
        "INSERT INTO target SELECT :inserted",
        "CREATE TABLE target AS SELECT :created AS value",
    ],
)
def test_named_placeholders_compose_with_analysis_query_positions(sql: str) -> None:
    expression = assert_roundtrip(sql)
    placeholders = list(expression.find_all(exp.Placeholder))
    assert placeholders
    assert all(isinstance(placeholder.this, str) for placeholder in placeholders)


def test_hyperloglog_public_templates_roundtrip_losslessly() -> None:
    create = assert_roundtrip(HYPERLOGLOG_CREATE)
    query = assert_roundtrip(HYPERLOGLOG_QUERY)

    assert [placeholder.this for placeholder in create.find_all(exp.Placeholder)] == [
        "precision",
        "bitsperbucket",
        "minrange",
        "maxrange",
    ]
    assert [placeholder.this for placeholder in query.find_all(exp.Placeholder)] == ["precision"]
    assert all("%(" not in statement.sql(dialect="vertica") for statement in (create, query))


def test_repeated_and_prefix_colliding_names_remain_distinct() -> None:
    expression = assert_roundtrip(
        "SELECT :a, :aa, :a, :a1, :a_1",
    )
    assert [placeholder.this for placeholder in expression.find_all(exp.Placeholder)] == [
        "a",
        "aa",
        "a",
        "a1",
        "a_1",
    ]


def test_placeholder_comments_and_script_boundaries_roundtrip() -> None:
    script = "SELECT :a /* named */; SELECT %s /* positional */; SELECT ? /* prepared */"
    statements = assert_script_roundtrip(script, [exp.Select, exp.Select, exp.Select])
    assert [next(statement.find_all(exp.Placeholder)).args for statement in statements] == [
        {"this": "a"},
        {"this": None},
        {"jdbc": True},
    ]


def test_named_placeholders_survive_tree_and_analysis_operations() -> None:
    expression = parse_one(
        "SELECT source.a + :delta AS result FROM source WHERE source.b > :floor",
        read="vertica",
    )
    expected = [{"this": "delta"}, {"this": "floor"}]
    schema = {"source": {"a": "INT", "b": "INT"}}

    restored = exp.Expr.load(expression.dump())
    copied = expression.copy()
    transformed = expression.transform(lambda node: node)
    qualified = qualify(expression.copy(), dialect="vertica", schema=schema)
    optimized = optimize(expression.copy(), dialect="vertica", schema=schema)
    optimized_twice = optimize(optimized.copy(), dialect="vertica", schema=schema)
    annotated = annotate_types(expression.copy(), dialect="vertica", schema=schema)

    for tree in (
        restored,
        copied,
        transformed,
        qualified,
        optimized,
        optimized_twice,
        annotated,
    ):
        assert [placeholder.args for placeholder in tree.find_all(exp.Placeholder)] == expected
        assert ":delta" in tree.sql(dialect="vertica")
        assert ":floor" in tree.sql(dialect="vertica")

    for placeholder in transformed.find_all(exp.Placeholder):
        assert placeholder.parent is not None
        assert placeholder.arg_key in {"this", "expression"}
    assert list(traverse_scope(expression))
    assert lineage("result", expression, dialect="vertica", schema=schema).name == "result"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT %(name)s",
        "SELECT %(name)d",
        "SELECT %d",
        "SELECT %f",
        "SELECT %S",
        "SELECT % s",
        "SELECT : name",
        'SELECT :"name"',
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_unadmitted_placeholder_spellings_fail_closed(sql: str, error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_invalid_placeholder_does_not_swallow_following_statement(
    error_level: ErrorLevel,
) -> None:
    with pytest.raises(ParseError):
        parse(
            "SELECT %(name)s; SELECT :valid",
            read="vertica",
            error_level=error_level,
        )


@pytest.mark.parametrize(
    "placeholder",
    [
        exp.Placeholder(),
        exp.Placeholder(this=exp.to_identifier("name")),
        exp.Placeholder(this=""),
        exp.Placeholder(this="1name"),
        exp.Placeholder(jdbc=False),
        exp.Placeholder(this=None, jdbc=True),
        exp.Placeholder(this="name", kind="named"),
        exp.Placeholder(this="name", widget=False),
    ],
)
@pytest.mark.parametrize("unsupported_level", ALL_PARSE_LEVELS)
def test_ambiguous_or_malformed_placeholder_asts_fail_atomically(
    placeholder: exp.Placeholder, unsupported_level: ErrorLevel
) -> None:
    expression = exp.select(placeholder)
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="vertica", unsupported_level=unsupported_level)


def test_foreign_pyformat_tree_cannot_masquerade_as_named_vertica_placeholder() -> None:
    expression = parse_one("SELECT %(name)s", read="postgres")
    placeholder = expression.find(exp.Placeholder)
    assert placeholder is not None and isinstance(placeholder.this, exp.Identifier)
    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("placeholder", "expected"),
    [
        (exp.Placeholder(this="named"), "SELECT :named"),
        (exp.Placeholder(this=None), "SELECT %s"),
        (exp.Placeholder(jdbc=True), "SELECT ?"),
    ],
)
@pytest.mark.parametrize("unsupported_level", ALL_PARSE_LEVELS)
def test_programmatic_placeholders_require_explicit_admitted_provenance(
    placeholder: exp.Placeholder, expected: str, unsupported_level: ErrorLevel
) -> None:
    expression = exp.select(placeholder)
    assert expression.sql(dialect="vertica", unsupported_level=unsupported_level) == expected


@pytest.mark.parametrize("clause", ("LIMIT", "OFFSET"))
@pytest.mark.parametrize("name", (":count", "%s"))
def test_named_and_positional_placeholders_remain_invalid_row_counts(
    clause: str, name: str
) -> None:
    with pytest.raises(ParseError):
        parse_one(f"SELECT a FROM t {clause} {name}", read="vertica")


@pytest.mark.parametrize("clause", ("LIMIT", "OFFSET"))
def test_prepared_placeholders_remain_valid_row_counts(clause: str) -> None:
    assert_roundtrip(f"SELECT a FROM t {clause} ?")
