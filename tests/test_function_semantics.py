"""Vertica-specific function syntax and semantic-preservation contracts."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT APPROXIMATE_PERCENTILE(x USING PARAMETERS percentiles='0.5,0.9') FROM t",
            "SELECT APPROXIMATE_PERCENTILE(x USING PARAMETERS percentiles = '0.5,0.9') FROM t",
        ),
        (
            "SELECT MAPLOOKUP(__raw__, 'name' USING PARAMETERS "
            "case_sensitive=TRUE, buffer_size=10) FROM logs",
            "SELECT MAPLOOKUP(__raw__, 'name' USING PARAMETERS "
            "case_sensitive = TRUE, buffer_size = 10) FROM logs",
        ),
        (
            "SELECT STV_DESCRIBE_INDEX(USING PARAMETERS index='ix') OVER()",
            "SELECT STV_DESCRIBE_INDEX(USING PARAMETERS index = 'ix') OVER ()",
        ),
        (
            "SELECT INFER_TABLE_DDL('/data/*.orc' USING PARAMETERS "
            "format='orc', table_name='orders')",
            "SELECT INFER_TABLE_DDL('/data/*.orc' USING PARAMETERS "
            "format = 'orc', table_name = 'orders')",
        ),
    ],
)
def test_generic_using_parameters_roundtrip(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    parameterized = expression.find(vexp.UsingParameters)

    assert parameterized is not None
    assert isinstance(parameterized.this, exp.Func)
    assert all(
        isinstance(parameter, exp.PropertyEQ) for parameter in parameterized.args["parameters"]
    )


def test_using_parameters_preserves_order_and_server_semantics() -> None:
    expression = assert_roundtrip(
        "SELECT custom_udx(x USING PARAMETERS unknown=1, unknown=2, mode='server')",
        "SELECT CUSTOM_UDX(x USING PARAMETERS unknown = 1, unknown = 2, mode = 'server')",
    )
    parameterized = expression.find(vexp.UsingParameters)
    assert parameterized is not None
    assert [parameter.name for parameter in parameterized.args["parameters"]] == [
        "unknown",
        "unknown",
        "mode",
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT f(x USING)",
        "SELECT f(x USING PARAMETER p=1)",
        "SELECT f(x USING PARAMETERS p)",
        "SELECT f(x USING PARAMETERS p=)",
        "SELECT f(x USING PARAMETERS p=1, y)",
        "SELECT f(x USING PARAMETERS p=1 USING PARAMETERS q=2)",
    ],
)
def test_using_parameters_rejects_only_malformed_structure(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_explode_and_unnest_remain_semantically_distinct() -> None:
    expression = assert_roundtrip(
        "SELECT EXPLODE(a, b) OVER() AS (a_pos, a_value, b_pos, b_value), UNNEST(a) FROM t",
        "SELECT EXPLODE(a, b) OVER () AS (a_pos, a_value, b_pos, b_value), UNNEST(a) FROM t",
    )
    explode = expression.find(vexp.VerticaExplode)

    assert explode is not None and isinstance(explode.this, exp.Explode)
    assert len(list(expression.find_all(exp.Explode))) == 2
    assert type(expression.expressions[1]) is exp.Explode


def test_explode_retains_generic_using_parameters() -> None:
    expression = assert_roundtrip(
        "SELECT EXPLODE(a USING PARAMETERS explode_count=1, with_offset=FALSE) OVER() FROM t",
        "SELECT EXPLODE(a USING PARAMETERS explode_count = 1, with_offset = FALSE) OVER () FROM t",
    )
    parameterized = expression.find(vexp.UsingParameters)

    assert parameterized is not None
    assert isinstance(parameterized.this, vexp.VerticaExplode)
    assert isinstance(parameterized.this.this, exp.Explode)
    assert [parameter.name for parameter in parameterized.args["parameters"]] == [
        "explode_count",
        "with_offset",
    ]


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("SELECT ARRAY_LENGTH(a) FROM t", "SELECT ARRAY_LENGTH(a) FROM t"),
        (
            "SELECT FILTER(a, e -> e IS NOT NULL) FROM t",
            "SELECT FILTER(a, e -> NOT e IS NULL) FROM t",
        ),
        (
            "SELECT REGEXP_LIKE(s, '^a', 'i', 'm') FROM t",
            "SELECT REGEXP_LIKE(s, '^a', 'i', 'm') FROM t",
        ),
        ("SELECT INSTR(s, 'a') FROM t", "SELECT INSTR(s, 'a') FROM t"),
        ("SELECT INSTR(s, 'a', -1) FROM t", "SELECT INSTR(s, 'a', -1) FROM t"),
        (
            "SELECT INSTR(s, 'a', -1, 2) FROM t",
            "SELECT INSTR(s, 'a', -1, 2) FROM t",
        ),
        (
            "SELECT TO_HEX(123), SHA1(s), INSERT(s, 2, 1, 'x') FROM t",
            "SELECT TO_HEX(123), SHA1(s), INSERT(s, 2, 1, 'x') FROM t",
        ),
    ],
)
def test_function_semantics_generate_exact_vertica(sql: str, expected: str) -> None:
    assert_roundtrip(sql, expected)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT ARRAY_LENGTH()",
        "SELECT ARRAY_LENGTH(a, 2)",
        "SELECT EXPLODE()",
        "SELECT REGEXP_LIKE(s)",
        "SELECT INSTR(s)",
        "SELECT INSTR(s, p, 1, 2, 3)",
    ],
)
def test_source_sensitive_functions_reject_invalid_arity(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_greatest_and_least_propagate_nulls_in_the_ast() -> None:
    expression = assert_roundtrip("SELECT GREATEST(1, NULL), LEAST(NULL, 2)")

    greatest = expression.find(exp.Greatest)
    least = expression.find(exp.Least)
    assert greatest is not None and greatest.args["ignore_nulls"] is False
    assert least is not None and least.args["ignore_nulls"] is False


def test_function_nodes_remain_optimizer_visible_and_typed() -> None:
    expression = optimize(
        parse_one(
            "SELECT ARRAY_LENGTH(a), FILTER(a, e -> e > 0), "
            "REGEXP_LIKE(s, 'a', 'i'), INSTR(s, 'a', -1, 2), "
            "TO_HEX(n), SHA1(s), INSERT(s, 2, 1, 'x') FROM t",
            read="vertica",
        ),
        dialect="vertica",
        schema={"t": {"a": "ARRAY<INT>", "s": "VARCHAR", "n": "INT"}},
    )

    assert len(list(expression.find_all(exp.ArraySize))) == 1
    assert len(list(expression.find_all(exp.ArrayFilter))) == 1
    assert len(list(expression.find_all(exp.RegexpLike))) == 1
    assert len(list(expression.find_all(exp.StrPosition))) == 1
    assert [item.type.this for item in expression.expressions] == [
        exp.DType.BIGINT,
        exp.DType.ARRAY,
        exp.DType.BOOLEAN,
        exp.DType.BIGINT,
        exp.DType.VARCHAR,
        exp.DType.VARCHAR,
        exp.DType.VARCHAR,
    ]
    assert "ARRAY(SELECT" not in expression.sql(dialect="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT custom_udx(x USING PARAMETERS p=1)",
        "SELECT EXPLODE(a) OVER() FROM t",
        "SELECT ARRAY_LENGTH(a) FROM t",
        "SELECT REGEXP_LIKE(s, 'a', 'i') FROM t",
        "SELECT INSTR(s, 'a', -1, 2) FROM t",
    ],
)
def test_vertica_only_function_semantics_fail_atomically_in_postgres(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises(ValueError, match="Unsupported expression type"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_using_parameters_programmatic_shape_is_validated() -> None:
    malformed = vexp.UsingParameters(
        this=exp.column("x"),
        parameters=[exp.PropertyEQ(this=exp.to_identifier("p"), expression=exp.Literal.number(1))],
    )
    with pytest.raises(UnsupportedError, match="function-call child"):
        malformed.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    empty = vexp.UsingParameters(this=exp.Anonymous(this="f"), parameters=[])
    with pytest.raises(UnsupportedError, match="at least one parameter"):
        empty.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        (
            "SELECT CHAR_LENGTH(name USING OCTETS) FROM people",
            "SELECT CHAR_LENGTH(name USING OCTETS) FROM people",
        ),
        (
            "SELECT CHARACTER_LENGTH(name USING CHARACTERS) FROM people",
            "SELECT CHARACTER_LENGTH(name USING CHARACTERS) FROM people",
        ),
        (
            "SELECT POSITION('x' IN name USING CHARACTERS) FROM people",
            "SELECT POSITION('x' IN name USING CHARACTERS) FROM people",
        ),
        (
            "SELECT SUBSTRING(name, 5, 2 USING OCTETS) FROM people",
            "SELECT SUBSTRING(name FROM 5 FOR 2 USING OCTETS) FROM people",
        ),
        (
            "SELECT SUBSTRING(name FROM 5 FOR 2 USING CHARACTERS) FROM people",
            "SELECT SUBSTRING(name FROM 5 FOR 2 USING CHARACTERS) FROM people",
        ),
        (
            "SELECT OVERLAY(name PLACING 'XX' FROM 2 USING OCTETS) FROM people",
            "SELECT OVERLAY(name PLACING 'XX' FROM 2 USING OCTETS) FROM people",
        ),
        (
            "SELECT INSTR(name, 'x' USING OCTETS) FROM people",
            "SELECT INSTR(name, 'x' USING OCTETS) FROM people",
        ),
        (
            "SELECT custom_string(name USING OCTETS) FROM people",
            "SELECT CUSTOM_STRING(name USING OCTETS) FROM people",
        ),
    ],
)
def test_string_unit_modifiers_roundtrip(sql: str, expected: str) -> None:
    expression = assert_roundtrip(sql, expected)
    string_unit = expression.find(vexp.StringUnit)

    assert string_unit is not None
    assert isinstance(string_unit.args["unit"], exp.Var)
    assert string_unit.args["unit"].name in {"CHARACTERS", "OCTETS"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT LENGTH(name USING)",
        "SELECT LENGTH(name USING BYTES)",
        "SELECT LENGTH(name USING OCTETS CHARACTERS)",
        "SELECT LENGTH(name USING OCTETS USING PARAMETERS p=1)",
    ],
)
def test_string_unit_rejects_malformed_structure(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("sql", "expected_type"),
    [
        ("SELECT TO_CHAR(amount) FROM t", vexp.VerticaToChar),
        ("SELECT TO_CHAR(created_at, 'YYYY-MM-DD') FROM t", exp.TimeToStr),
        ("SELECT TO_NUMBER(amount) FROM t", exp.ToNumber),
        ("SELECT TO_NUMBER(amount, '999D99') FROM t", exp.ToNumber),
    ],
)
def test_conversion_function_forms_roundtrip(sql: str, expected_type: type[exp.Expr]) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression.expressions[0], expected_type)


@pytest.mark.parametrize("sql", ["SELECT TO_CHAR()", "SELECT TO_CHAR(a, b, c)"])
def test_to_char_rejects_unsupported_arity(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT FIRST_VALUE(x IGNORE NULLS) OVER() FROM t",
        "SELECT LAST_VALUE(x IGNORE NULLS) OVER() FROM t",
        "SELECT NTH_VALUE(x, 2 IGNORE NULLS) OVER() FROM t",
    ],
)
def test_value_analytic_ignore_nulls_stays_inside_parentheses(sql: str) -> None:
    expression = assert_roundtrip(sql, sql.replace("OVER()", "OVER ()"))
    window = expression.find(exp.Window)

    assert window is not None
    assert isinstance(window.this, exp.IgnoreNulls)


@pytest.mark.parametrize(
    ("mode", "suffix"),
    [
        ("BEST", ""),
        ("NODES", " ORDER BY x"),
        ("ROW", ""),
        ("LEFT JOIN", ""),
    ],
)
def test_special_window_partition_modes_roundtrip(mode: str, suffix: str) -> None:
    sql = f"SELECT custom_transform(x) OVER(PARTITION {mode}{suffix}) FROM t"
    expected = f"SELECT CUSTOM_TRANSFORM(x) OVER (PARTITION {mode}{suffix}) FROM t"
    expression = assert_roundtrip(sql, expected)
    window = expression.find(vexp.VerticaWindow)

    assert window is not None
    assert isinstance(window, exp.Window)
    assert window.args["partition_mode"].name == mode
    assert not window.args.get("partition_by")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT f(x) OVER(PARTITION)",
        "SELECT f(x) OVER(PARTITION LEFT)",
        "SELECT f(x) OVER(PARTITION BEST BY x)",
    ],
)
def test_special_window_partition_modes_reject_malformed_structure(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_p1_function_nodes_remain_optimizer_visible_and_typed() -> None:
    expression = optimize(
        parse_one(
            "SELECT LENGTH(name USING OCTETS), TO_CHAR(amount), TO_NUMBER(amount), "
            "SUM(amount) OVER(PARTITION BEST) FROM t",
            read="vertica",
        ),
        dialect="vertica",
        schema={"t": {"name": "VARCHAR", "amount": "NUMERIC"}},
    )

    assert expression.find(exp.Length) is not None
    assert expression.find(exp.Anonymous, bfs=False) is not None
    assert expression.find(exp.ToNumber) is not None
    assert expression.find(exp.Sum) is not None
    assert isinstance(expression.find(vexp.VerticaWindow), vexp.VerticaWindow)
    assert [item.type.this for item in expression.expressions] == [
        exp.DType.BIGINT,
        exp.DType.VARCHAR,
        exp.DType.DOUBLE,
        exp.DType.DECIMAL,
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT LENGTH(name USING OCTETS) FROM t",
        "SELECT TO_CHAR(amount) FROM t",
        "SELECT SUM(amount) OVER(PARTITION BEST) FROM t",
    ],
)
def test_p1_vertica_function_syntax_fails_atomically_in_postgres(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises(ValueError, match="Unsupported expression type"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_p1_programmatic_shapes_are_validated() -> None:
    malformed_unit = vexp.StringUnit(
        this=exp.Length(this=exp.column("x")),
        unit=exp.var("BYTES"),
        name=exp.var("LENGTH"),
    )
    with pytest.raises(UnsupportedError, match="CHARACTERS or OCTETS"):
        malformed_unit.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    malformed_to_char = vexp.VerticaToChar(
        this=exp.Anonymous(this="TO_CHAR", expressions=[exp.column("x"), exp.column("y")])
    )
    with pytest.raises(UnsupportedError, match="one-argument TO_CHAR"):
        malformed_to_char.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    malformed_window = vexp.VerticaWindow(
        this=exp.Sum(this=exp.column("x")),
        partition_mode=exp.var("ALL"),
        over="OVER",
    )
    with pytest.raises(UnsupportedError, match="special partition mode"):
        malformed_window.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    extended_to_number = exp.ToNumber(
        this=exp.column("x"),
        nlsparam=exp.Literal.string("NLS_NUMERIC_CHARACTERS = ',.'"),
    )
    with pytest.raises(UnsupportedError, match="only value and format"):
        extended_to_number.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
