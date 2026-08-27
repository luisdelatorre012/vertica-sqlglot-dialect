"""Q36 PostgreSQL lowerings for direct, source-equivalent Vertica constructs."""

from __future__ import annotations

import subprocess
import sys

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import UnsupportedError
from sqlglot.optimizer import optimize
from sqlglot.optimizer.qualify import qualify

from sqlglot_vertica import expressions as vexp

ALL_LEVELS = tuple(ErrorLevel)


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_reported_local_temporary_ctas_lowers_to_postgres(level: ErrorLevel) -> None:
    source = "CREATE LOCAL TEMP TABLE t_local ON COMMIT PRESERVE ROWS AS SELECT 1 AS c"
    expression = parse_one(source, read="vertica")

    target = expression.sql(dialect="postgres", unsupported_level=level)
    assert target == "CREATE TEMPORARY TABLE t_local AS SELECT 1 AS c ON COMMIT PRESERVE ROWS"
    assert parse_one(target, read="postgres").sql(dialect="postgres") == target
    assert expression.sql(dialect="vertica") == (
        "CREATE LOCAL TEMPORARY TABLE t_local ON COMMIT PRESERVE ROWS AS SELECT 1 AS c"
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "CREATE LOCAL TEMPORARY TABLE t (id INT) ON COMMIT DELETE ROWS",
            "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DELETE ROWS",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t (c) AS SELECT 1 AS x",
            "CREATE TEMPORARY TABLE t (c) AS SELECT 1 AS x",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t AS /* prose */ SELECT 1 AS c",
            "CREATE TEMPORARY TABLE t AS /* prose */ SELECT 1 AS c",
        ),
    ],
)
def test_local_definition_and_ctas_shapes_lower_to_postgres(source: str, expected: str) -> None:
    expression = parse_one(source, read="vertica")
    assert expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE) == expected
    parse_one(expected, read="postgres")


def test_programmatic_local_temporary_like_lowers_without_mutation() -> None:
    expression = exp.Create(
        this=exp.table_("t"),
        kind="TABLE",
        properties=exp.Properties(
            expressions=[
                vexp.LocalProperty(),
                exp.TemporaryProperty(),
                exp.LikeProperty(this=exp.table_("source")),
            ]
        ),
    )
    before = expression.dump()
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
    assert target == "CREATE TEMPORARY TABLE t (LIKE source)"
    assert expression.dump() == before
    parse_one(target, read="postgres")


@pytest.mark.parametrize("level", ALL_LEVELS)
def test_vertica_global_scope_fails_atomically_in_postgres(level: ErrorLevel) -> None:
    expression = parse_one(
        "CREATE GLOBAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS SELECT 1 AS c",
        read="vertica",
    )
    assert isinstance(expression.find(vexp.VerticaGlobalProperty), vexp.VerticaGlobalProperty)
    with pytest.raises(ValueError, match="cannot preserve Vertica GLOBAL"):
        expression.sql(dialect="postgres", unsupported_level=level)


def test_postgres_parsed_global_compatibility_syntax_is_unchanged() -> None:
    expression = parse_one("CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS c", read="postgres")
    assert type(expression.find(exp.GlobalProperty)) is exp.GlobalProperty
    assert expression.sql(dialect="postgres") == "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS c"


@pytest.mark.parametrize(
    "properties",
    [
        [vexp.LocalProperty()],
        [vexp.LocalProperty(), vexp.LocalProperty(), exp.TemporaryProperty()],
        [vexp.LocalProperty(), exp.GlobalProperty(), exp.TemporaryProperty()],
    ],
)
def test_malformed_local_scope_containers_remain_atomic(
    properties: list[exp.Property],
) -> None:
    expression = exp.Create(
        this=exp.table_("t"),
        kind="TABLE",
        properties=exp.Properties(expressions=properties),
    )
    with pytest.raises(ValueError, match="Unsupported expression type LocalProperty"):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.IGNORE)


def test_detached_local_property_remains_atomic() -> None:
    with pytest.raises(UnsupportedError):
        vexp.LocalProperty().sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("direction", ("", " ASC", " DESC"))
@pytest.mark.parametrize("placement", ("FIRST", "LAST"))
def test_explicit_null_ordering_lowers_losslessly_to_postgres(
    direction: str, placement: str
) -> None:
    source = f"SELECT a FROM t ORDER BY a{direction} NULLS {placement}"
    expression = parse_one(source, read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
    assert target == source
    reparsed = parse_one(target, read="postgres")
    ordered = reparsed.find(exp.Ordered)
    assert ordered is not None
    assert ordered.args["desc"] is ({"": None, " ASC": False, " DESC": True}[direction])
    assert ordered.args["nulls_first"] is (placement == "FIRST")


@pytest.mark.parametrize(
    "source",
    [
        "SELECT ROW_NUMBER() OVER (ORDER BY a DESC NULLS FIRST) FROM t",
        "SELECT LISTAGG(a) WITHIN GROUP (ORDER BY a ASC NULLS LAST) FROM t",
        "WITH q AS (SELECT a FROM t ORDER BY a NULLS FIRST) SELECT a FROM q",
        "SELECT a FROM t UNION ALL SELECT a FROM u ORDER BY a DESC NULLS LAST",
    ],
)
def test_explicit_null_ordering_lowers_in_supported_owners(source: str) -> None:
    expression = parse_one(source, read="vertica")
    target = expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
    assert "NULLS FIRST" in target or "NULLS LAST" in target
    parse_one(target, read="postgres")


def test_explicit_null_ordering_survives_analysis_and_tree_operations() -> None:
    expression = parse_one("SELECT a FROM t ORDER BY a NULLS LAST", read="vertica")
    schema = {"t": {"a": "INT"}}
    for tree in (
        exp.Expr.load(expression.dump()),
        expression.copy(),
        expression.transform(lambda node: node),
        qualify(expression.copy(), dialect="vertica", schema=schema),
        optimize(expression.copy(), dialect="vertica", schema=schema),
    ):
        ordered = tree.find(vexp.VerticaOrdered)
        assert ordered is not None
        assert ordered.args["nulls"].name == "LAST"
        assert "NULLS LAST" in tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("level", ALL_LEVELS)
@pytest.mark.parametrize("nested", (False, True))
def test_nulls_auto_remains_atomic_in_postgres(level: ErrorLevel, nested: bool) -> None:
    ordered = vexp.VerticaOrdered(
        this=exp.column("a"),
        desc=None,
        nulls_first=False,
        nulls=exp.var("AUTO"),
        with_fill=None,
    )
    expression: exp.Expr = (
        exp.select("a").from_("t").order_by(ordered, copy=False) if nested else ordered
    )
    with pytest.raises(ValueError, match="only valid explicit NULLS FIRST or NULLS LAST"):
        expression.sql(dialect="postgres", unsupported_level=level)


@pytest.mark.parametrize("dialect", ("duckdb", "mysql", "sqlite"))
def test_other_foreign_dialects_remain_atomic(dialect: str) -> None:
    local = parse_one("CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS c", read="vertica")
    ordered = parse_one("SELECT a FROM t ORDER BY a NULLS LAST", read="vertica")
    for expression in (local, ordered):
        with pytest.raises((UnsupportedError, ValueError)):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("foreign_first", (False, True))
def test_postgres_patch_survives_import_order_and_dispatch_cache(foreign_first: bool) -> None:
    prefix = (
        "from sqlglot import exp; from sqlglot.generators.postgres import PostgresGenerator; "
        "PostgresGenerator().generate(exp.select('x')); "
        if foreign_first
        else ""
    )
    code = prefix + (
        "from sqlglot import ErrorLevel, parse_one; import sqlglot_vertica; "
        "tree = parse_one('SELECT a FROM t ORDER BY a NULLS LAST', read='vertica'); "
        "assert tree.sql(dialect='postgres', unsupported_level=ErrorLevel.RAISE).endswith("
        "'ORDER BY a NULLS LAST')"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
