"""Vertica optimizer-hint placement and AST regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_select_and_join_hints_are_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "SELECT /*+SYNTACTIC_JOIN,VERBATIM*/ * FROM x "
        "JOIN /*+JTYPE(FM),DISTRIB(L,R)*/ y ON x.a=y.a",
        "SELECT /*+ SYNTACTIC_JOIN, VERBATIM */ * FROM x "
        "JOIN /*+ JTYPE(FM), DISTRIB(L, R) */ y ON x.a = y.a",
    )

    assert isinstance(expression.args["hint"], exp.Hint)
    join = expression.args["joins"][0]
    assert isinstance(join.args["hint"], exp.Hint)
    assert not join.comments


def test_table_hint_after_alias_is_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "SELECT * FROM public.t AS t /*+PROJS('public.t_p'),SKIP_PROJS('public.old')*/",
        "SELECT * FROM public.t AS t /*+ PROJS('public.t_p'), SKIP_PROJS('public.old') */",
    )

    table = expression.find(exp.Table)
    assert table is not None
    assert len(table.args["hints"]) == 1
    assert isinstance(table.args["hints"][0], vexp.TableOptimizerHint)
    assert not table.args["alias"].comments


def test_table_hint_without_alias_is_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "SELECT * FROM public.t /*+PROJS('public.t_p')*/",
        "SELECT * FROM public.t /*+ PROJS('public.t_p') */",
    )
    table = expression.find(exp.Table)
    assert table is not None
    assert isinstance(table.args["hints"][0], vexp.TableOptimizerHint)


def test_with_hint_is_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ x AS (SELECT 1) SELECT * FROM x",
        "WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ x AS (SELECT 1) SELECT * FROM x",
    )

    with_expression = expression.args["with_"]
    assert isinstance(with_expression, vexp.WithHint)
    assert isinstance(with_expression.args["hint"], exp.Hint)
    assert not with_expression.comments


def test_recursive_with_hint_keeps_hint_before_recursive_keyword() -> None:
    assert_roundtrip(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ RECURSIVE "
        "x(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM x WHERE n < 2) SELECT * FROM x",
        "WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ RECURSIVE "
        "x(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM x WHERE n < 2) SELECT * FROM x",
    )


def test_explain_hint_and_options_are_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "EXPLAIN /*+ALLNODES*/ LOCAL VERBOSE JSON ANNOTATED SELECT * FROM t",
        "EXPLAIN /*+ ALLNODES */ LOCAL VERBOSE JSON ANNOTATED SELECT * FROM t",
    )

    assert isinstance(expression, vexp.Explain)
    assert isinstance(expression.args["hint"], exp.Hint)
    assert [option.name for option in expression.args["options"]] == [
        "LOCAL",
        "VERBOSE",
        "JSON",
        "ANNOTATED",
    ]
    assert isinstance(expression.this, exp.Select)


def test_explain_without_hint_or_options_and_describe_fallback() -> None:
    assert_roundtrip("EXPLAIN SELECT 1")
    assert_roundtrip("DESCRIBE t")


def test_explain_requires_a_statement() -> None:
    with pytest.raises(ParseError, match="EXPLAIN requires a SQL statement"):
        parse_one("EXPLAIN", read="vertica")


@pytest.mark.parametrize(
    ("sql", "expected", "expression_type"),
    [
        (
            "UPDATE /*+LABEL(update_job)*/ t SET a=1",
            "UPDATE /*+ LABEL(update_job) */ t SET a = 1",
            exp.Update,
        ),
        (
            "DELETE /*+LABEL(delete_job)*/ FROM t WHERE a=1",
            "DELETE /*+ LABEL(delete_job) */ FROM t WHERE a = 1",
            exp.Delete,
        ),
        (
            "INSERT /*+LABEL(insert_job)*/ INTO t VALUES (1)",
            "INSERT /*+ LABEL(insert_job) */ INTO t VALUES (1)",
            exp.Insert,
        ),
        (
            "MERGE /*+LABEL(merge_job)*/ INTO target AS t USING source AS s "
            "ON t.id=s.id WHEN MATCHED THEN UPDATE SET value=s.value "
            "WHEN NOT MATCHED THEN INSERT (id,value) VALUES (s.id,s.value)",
            "MERGE /*+ LABEL(merge_job) */ INTO target AS t USING source AS s "
            "ON t.id = s.id WHEN MATCHED THEN UPDATE SET value = s.value "
            "WHEN NOT MATCHED THEN INSERT (id, value) VALUES (s.id, s.value)",
            vexp.VerticaMerge,
        ),
    ],
)
def test_dml_hints_are_structured_and_placed_exactly(
    sql: str, expected: str, expression_type: type[exp.Expr]
) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, expression_type)
    assert isinstance(expression.args["hint"], exp.Hint)


def test_merge_without_hint_retains_canonical_sqlglot_ast() -> None:
    expression = assert_roundtrip(
        "MERGE INTO target AS t USING source AS s ON t.id = s.id "
        "WHEN MATCHED THEN UPDATE SET value = s.value"
    )
    assert type(expression) is exp.Merge


def test_copy_hint_is_structured_and_placed_exactly() -> None:
    expression = assert_roundtrip(
        "COPY /*+LABEL('daily_load')*/ t FROM STDIN",
        "COPY /*+ LABEL('daily_load') */ t FROM STDIN",
    )

    assert isinstance(expression, vexp.VerticaCopy)
    assert isinstance(expression.args["hint"], exp.Hint)
    assert not expression.comments


def test_ordinary_copy_comment_is_not_promoted_to_label_hint() -> None:
    expression = assert_roundtrip("COPY /* LABEL(ordinary_comment) */ t FROM STDIN")
    assert isinstance(expression, vexp.VerticaCopy)
    assert not expression.args.get("hint")
    assert expression.comments == [" LABEL(ordinary_comment) "]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t JOIN /* ordinary explanation */ y ON t.a = y.a",
        "SELECT * FROM t AS alias /* table-info: ordinary */",
        "WITH /* not-a-hint! */ x AS (SELECT 1) SELECT * FROM x",
    ],
)
def test_ordinary_comments_are_not_promoted_to_hints(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert not list(expression.find_all(exp.Hint))
    assert "/*+" not in expression.sql(dialect="vertica")
    assert any(node.comments for node in expression.walk())


def test_hint_generation_never_inserts_space_between_comment_opener_and_plus() -> None:
    expression = assert_roundtrip(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ x AS (SELECT 1) "
        "SELECT /*+LABEL(query_job)*/ * FROM x "
        "JOIN /*+JTYPE(H)*/ y ON x.a = y.a"
    )
    assert "/* +" not in expression.sql(dialect="vertica")


def test_hint_table_override_preserves_non_table_from_expressions() -> None:
    assert_roundtrip("SELECT * FROM (SELECT 1) AS nested_query")


def test_programmatic_hint_on_comma_join_is_reported_as_unsupported() -> None:
    join = exp.Join(
        this=exp.to_table("y"),
        hint=exp.Hint(expressions=[exp.Anonymous(this="JTYPE", expressions=[exp.var("FM")])]),
    )
    with pytest.raises(UnsupportedError, match="require an explicit JOIN"):
        join.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
