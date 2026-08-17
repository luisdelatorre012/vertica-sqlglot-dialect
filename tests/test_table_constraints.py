"""Vertica ordinary column and table constraint regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.annotate_types import annotate_types

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def _strict(expression: exp.Expr) -> str:
    return expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def _column_kinds(column: exp.ColumnDef) -> list[exp.Expr]:
    kinds = []
    for constraint in column.args.get("constraints") or []:
        kind = constraint.args.get("kind") if isinstance(constraint, exp.ColumnConstraint) else None
        if kind is not None:
            kinds.append(kind)
    return kinds


# ---------------------------------------------------------------------------
# Column-constraint positives
# ---------------------------------------------------------------------------


def test_column_not_null_and_null() -> None:
    expression = assert_roundtrip("CREATE TABLE t (id BIGINT NOT NULL)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, exp.NotNullColumnConstraint)
    assert not kind.args.get("allow_null")

    expression = assert_roundtrip("CREATE TABLE t (id BIGINT NULL)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, exp.NotNullColumnConstraint)
    assert kind.args.get("allow_null") is True


@pytest.mark.parametrize(
    ("clause", "state", "expected_type"),
    [
        ("PRIMARY KEY", None, exp.PrimaryKeyColumnConstraint),
        ("PRIMARY KEY ENABLED", True, vexp.VerticaPrimaryKeyColumnConstraint),
        ("PRIMARY KEY DISABLED", False, vexp.VerticaPrimaryKeyColumnConstraint),
    ],
)
def test_column_primary_key_enforcement_states(
    clause: str, state: bool | None, expected_type: type[exp.Expr]
) -> None:
    sql = f"CREATE TABLE t (id BIGINT {clause})"
    expression = assert_roundtrip(sql, sql)
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert type(kind) is expected_type
    assert kind.args.get("enforced") is state


@pytest.mark.parametrize(
    ("clause", "expected_type"),
    [
        ("UNIQUE", exp.UniqueColumnConstraint),
        ("UNIQUE ENABLED", vexp.VerticaUniqueColumnConstraint),
        ("UNIQUE DISABLED", vexp.VerticaUniqueColumnConstraint),
    ],
)
def test_column_unique_enforcement_states(clause: str, expected_type: type[exp.Expr]) -> None:
    sql = f"CREATE TABLE t (id BIGINT {clause})"
    expression = assert_roundtrip(sql, sql)
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert type(kind) is expected_type
    assert kind.args.get("this") is None


@pytest.mark.parametrize(
    ("clause", "enforced", "expected_type"),
    [
        ("CHECK (id > 0)", None, exp.CheckColumnConstraint),
        ("CHECK (id > 0) ENABLED", True, vexp.VerticaCheckColumnConstraint),
        ("CHECK (id > 0) DISABLED", False, vexp.VerticaCheckColumnConstraint),
    ],
)
def test_column_check_enforcement_states(
    clause: str, enforced: bool | None, expected_type: type[exp.Expr]
) -> None:
    sql = f"CREATE TABLE t (id BIGINT {clause})"
    expression = assert_roundtrip(sql, sql)
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert type(kind) is expected_type
    assert kind.args.get("enforced") is enforced
    assert isinstance(kind.this, exp.GT)


def test_column_check_expression_traversal_allows_subquery_and_aggregate_residual() -> None:
    """CHECK expression content (subqueries/aggregates) is a documented server-side residual."""

    subquery = assert_roundtrip("CREATE TABLE t (id BIGINT CHECK (id IN (SELECT x FROM y)))")
    check = _column_kinds(subquery.this.expressions[0])[0]
    assert isinstance(check, exp.CheckColumnConstraint)
    assert check.this.find(exp.Select) is not None

    aggregate = assert_roundtrip("CREATE TABLE t (id BIGINT CHECK (id < SUM(id)))")
    check = _column_kinds(aggregate.this.expressions[0])[0]
    assert check.this.find(exp.Sum) is not None


def test_column_references_with_and_without_column() -> None:
    expression = assert_roundtrip("CREATE TABLE t (id BIGINT REFERENCES other)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, exp.Reference)
    assert isinstance(kind.this, exp.Table)

    expression = assert_roundtrip("CREATE TABLE t (id BIGINT REFERENCES other (oid))")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind.this, exp.Schema)
    assert [column.name for column in kind.this.expressions] == ["oid"]


def test_column_default_set_using_and_default_using() -> None:
    expression = assert_roundtrip("CREATE TABLE t (id BIGINT DEFAULT 0)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, exp.DefaultColumnConstraint)

    expression = assert_roundtrip("CREATE TABLE t (id BIGINT SET USING 1)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, vexp.SetUsingColumnConstraint)
    assert kind.this.to_py() == 1

    expression = assert_roundtrip("CREATE TABLE t (id BIGINT DEFAULT USING 1)")
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, vexp.DefaultUsingColumnConstraint)

    sql = "CREATE TABLE t (id BIGINT DEFAULT 0 SET USING 1)"
    expression = assert_roundtrip(sql, sql)
    kinds = _column_kinds(expression.this.expressions[0])
    assert [type(kind) for kind in kinds] == [
        exp.DefaultColumnConstraint,
        vexp.SetUsingColumnConstraint,
    ]


def test_column_constraint_name_allowed_only_for_documented_kinds() -> None:
    sql = "CREATE TABLE t (id BIGINT CONSTRAINT pk PRIMARY KEY)"
    expression = assert_roundtrip(sql, sql)
    constraint = expression.this.expressions[0].args["constraints"][0]
    assert isinstance(constraint, exp.ColumnConstraint)
    assert constraint.this.name == "pk"

    assert_roundtrip(
        "CREATE TABLE t (id BIGINT CONSTRAINT ck CHECK (id > 0) ENABLED)",
        "CREATE TABLE t (id BIGINT CONSTRAINT ck CHECK (id > 0) ENABLED)",
    )
    assert_roundtrip(
        "CREATE TABLE t (id BIGINT CONSTRAINT fk REFERENCES other (oid))",
        "CREATE TABLE t (id BIGINT CONSTRAINT fk REFERENCES other (oid))",
    )
    assert_roundtrip(
        "CREATE TABLE t (id BIGINT CONSTRAINT uq UNIQUE ENABLED)",
        "CREATE TABLE t (id BIGINT CONSTRAINT uq UNIQUE ENABLED)",
    )


@pytest.mark.parametrize(
    ("clause", "kind_text", "start", "increment", "cache_size"),
    [
        ("AUTO_INCREMENT", "AUTO_INCREMENT", None, None, None),
        ("IDENTITY", "IDENTITY", None, None, None),
        ("IDENTITY(1)", "IDENTITY", 1, None, None),
        ("IDENTITY(1, 1)", "IDENTITY", 1, 1, None),
        ("IDENTITY(1, 1, 250000)", "IDENTITY", 1, 1, 250000),
        ("IDENTITY(-5, -2, 0)", "IDENTITY", -5, -2, 0),
    ],
)
def test_column_identity_forms(
    clause: str,
    kind_text: str,
    start: int | None,
    increment: int | None,
    cache_size: int | None,
) -> None:
    sql = f"CREATE TABLE t (id BIGINT {clause})"
    expression = assert_roundtrip(sql, sql)
    kind = _column_kinds(expression.this.expressions[0])[0]
    assert isinstance(kind, vexp.VerticaIdentityColumnConstraint)
    assert kind.args["kind"].name == kind_text
    for key, expected in (("start", start), ("increment", increment), ("cache_size", cache_size)):
        value = kind.args.get(key)
        if expected is None:
            assert value is None
        else:
            assert value.to_py() == expected


# ---------------------------------------------------------------------------
# Table-constraint positives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("clause", "expected_type"),
    [
        ("PRIMARY KEY (id)", exp.PrimaryKey),
        ("PRIMARY KEY (id) ENABLED", vexp.VerticaPrimaryKey),
        ("PRIMARY KEY (id) DISABLED", vexp.VerticaPrimaryKey),
    ],
)
def test_table_primary_key_forms(clause: str, expected_type: type[exp.Expr]) -> None:
    sql = f"CREATE TABLE t (id BIGINT, {clause})"
    expression = assert_roundtrip(sql, sql)
    pk = expression.this.expressions[1]
    assert type(pk) is expected_type
    assert [column.name for column in pk.expressions] == ["id"]


def test_table_multi_column_primary_key() -> None:
    sql = "CREATE TABLE t (a BIGINT, b BIGINT, PRIMARY KEY (a, b))"
    expression = assert_roundtrip(sql, sql)
    pk = expression.this.expressions[2]
    assert [column.name for column in pk.expressions] == ["a", "b"]


def test_table_unique_and_check() -> None:
    expression = assert_roundtrip("CREATE TABLE t (id BIGINT, UNIQUE (id))")
    unique = expression.this.expressions[1]
    assert type(unique) is exp.UniqueColumnConstraint
    assert isinstance(unique.this, exp.Schema)

    expression = assert_roundtrip("CREATE TABLE t (id BIGINT, CHECK (id > 0))")
    check = expression.this.expressions[1]
    assert type(check) is exp.CheckColumnConstraint

    sql = "CREATE TABLE t (id BIGINT, CHECK (id > 0) ENABLED)"
    expression = assert_roundtrip(sql, sql)
    check = expression.this.expressions[1]
    assert type(check) is vexp.VerticaCheckColumnConstraint
    assert check.args.get("enforced") is True


def test_table_foreign_key_with_and_without_columns() -> None:
    sql = "CREATE TABLE t (id BIGINT, FOREIGN KEY (id) REFERENCES other (oid))"
    expression = assert_roundtrip(sql, sql)
    fk = expression.this.expressions[1]
    assert isinstance(fk, exp.ForeignKey)
    assert [column.name for column in fk.expressions] == ["id"]
    assert [column.name for column in fk.args["reference"].this.expressions] == ["oid"]

    sql = "CREATE TABLE t (id BIGINT, FOREIGN KEY (id) REFERENCES other)"
    expression = assert_roundtrip(sql, sql)
    fk = expression.this.expressions[1]
    assert isinstance(fk.args["reference"].this, exp.Table)


def test_table_multi_column_foreign_key() -> None:
    sql = "CREATE TABLE t (a BIGINT, b BIGINT, FOREIGN KEY (a, b) REFERENCES other (x, y))"
    expression = assert_roundtrip(sql, sql)
    fk = expression.this.expressions[2]
    assert [column.name for column in fk.expressions] == ["a", "b"]
    assert [column.name for column in fk.args["reference"].this.expressions] == ["x", "y"]


def test_table_named_constraint_wraps_exactly_one_kind() -> None:
    sql = "CREATE TABLE t (id BIGINT, CONSTRAINT pk PRIMARY KEY (id) ENABLED)"
    expression = assert_roundtrip(sql, sql)
    constraint = expression.this.expressions[1]
    assert isinstance(constraint, exp.Constraint)
    assert constraint.this.name == "pk"
    assert len(constraint.expressions) == 1
    assert type(constraint.expressions[0]) is vexp.VerticaPrimaryKey


def test_mixed_column_and_table_constraints_preserve_order() -> None:
    sql = "CREATE TABLE t (id BIGINT NOT NULL, name VARCHAR, CONSTRAINT pk PRIMARY KEY (id))"
    expression = assert_roundtrip(sql, sql)
    assert [type(item) for item in expression.this.expressions] == [
        exp.ColumnDef,
        exp.ColumnDef,
        exp.Constraint,
    ]


# ---------------------------------------------------------------------------
# Structural and cardinality negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "CREATE TABLE t (PRIMARY KEY (id), id BIGINT)",
            "column definitions must precede table constraints",
        ),
        (
            "CREATE TABLE t (id BIGINT, PRIMARY KEY (id), name VARCHAR)",
            "column definitions must precede table constraints",
        ),
        (
            "CREATE TABLE t (a BIGINT PRIMARY KEY, b BIGINT PRIMARY KEY)",
            "allows at most one PRIMARY KEY",
        ),
        (
            "CREATE TABLE t (a BIGINT PRIMARY KEY, b BIGINT, PRIMARY KEY (b))",
            "allows at most one PRIMARY KEY",
        ),
        (
            "CREATE TABLE t (a BIGINT AUTO_INCREMENT, b BIGINT IDENTITY)",
            "allowed on only one table column",
        ),
        (
            "CREATE TABLE t (id BIGINT DEFAULT 0 DEFAULT 1)",
            "DEFAULT may be specified at most once",
        ),
        (
            "CREATE TABLE t (id BIGINT SET USING 0 SET USING 1)",
            "SET USING may be specified at most once",
        ),
        (
            "CREATE TABLE t (id BIGINT DEFAULT USING 1 DEFAULT 2)",
            "DEFAULT USING cannot be combined",
        ),
        (
            "CREATE TABLE t (id BIGINT DEFAULT USING 1 SET USING 2)",
            "DEFAULT USING cannot be combined",
        ),
        (
            "CREATE TABLE t (id BIGINT DEFAULT USING 1 DEFAULT USING 2)",
            "DEFAULT USING cannot be combined",
        ),
        (
            "CREATE TABLE t (a BIGINT, b VARCHAR DEFAULT (SELECT 'x')||(SELECT y FROM z))",
            "DEFAULT expressions support only one SELECT statement",
        ),
        (
            "CREATE TABLE t (a BIGINT, b VARCHAR SET USING (SELECT 'x')||(SELECT y FROM z))",
            "SET USING expressions support only one SELECT statement",
        ),
        (
            "CREATE TABLE t (a BIGINT, b VARCHAR DEFAULT USING (SELECT 'x')||(SELECT y FROM z))",
            "DEFAULT USING expressions support only one SELECT statement",
        ),
        (
            "CREATE TABLE t () AS SELECT 1",
            "column-name list cannot be empty",
        ),
        (
            "CREATE TABLE t (id BIGINT, name)",
            "column definitions require data types",
        ),
    ],
)
def test_definition_form_structural_negatives(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


# ---------------------------------------------------------------------------
# Temporary-table restrictions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scope", ["", "GLOBAL ", "LOCAL "])
@pytest.mark.parametrize("clause", ["AUTO_INCREMENT", "IDENTITY", "IDENTITY(1, 1, 100)"])
def test_temporary_tables_reject_identity(scope: str, clause: str) -> None:
    sql = f"CREATE {scope}TEMPORARY TABLE t (id BIGINT {clause})"
    with pytest.raises(ParseError, match="not supported in temporary tables"):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize("label", ["DEFAULT", "SET USING", "DEFAULT USING"])
def test_temporary_tables_reject_default_family_subqueries(label: str) -> None:
    sql = f"CREATE TEMPORARY TABLE t (id BIGINT {label} (SELECT 1))"
    with pytest.raises(ParseError, match="does not support subqueries in a temporary table"):
        parse_one(sql, read="vertica")


def test_temporary_table_allows_non_subquery_defaults() -> None:
    sql = "CREATE TEMPORARY TABLE t (id BIGINT DEFAULT 0 SET USING id + 1)"
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression.find(exp.TemporaryProperty), exp.TemporaryProperty)


def test_temporary_table_allows_ordinary_constraints() -> None:
    sql = "CREATE TEMPORARY TABLE t (id BIGINT PRIMARY KEY, CONSTRAINT ck CHECK (id > 0) ENABLED)"
    assert_roundtrip(sql, sql)


# ---------------------------------------------------------------------------
# CTAS / LIKE / flex boundary
# ---------------------------------------------------------------------------


def test_ctas_rejects_column_and_table_constraints() -> None:
    with pytest.raises(ParseError):
        parse_one("CREATE TABLE t (id BIGINT PRIMARY KEY) AS SELECT 1", read="vertica")
    with pytest.raises(ParseError):
        parse_one(
            "CREATE TABLE t (id BIGINT, CHECK (id > 0)) AS SELECT 1",
            read="vertica",
        )


def test_ctas_column_name_list_rejects_set_using_and_identity() -> None:
    with pytest.raises(ParseError):
        parse_one("CREATE TABLE t (id SET USING 1) AS SELECT 1", read="vertica")
    with pytest.raises(ParseError):
        parse_one("CREATE TABLE t (id IDENTITY) AS SELECT 1", read="vertica")


def test_like_form_still_rejects_constraint_keyword() -> None:
    with pytest.raises(ParseError, match="must be followed by PROJECTIONS"):
        parse_one("CREATE TABLE t LIKE source INCLUDING CONSTRAINTS", read="vertica")


def test_native_flex_table_definition_remains_unaffected_command_fallback() -> None:
    """P16 owns native flex tables; constraint work must not accidentally parse them."""

    expression = parse_one("CREATE FLEX TABLE t (id INT)", read="vertica")
    assert isinstance(expression, exp.Command)


# ---------------------------------------------------------------------------
# Rejected column/table-constraint grammar (Postgres/generic extensions Vertica
# does not document): reused options, ON DELETE/UPDATE, MATCH, DEFERRABLE,
# INCLUDE, ASC/DESC, GENERATED AS IDENTITY, NOT CASESPECIFIC/FOR REPLICATION,
# CHARACTER SET, COLLATE, COMMENT, EXCLUDE, PERIOD, ENFORCED, unnameable
# CONSTRAINT-name targets, unbounded identity argument counts/signs, and
# multi-kind named table constraints.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (id BIGINT FOREIGN KEY)",
        "CREATE TABLE t (id BIGINT PRIMARY KEY (id))",
        "CREATE TABLE t (id BIGINT UNIQUE (id))",
        "CREATE TABLE t (id BIGINT PRIMARY KEY DESC)",
        "CREATE TABLE t (id BIGINT PRIMARY KEY ASC)",
        "CREATE TABLE t (id BIGINT, FOREIGN KEY (id) REFERENCES o(x) ON DELETE CASCADE)",
        "CREATE TABLE t (id BIGINT, FOREIGN KEY (id) REFERENCES o(x) ON UPDATE CASCADE)",
        "CREATE TABLE t (id BIGINT REFERENCES o(x) ON DELETE CASCADE)",
        "CREATE TABLE t (id BIGINT REFERENCES o(a, b))",
        "CREATE TABLE t (id BIGINT REFERENCES o MATCH FULL)",
        "CREATE TABLE t (id BIGINT, PRIMARY KEY (id) DEFERRABLE)",
        "CREATE TABLE t (id BIGINT, PRIMARY KEY (id) INCLUDE (id))",
        "CREATE TABLE t (id BIGINT, UNIQUE (id) NULLS NOT DISTINCT)",
        "CREATE TABLE t (id BIGINT GENERATED ALWAYS AS IDENTITY)",
        "CREATE TABLE t (id BIGINT GENERATED BY DEFAULT AS IDENTITY)",
        "CREATE TABLE t (id BIGINT NOT CASESPECIFIC)",
        "CREATE TABLE t (id BIGINT NOT FOR REPLICATION)",
        "CREATE TABLE t (id BIGINT CHARACTER SET utf8)",
        "CREATE TABLE t (id BIGINT COLLATE en_US)",
        "CREATE TABLE t (id BIGINT COMMENT 'hi')",
        "CREATE TABLE t (id BIGINT, EXCLUDE (id WITH =))",
        "CREATE TABLE t (id BIGINT, PERIOD FOR SYSTEM_TIME (a, b))",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo NOT NULL)",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo DEFAULT 0)",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo SET USING 1)",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo AUTO_INCREMENT)",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo ACCESSRANK 1)",
        "CREATE TABLE t (id BIGINT, CONSTRAINT foo NOT NULL)",
        "CREATE TABLE t (id BIGINT, CONSTRAINT foo BANANA)",
        "CREATE TABLE t (id BIGINT CHECK (id > 0) ENFORCED)",
        "CREATE TABLE t (id BIGINT CHECK (id > 0) NOT ENFORCED)",
        "CREATE TABLE t (id BIGINT SET 1)",
        "CREATE TABLE t (id BIGINT SET)",
        "CREATE TABLE t (id BIGINT IDENTITY())",
        "CREATE TABLE t (id BIGINT IDENTITY(1, 1, 1, 1))",
        "CREATE TABLE t (id BIGINT IDENTITY(1.5))",
        "CREATE TABLE t (id BIGINT IDENTITY(1, 1, -5))",
        "CREATE TABLE t (id BIGINT IDENTITY(1, 1, 5,))",
        "CREATE TABLE t (id BIGINT, CONSTRAINT foo PRIMARY KEY (id) UNIQUE (id))",
        "CREATE TABLE t (id BIGINT, PRIMARY KEY (id) FOREIGN KEY (id) REFERENCES o)",
        "CREATE TABLE t (id BIGINT CHECK id > 0)",
        "CREATE TABLE t (id BIGINT, CHECK id > 0)",
    ],
)
def test_undocumented_constraint_grammar_fails_closed(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (id BIGINT FOREIGN KEY)",
        "CREATE TABLE t (id BIGINT PRIMARY KEY (id))",
        "CREATE TABLE t (id BIGINT, FOREIGN KEY (id) REFERENCES o(x) ON DELETE CASCADE)",
        "CREATE TABLE t (id BIGINT GENERATED ALWAYS AS IDENTITY)",
        "CREATE TABLE t (id BIGINT CONSTRAINT foo NOT NULL)",
        "CREATE TABLE t (id BIGINT CHECK (id > 0) ENFORCED)",
        "CREATE TABLE t (id BIGINT IDENTITY(1, 1, 1, 1))",
        "CREATE TABLE t (id BIGINT, CONSTRAINT foo PRIMARY KEY (id) UNIQUE (id))",
        "CREATE TABLE t (a BIGINT PRIMARY KEY, b BIGINT PRIMARY KEY)",
        "CREATE TABLE t (id BIGINT DEFAULT 0 DEFAULT 1)",
        "CREATE TEMPORARY TABLE t (id BIGINT AUTO_INCREMENT)",
        "CREATE TEMPORARY TABLE t (id BIGINT DEFAULT (SELECT 1))",
    ],
)
@pytest.mark.parametrize("error_level", list(ErrorLevel))
def test_constraint_negatives_fail_atomically_at_every_error_level(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


# ---------------------------------------------------------------------------
# Serialization, mutation, optimizer, and type-annotation contracts
# ---------------------------------------------------------------------------


def test_constraint_lifecycle_serialization_transform_and_types() -> None:
    sql = (
        "CREATE TABLE orders (id BIGINT PRIMARY KEY ENABLED, "
        "customer_id BIGINT NOT NULL REFERENCES customers, "
        "quantity BIGINT DEFAULT 1 CHECK (quantity > 0) ENABLED, "
        "note VARCHAR SET USING id, "
        "CONSTRAINT positive_id CHECK (id > 0) DISABLED)"
    )
    expression = parse_one(sql, read="vertica")
    assert expression.copy() == expression
    assert exp.Expr.load(expression.dump()) == expression

    transformed = expression.transform(
        lambda node: (
            exp.to_identifier("orders_v2")
            if isinstance(node, exp.Identifier) and node.name == "orders"
            else node
        )
    )
    assert "orders_v2" in _strict(transformed)

    optimized = optimize(expression.copy(), dialect="vertica")
    assert parse_one(_strict(optimized), read="vertica") == optimized

    annotated = annotate_types(expression.copy(), dialect="vertica")
    check = annotated.find(vexp.VerticaCheckColumnConstraint)
    assert check is not None
    assert check.this.type is not None

    for parent in expression.walk():
        for arg_key, value in parent.args.items():
            if isinstance(value, exp.Expr):
                assert value.parent is parent
                assert value.arg_key == arg_key
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    if isinstance(child, exp.Expr):
                        assert child.parent is parent
                        assert child.arg_key == arg_key
                        assert child.index == index


def test_constraint_dispatch_does_not_regress_neighboring_statements() -> None:
    statements = (
        "CREATE TABLE t (id BIGINT)",
        "CREATE TABLE t (id BIGINT ENCODING RLE ACCESSRANK 1)",
        "CREATE TABLE t LIKE source",
        "CREATE TABLE t AS SELECT 1 AS id",
    )
    for sql in statements:
        expression = parse_one(sql, read="vertica")
        assert not isinstance(expression, exp.Command)


# ---------------------------------------------------------------------------
# Foreign-generation atomicity and programmatic-AST validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (id BIGINT SET USING 1)",
        "CREATE TABLE t (id BIGINT DEFAULT USING 1)",
        "CREATE TABLE t (id BIGINT IDENTITY(1, 1, 250000))",
        "CREATE TABLE t (id BIGINT CHECK (id > 0) DISABLED)",
        "CREATE TABLE t (id BIGINT PRIMARY KEY ENABLED)",
        "CREATE TABLE t (id BIGINT UNIQUE DISABLED)",
        "CREATE TABLE t (id BIGINT, PRIMARY KEY (id) ENABLED)",
        "CREATE TABLE t (id BIGINT, UNIQUE (id) DISABLED)",
    ],
)
@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_new_constraint_nodes_foreign_generation_is_atomic(sql: str, dialect: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)
    nested = exp.Tuple(expressions=[expression.copy()])
    with pytest.raises((UnsupportedError, ValueError)):
        nested.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_check_and_identity_programmatic_ast_validation() -> None:
    malformed = (
        # A plain (non-Vertica) CheckColumnConstraint must never carry an
        # enforcement marker: real Vertica ASTs always use the dedicated
        # VerticaCheckColumnConstraint subclass for ENABLED/DISABLED.
        exp.CheckColumnConstraint(this=exp.column("x"), enforced=True),
        exp.CheckColumnConstraint(this=exp.column("x"), enforced=False),
        vexp.VerticaCheckColumnConstraint(this=exp.column("x"), enforced="yes"),
        vexp.VerticaCheckColumnConstraint(this=exp.column("x"), enforced=exp.true()),
        vexp.VerticaIdentityColumnConstraint(kind=exp.var("BANANA")),
        vexp.VerticaIdentityColumnConstraint(kind=exp.to_identifier("IDENTITY")),
        vexp.VerticaPrimaryKeyColumnConstraint(enforced="yes"),
        vexp.VerticaUniqueColumnConstraint(enforced="yes"),
        vexp.VerticaPrimaryKey(expressions=[exp.to_identifier("id")], enforced="yes"),
    )
    for expression in malformed:
        with pytest.raises(UnsupportedError):
            expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_check_enforcement_boolean_true_false_round_trip_programmatically() -> None:
    condition = exp.GT(this=exp.column("x"), expression=exp.Literal.number(0))
    enabled = vexp.VerticaCheckColumnConstraint(this=condition.copy(), enforced=True)
    disabled = vexp.VerticaCheckColumnConstraint(this=condition.copy(), enforced=False)
    omitted = exp.CheckColumnConstraint(this=condition.copy())

    assert _strict(enabled) == "CHECK (x > 0) ENABLED"
    assert _strict(disabled) == "CHECK (x > 0) DISABLED"
    assert _strict(omitted) == "CHECK (x > 0)"
