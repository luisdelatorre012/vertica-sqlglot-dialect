"""Vertica optimizer-hint placement and AST regressions."""
# ruff: noqa: E501 -- ISSUE_2_SQL is a verbatim public regression fixture.

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, TokenType, exp, parse, parse_one
from sqlglot.dialects import Dialect
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.lineage import lineage
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from sqlglot_vertica import expressions as vexp
from sqlglot_vertica.tokens import OptimizerHintComment
from tests.helpers import assert_roundtrip

ISSUE_2_SQL = """--dialect: vertica
--
-- PATTERN: pattern_a
-- TYPE: join (multi-entry)
--
-- ENTRY_POINTS
-- - name: entry_a
--   description: >
--      Given an upstream col_f set, rank/select one row per col_a using col_e/date tie-breaks.
--   prerequisite_grain: col_f (import)
--   prerequisite_columns: [col_f]
--   output_grain: one row per col_f
--   output_columns: [col_f, col_c, col_d]
--   parameters: [tie_break_order (default: col_e desc, date_entry desc, date_import desc)]
--   notes: >
--        Tie-break does not have to be fully deterministic; defaults are usually sufficient for most reporting.
--
--  - name: entry_b
--  description: >
--    Given selected rows joined to updstream col_f rows, roll up max col_g.
--   prerequisite_grain: col_f
--   prerequisite_columns: [col_f]
--   output_grain: one row per col_f
--   output_columns: [col_f, col_h]
-- notes: >
--     Template performs line aggregation after rank-select join; keep aggregation scoped to upstream rows.
WITH cte_a AS (
    SELECT
        t1.col_a,
        t1.col_b,
        t1.col_c,
        t1.col_d,
        ROW_NUMBER() OVER (PARTITION by t1.col_a ORDER BY t1.col_e DESC) AS rn
    FROM schema_a.tabe_a AS t1
)

SELECT
    t2.col_f,
    t1.col_c,
    t1.col_d,
    MAX(t3.col_g) as col_h
FROM upstream_cte AS t2
INNER JOIN cte_a AS t1
    ON
        t2.col_f = t1.col_a
        AND t1.rn = 1
LEFT JOIN schema_a.table_b AS t3
    ON t1.col_b = t3.col_b
GROUP BY
    t2.col_f,
    t1.col_c,
    t1.col_d;
"""


ISSUE_2_SCHEMA = {
    "schema_a": {
        "tabe_a": {
            "col_a": "INT",
            "col_b": "INT",
            "col_c": "INT",
            "col_d": "INT",
            "col_e": "INT",
        },
        "table_b": {"col_b": "INT", "col_g": "INT"},
    },
    "public": {"upstream_cte": {"col_f": "INT"}},
}


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


@pytest.mark.parametrize(
    "comment",
    ["--\n", "--   \n", "/* */", "/*   */", "/* !@#$%^& */"],
)
@pytest.mark.parametrize(
    "sql_template",
    [
        "WITH {comment} x AS (SELECT 1) SELECT * FROM x",
        "SELECT * FROM public.t {comment}",
        "SELECT * FROM public.t AS t {comment}",
        "SELECT * FROM x JOIN {comment} y ON x.a = y.a",
        "CREATE TABLE q26_out AS {comment} SELECT 1 AS id",
    ],
)
def test_empty_and_prose_comments_bypass_shared_hint_extraction(
    sql_template: str, comment: str
) -> None:
    expression = parse_one(sql_template.format(comment=comment), read="vertica")
    generated = expression.sql(dialect="vertica")

    assert not isinstance(expression, exp.Command)
    assert not list(expression.find_all(exp.Hint))
    assert not list(expression.find_all(vexp.WithHint))
    assert not list(expression.find_all(vexp.CtasHintProperty))
    assert not list(expression.find_all(vexp.TableOptimizerHint))
    assert parse_one(generated, read="vertica") is not None


@pytest.mark.parametrize(
    ("sql", "comment_body"),
    [
        (
            "WITH {comment} x AS (SELECT 1) SELECT * FROM x",
            "ENABLE_WITH_CLAUSE_MATERIALIZATION",
        ),
        ("SELECT * FROM public.t {comment}", "PROJS('public.t_p')"),
        ("SELECT * FROM public.t AS t {comment}", "SKIP_PROJS('public.old')"),
        ("SELECT * FROM x JOIN {comment} y ON x.a = y.a", "JTYPE(H)"),
        ("CREATE TABLE q26_out AS {comment} SELECT 1 AS id", "LABEL(ctas_job)"),
    ],
)
@pytest.mark.parametrize("comment_template", ["-- {body}\n", "/* {body} */"])
def test_allowed_hint_text_in_an_ordinary_comment_stays_inert(
    sql: str, comment_body: str, comment_template: str
) -> None:
    comment = comment_template.format(body=comment_body)
    expression = parse_one(sql.format(comment=comment), read="vertica")
    generated = expression.sql(dialect="vertica")

    assert not list(expression.find_all(exp.Hint))
    assert not list(expression.find_all(vexp.WithHint))
    assert not list(expression.find_all(vexp.CtasHintProperty))
    assert not list(expression.find_all(vexp.TableOptimizerHint))
    assert comment_body in generated
    assert "/*+" not in generated


def test_exact_plus_hint_provenance_is_distinct_from_ordinary_comments() -> None:
    tokens = (
        Dialect.get_or_raise("vertica")
        .tokenizer()
        .tokenize(
            "WITH /* ordinary */ /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ "
            "x AS (SELECT 1) SELECT * FROM x"
        )
    )
    comments = [comment for token in tokens for comment in token.comments]

    assert type(comments[0]) is str
    assert isinstance(comments[1], OptimizerHintComment)


def test_whitespace_before_plus_retains_optimizer_hint_provenance() -> None:
    tokens = (
        Dialect.get_or_raise("vertica").tokenizer().tokenize("SELECT /* + LABEL(query_job) */ 1")
    )

    assert [token.token_type for token in tokens] == [
        TokenType.SELECT,
        TokenType.HINT,
        TokenType.NUMBER,
    ]
    assert isinstance(tokens[1].comments[0], OptimizerHintComment)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT /* + LABEL(query_job) */ 1", "SELECT /*+ LABEL(query_job) */ 1"),
        (
            "EXPLAIN /* + ALLNODES */ SELECT 1",
            "EXPLAIN /*+ ALLNODES */ SELECT 1",
        ),
        (
            "WITH /* + ENABLE_WITH_CLAUSE_MATERIALIZATION */ x AS (SELECT 1) SELECT * FROM x",
            "WITH /*+ ENABLE_WITH_CLAUSE_MATERIALIZATION */ x AS (SELECT 1) SELECT * FROM x",
        ),
        (
            "SELECT * FROM t /* + PROJS('t_p') */",
            "SELECT * FROM t /*+ PROJS('t_p') */",
        ),
        (
            "SELECT * FROM t AS x /* + SKIP_PROJS('t_old') */",
            "SELECT * FROM t AS x /*+ SKIP_PROJS('t_old') */",
        ),
        (
            "SELECT * FROM t JOIN /* + JTYPE(H), DISTRIB(L,R) */ u ON t.a=u.a",
            "SELECT * FROM t JOIN /*+ JTYPE(H), DISTRIB(L, R) */ u ON t.a = u.a",
        ),
        (
            "CREATE TABLE q27_out AS /* + LABEL(ctas_job) */ SELECT 1",
            "CREATE TABLE q27_out AS /*+ LABEL(ctas_job) */ SELECT 1",
        ),
        (
            "INSERT /* + LABEL(insert_job) */ INTO t VALUES (1)",
            "INSERT /*+ LABEL(insert_job) */ INTO t VALUES (1)",
        ),
        (
            "COPY /* + LABEL(copy_job) */ t FROM STDIN",
            "COPY /*+ LABEL(copy_job) */ t FROM STDIN",
        ),
    ],
)
def test_whitespace_before_plus_hints_canonicalize_to_compact_opener(
    sql: str, expected: str
) -> None:
    assert_roundtrip(sql, expected)


def test_ordinary_comment_with_unrelated_plus_stays_inert() -> None:
    expression = assert_roundtrip("SELECT * FROM t /* metadata + arithmetic */")
    assert not list(expression.find_all(exp.Hint))
    assert "/*+" not in expression.sql(dialect="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "WITH /* + EARLY_MATERIALIZATION */ x AS (SELECT 1) SELECT * FROM x",
        "SELECT * FROM t /* + UNKNOWN_HINT(x) */",
        "SELECT a FROM t GROUP BY /* + UTYPE(B) */ a",
    ],
)
def test_well_formed_unmodeled_hint_retains_plus_identity(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    restored = exp.Expr.load(expression.dump())
    copied = expression.copy().transform(lambda node: node)

    for candidate in (expression, restored, copied):
        generated = candidate.sql(dialect="vertica")
        assert "/*+" in generated
        assert parse_one(generated, read="vertica") is not None


def test_mixed_ordinary_and_genuine_hint_comments_promote_only_the_genuine_hint() -> None:
    expression = assert_roundtrip(
        "WITH /* metadata one */ /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ "
        "/* metadata two */ x AS (SELECT 1) SELECT * FROM x"
    )
    with_expression = expression.args["with_"]

    assert isinstance(with_expression, vexp.WithHint)
    assert isinstance(with_expression.args["hint"], exp.Hint)
    generated = expression.sql(dialect="vertica")
    assert generated.count("/*+") == 1
    assert generated.index("metadata one") < generated.index("metadata two")


@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_issue_2_exact_fixture_parses_at_every_error_level(
    error_level: ErrorLevel, caplog: pytest.LogCaptureFixture
) -> None:
    statements = parse(ISSUE_2_SQL, read="vertica", error_level=error_level)

    assert len(statements) == 1
    expression = statements[0]
    assert type(expression) is exp.Select
    assert type(expression.args["with_"]) is exp.With
    assert isinstance(expression.args["group"], vexp.VerticaGroup)
    assert len(expression.args["joins"]) == 2
    assert {join.side for join in expression.args["joins"]} == {"", "LEFT"}
    assert expression.find(exp.Window) is not None
    assert not list(expression.find_all(exp.Hint))
    assert not caplog.records


def test_issue_2_fixture_roundtrips_and_preserves_nonempty_metadata_comments() -> None:
    expression = parse(ISSUE_2_SQL, read="vertica")[0]
    assert expression is not None
    generated = expression.sql(dialect="vertica")
    reparsed = parse(generated, read="vertica")
    pretty = expression.sql(dialect="vertica", pretty=True)

    assert reparsed == [expression]
    assert parse(pretty, read="vertica") == [expression]
    assert exp.Expr.load(expression.dump()) == expression
    for metadata in (
        "dialect: vertica",
        "PATTERN: pattern_a",
        "TYPE: join (multi-entry)",
        "ENTRY_POINTS",
        "Template performs line aggregation",
    ):
        assert metadata in generated
    assert "/*+" not in generated


def test_issue_2_fixture_copy_transform_parents_and_analysis() -> None:
    expression = parse(ISSUE_2_SQL, read="vertica")[0]
    assert isinstance(expression, exp.Select)
    copied = expression.copy()
    transformed = copied.transform(lambda node: node)

    assert transformed == expression
    assert all(node is transformed or node.parent is not None for node in transformed.walk())
    assert list(traverse_scope(expression))

    qualified = qualify(expression.copy(), dialect="vertica", schema=ISSUE_2_SCHEMA)
    optimized = optimize(expression.copy(), dialect="vertica", schema=ISSUE_2_SCHEMA)
    for analyzed in (qualified, optimized):
        assert isinstance(analyzed, exp.Select)
        assert isinstance(analyzed.args["group"], vexp.VerticaGroup)
        assert list(traverse_scope(analyzed))
        assert parse_one(analyzed.sql(dialect="vertica"), read="vertica") == analyzed

    node = lineage("col_h", expression, schema=ISSUE_2_SCHEMA, dialect="vertica")
    assert any(downstream.name == "t3.col_g" for downstream in node.walk())


@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_blank_comment_reproducer_does_not_swallow_following_statement(
    error_level: ErrorLevel,
) -> None:
    statements = parse(
        "WITH --\n x AS (SELECT 1 AS a) SELECT a FROM x; SELECT 2;",
        read="vertica",
        error_level=error_level,
    )
    assert [type(statement) for statement in statements] == [exp.Select, exp.Select]


def test_hint_generation_never_inserts_space_between_comment_opener_and_plus() -> None:
    expression = assert_roundtrip(
        "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ x AS (SELECT 1) "
        "SELECT /*+LABEL(query_job)*/ * FROM x "
        "JOIN /*+JTYPE(H)*/ y ON x.a = y.a"
    )
    assert "/* +" not in expression.sql(dialect="vertica")


MALFORMED_HINT_SITES = [
    "SELECT {hint} 1",
    "EXPLAIN {hint} SELECT 1",
    "WITH {hint} x AS (SELECT 1) SELECT * FROM x",
    "SELECT * FROM t {hint}",
    "SELECT * FROM t AS x {hint}",
    "SELECT * FROM t JOIN {hint} u ON t.a = u.a",
    "SELECT a FROM t GROUP BY {hint} a",
    "CREATE TABLE q27_out AS {hint} SELECT 1",
    "INSERT {hint} INTO t VALUES (1)",
    "UPDATE {hint} t SET a = 1",
    "DELETE {hint} FROM t",
    "MERGE {hint} INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET a = s.a",
    "COPY {hint} t FROM STDIN",
]


@pytest.mark.parametrize("sql_template", MALFORMED_HINT_SITES)
@pytest.mark.parametrize("hint", ["/*+LABEL(*/", "/* + LABEL( */"])
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_malformed_hint_fails_closed_at_every_owner_and_error_level(
    sql_template: str,
    hint: str,
    error_level: ErrorLevel,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with pytest.raises(ParseError, match="Malformed Vertica optimizer hint"):
        parse_one(sql_template.format(hint=hint), read="vertica", error_level=error_level)
    assert not caplog.records


@pytest.mark.parametrize(
    "body",
    ["", "   ", "LABEL(", "LABEL(x,)", "LABEL(x),", "LABEL(,x)"],
)
@pytest.mark.parametrize("spaced", [False, True])
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_structurally_malformed_hint_bodies_fail_closed(
    body: str, spaced: bool, error_level: ErrorLevel
) -> None:
    hint = f"/* + {body} */" if spaced else f"/*+{body}*/"
    with pytest.raises(ParseError):
        parse_one(f"SELECT {hint} 1", read="vertica", error_level=error_level)


@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_malformed_hint_does_not_swallow_following_statement(error_level: ErrorLevel) -> None:
    with pytest.raises(ParseError, match="Malformed Vertica optimizer hint"):
        parse(
            "INSERT /*+LABEL(*/ INTO t VALUES (1); SELECT 2;",
            read="vertica",
            error_level=error_level,
        )


def test_mixed_whitespace_hint_query_preserves_analysis_and_parents() -> None:
    sql = (
        "WITH /* + ENABLE_WITH_CLAUSE_MATERIALIZATION */ q AS ("
        "SELECT t.a, SUM(u.v) AS total FROM t /* + PROJS('t_p') */ "
        "JOIN /* + JTYPE(H), DISTRIB(L,R) */ u ON t.a = u.a "
        "GROUP BY /* + GBYTYPE(HASH) */ t.a) "
        "SELECT /* + LABEL(report_job) */ a, total FROM q"
    )
    schema = {"t": {"a": "INT"}, "u": {"a": "INT", "v": "INT"}}
    expression = assert_roundtrip(sql)
    restored = exp.Expr.load(expression.dump())
    transformed = expression.copy().transform(lambda node: node)

    assert restored == expression
    assert transformed == expression
    assert all(node is transformed or node.parent is not None for node in transformed.walk())
    assert list(traverse_scope(expression))

    for analyzed in (
        qualify(expression.copy(), dialect="vertica", schema=schema),
        optimize(expression.copy(), dialect="vertica", schema=schema),
    ):
        assert list(traverse_scope(analyzed))
        generated = analyzed.sql(dialect="vertica")
        assert parse_one(generated, read="vertica").sql(dialect="vertica") == generated

    node = lineage("total", expression, dialect="vertica", schema=schema)
    assert any(downstream.name == "u.v" for downstream in node.walk())


def test_malformed_programmatic_hint_trees_fail_before_generation() -> None:
    cases: list[exp.Expr] = [
        exp.Hint(expressions=["LABEL("]),
        exp.Select(expressions=[exp.Literal.number(1)], hint=exp.Hint(expressions=[None])),
        parse_one(
            "WITH /*+ENABLE_WITH_CLAUSE_MATERIALIZATION*/ x AS (SELECT 1) SELECT * FROM x",
            read="vertica",
        ),
        parse_one("SELECT * FROM t /*+PROJS('t_p')*/", read="vertica"),
        parse_one("SELECT * FROM t JOIN /*+JTYPE(H)*/ u ON t.a=u.a", read="vertica"),
        parse_one("CREATE TABLE q27_out AS /*+LABEL(job)*/ SELECT 1", read="vertica"),
        parse_one("INSERT /*+LABEL(job)*/ INTO t VALUES (1)", read="vertica"),
    ]
    malformed = exp.Hint(expressions=[exp.Anonymous(this="LABEL", expressions=["bad"])])
    cases[2].args["with_"].set("hint", malformed.copy())
    table_hint = cases[3].find(vexp.TableOptimizerHint)
    assert table_hint is not None
    table_hint.set("expressions", ["PROJS("])
    cases[4].args["joins"][0].set("hint", malformed.copy())
    ctas_hint = cases[5].find(vexp.CtasHintProperty)
    assert ctas_hint is not None
    ctas_hint.set("this", malformed.copy())
    cases[6].set("hint", malformed.copy())

    for expression in cases:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_hint_table_override_preserves_non_table_from_expressions() -> None:
    assert_roundtrip("SELECT * FROM (SELECT 1) AS nested_query")


def test_programmatic_hint_on_comma_join_is_reported_as_unsupported() -> None:
    join = exp.Join(
        this=exp.to_table("y"),
        hint=exp.Hint(expressions=[exp.Anonymous(this="JTYPE", expressions=[exp.var("FM")])]),
    )
    with pytest.raises(UnsupportedError, match="require an explicit JOIN"):
        join.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
