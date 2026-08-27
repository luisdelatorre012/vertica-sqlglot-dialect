"""Q39 recertification gate for the reported PostgreSQL transpilation corpus."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp

REPORT_FIXTURE = Path(__file__).with_name("fixtures") / "postgres_transpilation_report.sql"
REPORT_COMMENTS = (
    "Unsupported expression type LocalProperty",
    "Unsupported expression type PartitionedLimit",
    "Unsupported expression type StatementTimestamp",
    "Unsupposrted expression type UtcStatementTimestamp",
    "Unsupported expression type VerticaOrdered",
    "Unsupported expression type VerticaRegexpLike",
    "Unsupported expression type VerticaToChar",
)
GENERATOR_LEVELS: tuple[ErrorLevel | None, ...] = (None, ErrorLevel.RAISE)
COMPOSED_SQL = """
/* q39 composed PostgreSQL lowering */
CREATE LOCAL TEMP TABLE q39_composed ON COMMIT PRESERVE ROWS AS
SELECT
    GETDATE() AS local_started,
    GETUTCDATE() AS utc_started,
    TO_CHAR(YEAR(CURRENT_DATE) - 2) AS prior_year,
    REGEXP_LIKE(name, 'a') AS matches,
    x AS x
FROM q39_source
ORDER BY x NULLS LAST
LIMIT 1 OVER (PARTITION BY x ORDER BY x NULLS FIRST)
""".strip()
COMPOSED_SCHEMA = {"q39_source": {"name": "VARCHAR", "x": "INT"}}

UNSAFE_POSTGRES_CASES = (
    (
        "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS c",
        "cannot preserve Vertica GLOBAL",
    ),
    (
        "SELECT ROW_NUMBER() OVER (ORDER BY a NULLS AUTO) FROM t",
        "only valid explicit NULLS FIRST or NULLS LAST",
    ),
    ("SELECT TO_CHAR(value) FROM t", "statically integral"),
    ("SELECT TO_CHAR(CAST('2026-08-27' AS DATE))", "statically integral"),
    ("SELECT REGEXP_LIKE('abc', '^a')", "Perl REGEXP_LIKE metacharacter"),
    ("SELECT REGEXP_LIKE(value, pattern) FROM t", "literal pattern"),
    ("SELECT REGEXP_LIKE('abc', 'a', 'i')", "omitted or 'c' mode"),
    (
        "SELECT * FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY b)",
        "star projection",
    ),
    (
        "SELECT a + 1 FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "stable name",
    ),
    (
        "SELECT a AS x, b AS x FROM t LIMIT 1 OVER (PARTITION BY x ORDER BY x)",
        "duplicate SELECT alias",
    ),
    (
        "SELECT DISTINCT a FROM t LIMIT 1 OVER (PARTITION BY b ORDER BY b)",
        "DISTINCT requires",
    ),
    (
        "SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a) FOR UPDATE",
        "lock tail",
    ),
    (
        "SELECT a INTO TABLE sink FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "SelectInto",
    ),
    (
        "AT EPOCH LATEST SELECT a FROM t LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "AtEpochSelect",
    ),
    (
        "SELECT slice_time FROM t TIMESERIES slice_time AS '1 minute' "
        "OVER (ORDER BY ts) LIMIT 1 OVER "
        "(PARTITION BY slice_time ORDER BY slice_time)",
        "TimeseriesSelect",
    ),
    (
        "SELECT a FROM t UNION ALL SELECT a FROM u LIMIT 1 OVER (PARTITION BY a ORDER BY a)",
        "set-operation root",
    ),
)


def _report_script() -> str:
    return REPORT_FIXTURE.read_text(encoding="utf-8")


def _postgres_sql(expression: exp.Expr, level: ErrorLevel | None, *, pretty: bool = False) -> str:
    if level is None:
        return expression.sql(dialect="postgres", pretty=pretty)
    return expression.sql(dialect="postgres", unsupported_level=level, pretty=pretty)


def _assert_target_shape(index: int, target_sql: str) -> None:
    target = parse_one(target_sql, read="postgres")

    if index == 0:
        assert isinstance(target, exp.Create)
        assert target.find(exp.TemporaryProperty) is not None
        assert target.find(exp.OnCommitProperty) is not None
        assert target.find(exp.GlobalProperty) is None
        assert "LOCAL" not in target_sql
    elif index == 1:
        assert target.named_selects == ["x"]
        assert len(list(target.find_all(exp.Subquery))) == 2
        assert isinstance(target.find(exp.RowNumber), exp.RowNumber)
        assert isinstance(target.args.get("where"), exp.Where)
        assert "_vertica_pl_row_number" not in target.named_selects
    elif index in {2, 3}:
        typed = annotate_types(target, dialect="postgres")
        assert isinstance(typed.expressions[0], exp.Cast)
        assert typed.expressions[0].type.this is exp.DType.TIMESTAMP
        assert "STATEMENT_TIMESTAMP()" in target_sql
        assert "CURRENT_TIMESTAMP" not in target_sql
        assert "NOW(" not in target_sql
        assert ("AT TIME ZONE 'UTC'" in target_sql) is (index == 3)
    elif index == 4:
        ordered = target.find(exp.Ordered)
        assert ordered is not None
        assert ordered.args.get("desc") is False
        assert ordered.args.get("nulls_first") is False
        assert "NULLS LAST" in target_sql
    elif index == 5:
        assert isinstance(target.expressions[0], exp.GT)
        assert isinstance(target.find(exp.StrPosition), exp.StrPosition)
    else:
        typed = annotate_types(target, dialect="postgres")
        assert isinstance(typed.expressions[0], exp.Cast)
        assert typed.expressions[0].type.this is exp.DType.TEXT


def test_repository_fixture_is_the_exact_seven_statement_report() -> None:
    statements = parse(_report_script(), read="vertica")

    assert len(statements) == 7
    assert [type(statement) for statement in statements] == [exp.Create, *([exp.Select] * 6)]
    for statement, comment in zip(statements, REPORT_COMMENTS):
        assert comment in statement.sql(dialect="vertica")
        assert not isinstance(statement, exp.Command)


@pytest.mark.parametrize("level", GENERATOR_LEVELS)
@pytest.mark.parametrize("index", range(7))
def test_report_cases_transpile_warning_free_and_reparse(
    index: int,
    level: ErrorLevel | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    expression = parse(_report_script(), read="vertica")[index]
    before = expression.dump()

    with caplog.at_level(logging.WARNING, logger="sqlglot"):
        target_sql = _postgres_sql(expression, level)

    assert not caplog.records
    assert expression.dump() == before
    _assert_target_shape(index, target_sql)


@pytest.mark.parametrize("pretty", (False, True))
def test_commented_report_script_preserves_boundaries_and_reparses(pretty: bool) -> None:
    statements = parse(_report_script(), read="vertica")
    targets = [
        _postgres_sql(statement, ErrorLevel.RAISE, pretty=pretty) for statement in statements
    ]
    target_script = ";\n".join(targets) + ";"

    assert len(parse(target_script, read="postgres")) == 7
    for index, (statement, target_sql, comment) in enumerate(
        zip(statements, targets, REPORT_COMMENTS)
    ):
        assert comment in target_sql
        _assert_target_shape(index, target_sql)
        for tree in (
            exp.Expr.load(statement.dump()),
            statement.copy(),
            statement.transform(lambda node: node),
        ):
            assert tree == statement
            assert all(node is tree or node.parent is not None for node in tree.walk())


def test_composed_workload_survives_source_analysis_and_postgres_lowering() -> None:
    source = parse_one(COMPOSED_SQL, read="vertica")
    assert isinstance(source, exp.Create)
    query = source.expression
    assert isinstance(query, exp.Select)
    before = source.dump()

    analyzed_queries = (
        exp.Expr.load(query.dump()),
        query.copy(),
        query.transform(lambda node: node),
        qualify(query.copy(), dialect="vertica", schema=COMPOSED_SCHEMA),
        optimize(query.copy(), dialect="vertica", schema=COMPOSED_SCHEMA),
        annotate_types(query.copy(), dialect="vertica", schema=COMPOSED_SCHEMA),
    )
    for analyzed in analyzed_queries:
        assert isinstance(analyzed.find(vexp.PartitionedLimit), vexp.PartitionedLimit)
        assert analyzed.find(vexp.StatementTimestamp) is not None
        assert analyzed.find(vexp.UtcStatementTimestamp) is not None
        assert analyzed.find(vexp.VerticaToChar) is not None
        assert analyzed.find(vexp.VerticaRegexpLike) is not None
        assert len(list(traverse_scope(analyzed))) == 1

    optimized = optimize(query.copy(), dialect="vertica", schema=COMPOSED_SCHEMA)
    assert optimize(optimized.copy(), dialect="vertica", schema=COMPOSED_SCHEMA) == optimized
    assert lineage("x", query, dialect="vertica", schema=COMPOSED_SCHEMA).downstream

    for pretty in (False, True):
        target_sql = source.sql(
            dialect="postgres",
            unsupported_level=ErrorLevel.RAISE,
            pretty=pretty,
        )
        target = parse_one(target_sql, read="postgres")
        assert isinstance(target, exp.Create)
        assert target.find(exp.TemporaryProperty) is not None
        assert target.find(exp.RowNumber) is not None
        assert target.find(exp.StrPosition) is not None
        assert target_sql.count("STATEMENT_TIMESTAMP()") == 2
        assert "AT TIME ZONE 'UTC'" in target_sql
        assert "NULLS FIRST" in target_sql
        assert "NULLS LAST" in target_sql
        assert "q39 composed PostgreSQL lowering" in target_sql

    assert source.dump() == before


@pytest.mark.parametrize("level", GENERATOR_LEVELS)
@pytest.mark.parametrize(("source", "message"), UNSAFE_POSTGRES_CASES)
def test_documented_unsafe_boundaries_are_atomic_and_keep_following_statement(
    source: str,
    message: str,
    level: ErrorLevel | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    statements = parse(f"{source}; SELECT 1 AS sentinel;", read="vertica")
    assert len(statements) == 2

    with caplog.at_level(logging.WARNING, logger="sqlglot"), pytest.raises(ValueError) as error:
        _postgres_sql(statements[0], level)

    assert message in str(error.value)
    assert "Unsupported expression type" not in str(error.value)
    assert not caplog.records
    assert statements[1].sql(dialect="postgres") == "SELECT 1 AS sentinel"
