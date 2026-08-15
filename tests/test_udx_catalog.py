"""Library and bodyless user-defined-extension catalog DDL."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    ("sql", "expected", "kind", "language", "fenced"),
    [
        (
            "CREATE FUNCTION add2 AS NAME 'Add2Factory' LIBRARY ScalarLib",
            None,
            "FUNCTION",
            None,
            None,
        ),
        (
            "CREATE FUNCTION IF NOT EXISTS analytics.add2 "
            "AS LANGUAGE 'python' NAME 'Add2Factory' LIBRARY analytics.py_lib FENCED",
            "CREATE FUNCTION IF NOT EXISTS analytics.add2 "
            "AS LANGUAGE 'Python' NAME 'Add2Factory' LIBRARY analytics.py_lib FENCED",
            "FUNCTION",
            "Python",
            True,
        ),
        (
            "CREATE OR REPLACE AGGREGATE FUNCTION ag_avg "
            "AS LANGUAGE 'C++' NAME 'AverageFactory' LIBRARY AggregateLib NOT FENCED",
            None,
            "AGGREGATE FUNCTION",
            "C++",
            False,
        ),
        (
            "CREATE AGGREGATE FUNCTION ag_count AS NAME 'CountFactory' LIBRARY AggregateLib",
            None,
            "AGGREGATE FUNCTION",
            None,
            None,
        ),
        (
            "CREATE ANALYTIC FUNCTION db.analytics.ranker "
            "AS LANGUAGE 'Java' NAME 'RankFactory' LIBRARY analytics.AnalyticLib FENCED",
            None,
            "ANALYTIC FUNCTION",
            "Java",
            True,
        ),
        (
            "CREATE TRANSFORM FUNCTION pagerank "
            "AS LANGUAGE 'r' NAME 'PageRankFactory' LIBRARY TransformLib FENCED",
            "CREATE TRANSFORM FUNCTION pagerank "
            "AS LANGUAGE 'R' NAME 'PageRankFactory' LIBRARY TransformLib FENCED",
            "TRANSFORM FUNCTION",
            "R",
            True,
        ),
        (
            "CREATE FILTER decode AS LANGUAGE 'Python' NAME 'DecodeFactory' LIBRARY LoadLib FENCED",
            None,
            "FILTER",
            "Python",
            True,
        ),
        (
            "CREATE PARSER csvx AS LANGUAGE 'C++' NAME 'CsvFactory' LIBRARY LoadLib NOT FENCED",
            None,
            "PARSER",
            "C++",
            False,
        ),
        (
            "CREATE SOURCE src AS LANGUAGE 'Java' NAME 'SourceFactory' LIBRARY LoadLib FENCED",
            None,
            "SOURCE",
            "Java",
            True,
        ),
        (
            "CREATE SOURCE default_src AS LANGUAGE 'Java' NAME 'SourceFactory' LIBRARY LoadLib",
            None,
            "SOURCE",
            "Java",
            None,
        ),
    ],
)
def test_create_user_defined_extension_matrix(
    sql: str,
    expected: str | None,
    kind: str,
    language: str | None,
    fenced: bool | None,
) -> None:
    expression = assert_roundtrip(sql, expected)

    assert isinstance(expression, vexp.CreateUserDefinedExtension)
    assert isinstance(expression, exp.Create)
    assert expression.kind == kind
    assert isinstance(expression.this, exp.Table)
    spec = expression.args["expression"]
    assert isinstance(spec, vexp.UDxFactorySpec)
    assert spec.parent is expression
    assert isinstance(spec.args["factory"], exp.Literal)
    assert isinstance(spec.args["library"], exp.Table)
    assert spec.args["factory"].parent is spec
    assert spec.args["library"].parent is spec
    parsed_language = spec.args.get("language")
    assert (parsed_language.this if isinstance(parsed_language, exp.Literal) else None) == language
    assert spec.args.get("fenced") is fenced


@pytest.mark.parametrize(
    ("sql", "expected"),
    [
        ("CREATE LIBRARY mylib AS '/opt/vertica/lib/mylib.so'", None),
        (
            "CREATE OR REPLACE LIBRARY ext.mylib AS 's3://bucket/mylib.jar' "
            "DEPENDS '[\"s3://bucket/dep.jar\"]' LANGUAGE 'java'",
            "CREATE OR REPLACE LIBRARY ext.mylib AS 's3://bucket/mylib.jar' "
            "DEPENDS '[\"s3://bucket/dep.jar\"]' LANGUAGE 'Java'",
        ),
        ("DROP LIBRARY mylib", None),
        ("DROP LIBRARY IF EXISTS ext.mylib CASCADE", None),
    ],
)
def test_library_create_and_drop_matrix(sql: str, expected: str | None) -> None:
    expression = assert_roundtrip(sql, expected)
    assert isinstance(expression, (vexp.CreateLibrary, vexp.DropLibrary))

    if isinstance(expression, vexp.CreateLibrary):
        assert isinstance(expression.args["path"], exp.Literal)
        language = expression.args.get("language")
        if language is not None:
            assert isinstance(language, exp.Literal)
            assert language.this == "Java"
    else:
        assert expression.args.get("cascade") is bool(expression.args.get("cascade"))


@pytest.mark.parametrize(
    ("sql", "kind", "argument_types"),
    [
        ("DROP FUNCTION IF EXISTS add2()", "FUNCTION", []),
        ("DROP FUNCTION add2(INT, VARCHAR(20))", "FUNCTION", [exp.DataType, exp.DataType]),
        (
            "DROP AGGREGATE FUNCTION IF EXISTS analytics.ag_avg(value NUMERIC)",
            "AGGREGATE FUNCTION",
            [exp.ColumnDef],
        ),
        (
            "DROP ANALYTIC FUNCTION ranker(x INT, VARCHAR)",
            "ANALYTIC FUNCTION",
            [exp.ColumnDef, exp.DataType],
        ),
        ("DROP TRANSFORM FUNCTION pagerank()", "TRANSFORM FUNCTION", []),
        ("DROP FILTER decode()", "FILTER", []),
        ("DROP PARSER csvx()", "PARSER", []),
        ("DROP SOURCE src()", "SOURCE", []),
    ],
)
def test_drop_user_defined_extension_signatures(
    sql: str, kind: str, argument_types: list[type[exp.Expr]]
) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.DropUserDefinedExtension)
    assert isinstance(expression, exp.Drop)
    assert expression.kind == kind
    signature = expression.this
    assert isinstance(signature, vexp.RoutineSignature)
    assert isinstance(signature.this, exp.Table)
    assert [type(argument) for argument in signature.expressions] == argument_types
    assert expression.sql(dialect="vertica").endswith(f"{signature.sql(dialect='vertica')}")


def test_factory_dispatch_does_not_capture_sql_function_syntax() -> None:
    expression = parse_one(
        "CREATE FUNCTION zero(x INT) RETURN INT AS BEGIN RETURN x + 1",
        read="vertica",
    )
    assert not isinstance(expression, vexp.CreateUserDefinedExtension)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE OR REPLACE FUNCTION IF NOT EXISTS f AS NAME 'F' LIBRARY l",
        "CREATE AGGREGATE f AS NAME 'F' LIBRARY l",
        "CREATE ANALYTIC f AS NAME 'F' LIBRARY l",
        "CREATE TRANSFORM f AS NAME 'F' LIBRARY l",
        "CREATE FUNCTION f() AS NAME 'F' LIBRARY l",
        "CREATE FUNCTION AS NAME 'F' LIBRARY l",
        "CREATE FUNCTION db.schema.extra.f AS NAME 'F' LIBRARY l",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY db.schema.extra.l",
        "CREATE FUNCTION f NAME 'F' LIBRARY l",
        "CREATE FUNCTION f AS LIBRARY l NAME 'F'",
        "CREATE FUNCTION f AS NAME F LIBRARY l",
        "CREATE FUNCTION f AS NAME 'F'",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY",
        "CREATE FUNCTION f AS LANGUAGE Python NAME 'F' LIBRARY l",
        "CREATE FUNCTION f AS LANGUAGE 'Rust' NAME 'F' LIBRARY l",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l LANGUAGE 'C++'",
        "CREATE FUNCTION f AS LANGUAGE 'C++' LANGUAGE 'C++' NAME 'F' LIBRARY l",
        "CREATE FUNCTION f AS NAME 'F' NAME 'G' LIBRARY l",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l LIBRARY other",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l FENCED FENCED",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l FENCED NOT FENCED",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l NOT",
        "CREATE FUNCTION f AS LANGUAGE 'Python' NAME 'F' LIBRARY l NOT FENCED",
        "CREATE ANALYTIC FUNCTION f AS LANGUAGE 'Java' NAME 'F' LIBRARY l NOT FENCED",
        "CREATE TRANSFORM FUNCTION f AS LANGUAGE 'R' NAME 'F' LIBRARY l NOT FENCED",
        "CREATE FILTER f AS LANGUAGE 'R' NAME 'F' LIBRARY l FENCED",
        "CREATE PARSER f AS LANGUAGE 'R' NAME 'F' LIBRARY l FENCED",
        "CREATE SOURCE f AS LANGUAGE 'Python' NAME 'F' LIBRARY l FENCED",
        "CREATE AGGREGATE FUNCTION f AS LANGUAGE 'Java' NAME 'F' LIBRARY l",
        "CREATE AGGREGATE FUNCTION f AS NAME 'F' LIBRARY l FENCED",
        "CREATE LIBRARY IF NOT EXISTS l AS '/x'",
        "CREATE LIBRARY AS '/x'",
        "CREATE LIBRARY db.schema.extra.l AS '/x'",
        "CREATE LIBRARY l '/x'",
        "CREATE LIBRARY l AS /x",
        "CREATE LIBRARY l AS '/x' DEPENDS dep",
        "CREATE LIBRARY l AS '/x' LANGUAGE C++",
        "CREATE LIBRARY l AS '/x' LANGUAGE 'Rust'",
        "CREATE LIBRARY l AS '/x' LANGUAGE 'Java' DEPENDS 'dep'",
        "CREATE LIBRARY l AS '/x' DEPENDS 'a' DEPENDS 'b'",
        "DROP FUNCTION f",
        "DROP FUNCTION ()",
        "DROP FUNCTION f(INT,)",
        "DROP FUNCTION db.schema.extra.f()",
        "DROP FUNCTION f() CASCADE",
        "DROP FUNCTION f() RESTRICT",
        "DROP FUNCTION f(), g()",
        "DROP AGGREGATE f()",
        "DROP ANALYTIC f()",
        "DROP TRANSFORM f()",
        "DROP FILTER f(INT)",
        "DROP FILTER IF EXISTS f()",
        "DROP FILTER f",
        "DROP PARSER f(x INT)",
        "DROP PARSER IF EXISTS f()",
        "DROP SOURCE IF EXISTS f()",
        "DROP FILTER f() CASCADE",
        "DROP LIBRARY l RESTRICT",
        "DROP LIBRARY",
        "DROP LIBRARY l CASCADE CASCADE",
        "DROP LIBRARY db.schema.extra.l",
        "DROP LIBRARY l, other",
    ],
)
def test_udx_and_library_parser_rejects_invalid_grammar(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE LIBRARY l AS '/x'",
        "DROP LIBRARY IF EXISTS l CASCADE",
        "CREATE FUNCTION f AS NAME 'F' LIBRARY l",
        "CREATE AGGREGATE FUNCTION a AS NAME 'A' LIBRARY l NOT FENCED",
        "CREATE FILTER f AS NAME 'F' LIBRARY l",
        "DROP FUNCTION f()",
        "DROP ANALYTIC FUNCTION a(x INT)",
        "DROP SOURCE s()",
    ],
)
def test_udx_and_library_roots_fail_atomically_in_foreign_dialects(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def _factory_spec(
    *,
    language: exp.Expr | None = None,
    factory: exp.Expr | None = None,
    library: exp.Expr | None = None,
    fenced: object = None,
) -> vexp.UDxFactorySpec:
    return vexp.UDxFactorySpec(
        language=language,
        factory=factory if factory is not None else exp.Literal.string("Factory"),
        library=library if library is not None else exp.to_table("lib"),
        fenced=fenced,
    )


def _create_udx(
    kind: str = "FUNCTION", spec: exp.Expr | None = None
) -> vexp.CreateUserDefinedExtension:
    return vexp.CreateUserDefinedExtension(
        this=exp.to_table("f"),
        kind=kind,
        expression=spec if spec is not None else _factory_spec(),
    )


def _signature(*arguments: exp.Expr) -> vexp.RoutineSignature:
    return vexp.RoutineSignature(this=exp.to_table("f"), expressions=list(arguments))


@pytest.mark.parametrize(
    "expression",
    [
        _create_udx(kind="MODEL"),
        vexp.CreateUserDefinedExtension(
            this=exp.to_table("f"),
            kind="FUNCTION",
            expression=_factory_spec(),
            replace=True,
            exists=True,
        ),
        vexp.CreateUserDefinedExtension(
            this=exp.to_identifier("f"), kind="FUNCTION", expression=_factory_spec()
        ),
        _create_udx(spec=exp.var("opaque")),
        _create_udx(spec=_factory_spec(factory=exp.Literal.number(1))),
        _create_udx(spec=_factory_spec(library=exp.to_identifier("lib"))),
        _create_udx(spec=_factory_spec(language=exp.Literal.number(1))),
        _create_udx(spec=_factory_spec(language=exp.Literal.string("Rust"))),
        _create_udx(spec=_factory_spec(language=exp.Literal.string("Python"), fenced=False)),
        _create_udx(kind="AGGREGATE FUNCTION", spec=_factory_spec(fenced=True)),
        vexp.CreateUserDefinedExtension(
            this=exp.to_table("f"),
            kind="FUNCTION",
            expression=_factory_spec(),
            properties=exp.Properties(expressions=[]),
        ),
        vexp.DropUserDefinedExtension(this=exp.to_table("f"), kind="FUNCTION"),
        vexp.DropUserDefinedExtension(this=_signature(), kind="MODEL"),
        vexp.DropUserDefinedExtension(
            this=vexp.RoutineSignature(this=exp.to_identifier("f"), expressions=[]),
            kind="FUNCTION",
        ),
        vexp.DropUserDefinedExtension(this=_signature(exp.Literal.string("INT")), kind="FUNCTION"),
        vexp.DropUserDefinedExtension(
            this=_signature(exp.ColumnDef(this=exp.to_identifier("x"))), kind="FUNCTION"
        ),
        vexp.DropUserDefinedExtension(
            this=_signature(
                exp.ColumnDef(
                    this=exp.to_identifier("x"),
                    kind=exp.DataType.build("INT"),
                    constraints=[exp.ColumnConstraint(kind=exp.NotNullColumnConstraint())],
                )
            ),
            kind="FUNCTION",
        ),
        vexp.DropUserDefinedExtension(this=_signature(exp.DataType.build("INT")), kind="SOURCE"),
        vexp.DropUserDefinedExtension(this=_signature(), kind="SOURCE", exists=True),
        vexp.DropUserDefinedExtension(this=_signature(), kind="FUNCTION", cascade=True),
        vexp.DropUserDefinedExtension(
            this=_signature(),
            expressions=[_signature()],
            kind="FUNCTION",
        ),
        vexp.CreateLibrary(this=exp.to_table("l"), kind="MODEL", path=exp.Literal.string("/x")),
        vexp.CreateLibrary(
            this=exp.to_table("l"), kind="LIBRARY", exists=True, path=exp.Literal.string("/x")
        ),
        vexp.CreateLibrary(this=exp.to_table("l"), kind="LIBRARY", path=exp.Literal.number(1)),
        vexp.CreateLibrary(
            this=exp.to_table("l"),
            kind="LIBRARY",
            path=exp.Literal.string("/x"),
            language=exp.Literal.string("Rust"),
        ),
        vexp.CreateLibrary(
            this=exp.to_table("l"),
            kind="LIBRARY",
            path=exp.Literal.string("/x"),
            depends=exp.Literal.number(1),
        ),
        vexp.CreateLibrary(
            this=exp.to_table("l"),
            kind="LIBRARY",
            path=exp.Literal.string("/x"),
            properties=exp.Properties(expressions=[]),
        ),
        vexp.CreateLibrary(
            this=exp.Table(this=exp.Literal.string("l")),
            kind="LIBRARY",
            path=exp.Literal.string("/x"),
        ),
        vexp.CreateLibrary(
            this=exp.to_table("l").as_("alias"),
            kind="LIBRARY",
            path=exp.Literal.string("/x"),
        ),
        vexp.DropLibrary(this=exp.to_table("l"), kind="MODEL"),
        vexp.DropLibrary(this=exp.to_identifier("l"), kind="LIBRARY"),
        vexp.DropLibrary(this=exp.to_table("l"), kind="LIBRARY", restrict=True),
        vexp.DropLibrary(
            this=exp.to_table("l"),
            expressions=[exp.to_table("other")],
            kind="LIBRARY",
        ),
    ],
)
def test_udx_and_library_generators_reject_malformed_programmatic_asts(
    expression: exp.Expr,
) -> None:
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_udx_child_generators_validate_standalone_programmatic_shapes() -> None:
    standalone_spec = _factory_spec(language=exp.Literal.string("python"), fenced=True)
    assert standalone_spec.sql(dialect="vertica") == (
        "LANGUAGE 'Python' NAME 'Factory' LIBRARY lib FENCED"
    )

    malformed_spec = _factory_spec(fenced=exp.Boolean(this=True))
    malformed_spec.set("extra", exp.var("x"))
    with pytest.raises(UnsupportedError):
        malformed_spec.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    malformed_signature = _signature()
    malformed_signature.set("extra", exp.var("x"))
    drop = vexp.DropUserDefinedExtension(this=malformed_signature, kind="FUNCTION")
    with pytest.raises(UnsupportedError):
        drop.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
