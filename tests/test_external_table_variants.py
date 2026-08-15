"""Iceberg-backed and flexible external-table regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE sales STORED BY ICEBERG LOCATION 's3:/sales/*'",
        "CREATE EXTERNAL TABLE catalog.public.sales_snapshot "
        "STORED BY ICEBERG LOCATION '/warehouse/sales/v2.metadata.json'",
        "CREATE EXTERNAL TABLE users_hms "
        "STORED BY ICEBERG LOCATION 'thrift://hms.example:9083' "
        "HMS_DB 'analytics' HMS_TABLE 'users'",
        "CREATE EXTERNAL TABLE users_rest "
        "STORED BY ICEBERG LOCATION 'https://catalog.example/iceberg/v1/users' "
        'REST_AUTH \'{"bearerToken":"token"}\'',
    ],
)
def test_create_iceberg_external_table_catalog_matrix(sql: str) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateIcebergExternalTable)
    assert isinstance(expression.args["expression"], vexp.IcebergExternalTableSpec)
    assert not isinstance(expression.this, exp.Schema)


def test_iceberg_glue_and_nested_column_type_overrides() -> None:
    expression = assert_roundtrip(
        "CREATE EXTERNAL TABLE users_glue "
        "STORED BY ICEBERG LOCATION 's3://warehouse/iceberg' "
        "GLUE_DB 'analytics' GLUE_TABLE 'users' "
        "COLUMN TYPES ("
        "name VARCHAR(256), payload LONG VARBINARY(4096), "
        "address ROW(street VARCHAR(100), city LONG VARCHAR(500), "
        "coordinates ROW(label VARCHAR(20))), "
        "tags ARRAY[VARCHAR(50), 100], "
        "properties ARRAY[ROW(key VARCHAR(50), value INT), 20], "
        "encoded ARRAY[VARBINARY(16)](8192))",
        "CREATE EXTERNAL TABLE users_glue "
        "STORED BY ICEBERG LOCATION 's3://warehouse/iceberg' "
        "GLUE_DB 'analytics' GLUE_TABLE 'users' "
        "COLUMN TYPES ("
        "name VARCHAR(256), payload LONG VARBINARY(4096), "
        "address ROW(street VARCHAR(100), city LONG VARCHAR(500), "
        "coordinates ROW(label VARCHAR(20))), "
        "tags ARRAY[VARCHAR(50), 100], "
        "properties ARRAY[ROW(key VARCHAR(50), value BIGINT), 20], "
        "encoded ARRAY[VARBINARY(16)](8192))",
    )

    spec = expression.args["expression"]
    overrides = spec.args["column_types"]
    assert all(isinstance(override, vexp.IcebergColumnType) for override in overrides)
    assert [override.name for override in overrides] == [
        "name",
        "payload",
        "address",
        "tags",
        "properties",
        "encoded",
    ]
    assert overrides[2].args["kind"].this == exp.DType.STRUCT
    assert overrides[3].args["kind"].this == exp.DType.ARRAY
    assert overrides[3].args["kind"].args["values"][0].to_py() == 100
    assert overrides[5].args["kind"].args["kind"].name == "MAX_SIZE"


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE FLEX EXTERNAL TABLE mountains() "
        "AS COPY FROM '/data/mountains.json' PARSER FJSONPARSER()",
        "CREATE FLEXIBLE EXTERNAL TABLE IF NOT EXISTS ext.events(ts TIMESTAMP) "
        "INCLUDE SCHEMA PRIVILEGES AS COPY "
        "FROM '/data/events/*.json.gz' GZIP PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE ext_files() EXCLUDE PRIVILEGES AS COPY "
        "FROM '/data/a.json' ON node01 GZIP, '/data/b.json' ON ANY NODE ZSTD, "
        "'/data/c.json' ON (node02, node03) UNCOMPRESSED "
        "PARSER CustomFlexParser(mode='strict')",
        "CREATE FLEXIBLE EXTERNAL TABLE events(lang VARCHAR) "
        "AS COPY (__raw__, raw_lang FILLER VARCHAR, lang AS raw_lang::VARCHAR) "
        "FROM '/data/events.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE remote_events() AS COPY "
        "FROM WITH SOURCE HttpSource(url='https://example/data') "
        "FILTER GunzipFilter() FILTER AuditFilter(enabled=TRUE) "
        "PARSER CustomFlexParser()",
    ],
)
def test_create_flexible_external_table_matrix(sql: str) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateFlexibleExternalTable)
    assert isinstance(expression.this, exp.Schema)
    assert isinstance(expression.args["expression"], vexp.FlexibleCopyDefinition)


def test_flex_alias_is_canonicalized_to_flexible_and_empty_parentheses_are_preserved() -> None:
    expression = assert_roundtrip(
        "CREATE FLEX EXTERNAL TABLE mountains() "
        "AS COPY FROM '/data/mountains.json' PARSER FJSONPARSER()",
        "CREATE FLEXIBLE EXTERNAL TABLE mountains () "
        "AS COPY FROM '/data/mountains.json' PARSER FJSONPARSER()",
    )

    assert isinstance(expression.this, exp.Schema)
    assert expression.this.expressions == []


def test_flexible_copy_allowed_parameter_order_and_ast() -> None:
    expression = assert_roundtrip(
        "CREATE FLEX EXTERNAL TABLE flex_events() AS COPY "
        "FROM '/data/events.json' PARSER FJSONPARSER() "
        "ABORT ON ERROR DELIMITER '|' ENCLOSED BY '\"' ENFORCELENGTH "
        "ESCAPE AS '\\' EXCEPTIONS '/reject/errors' NULL AS '' "
        "RECORD TERMINATOR E'\\n' REJECTED DATA '/reject/data' "
        "REJECTMAX 10 SKIP 1 SKIP BYTES 2 TRAILING NULLCOLS TRIM ' '",
    )

    definition = expression.args["expression"]
    assert [parameter.name for parameter in definition.args["params"]] == [
        "PARSER",
        "ABORT ON ERROR",
        "DELIMITER",
        "ENCLOSED BY",
        "ENFORCELENGTH",
        "ESCAPE AS",
        "EXCEPTIONS",
        "NULL AS",
        "RECORD TERMINATOR",
        "REJECTED DATA",
        "REJECTMAX",
        "SKIP",
        "SKIP BYTES",
        "TRAILING NULLCOLS",
        "TRIM",
    ]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE IF NOT EXISTS t STORED BY ICEBERG LOCATION '/x'",
        "CREATE OR REPLACE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x'",
        "CREATE EXTERNAL TABLE t (id INT) STORED BY ICEBERG LOCATION '/x'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION /x",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' GLUE_DB 'db'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' GLUE_TABLE 't'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' HMS_DB 'db'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' HMS_TABLE 't'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' "
        "GLUE_DB 'db' GLUE_TABLE 't' HMS_DB 'db' HMS_TABLE 't'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' "
        "GLUE_DB 'db' GLUE_TABLE 't' REST_AUTH '{}'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' GLUE_TABLE 't' GLUE_DB 'db'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' "
        "GLUE_DB 'a' GLUE_DB 'b' GLUE_TABLE 't'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' "
        "REST_AUTH '{}' HMS_DB 'db' HMS_TABLE 't'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' "
        "COLUMN TYPES (name VARCHAR(20)) REST_AUTH '{}'",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' INCLUDE PRIVILEGES",
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' AS COPY FROM '/x'",
    ],
)
def test_iceberg_rejects_invalid_statement_and_catalog_modes(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "override",
    [
        "",
        "id INT",
        "flag BOOLEAN",
        "amount NUMERIC(10, 2)",
        "event_date DATE",
        "fixed BINARY(16)",
        "identifier UUID",
        "name VARCHAR",
        "payload VARBINARY",
        "name VARCHAR(0)",
        "name VARCHAR(-1)",
        "name VARCHAR(10, 20)",
        "items ARRAY[INT]",
        "items ARRAY[INT, 0]",
        "items ARRAY[INT, -1]",
        "items ARRAY[LONG VARCHAR, 10]",
        "address ROW(zip INT)",
        "address ROW(street VARCHAR)",
        "address ROW(street VARCHAR(20) DEFAULT 'x')",
        "address ROW(street VARCHAR(20) NOT NULL)",
        "address ROW(street VARCHAR(20), street VARCHAR(30))",
        "name VARCHAR(20) DEFAULT 'x'",
        "name VARCHAR(20) NOT NULL",
    ],
)
def test_iceberg_rejects_invalid_column_type_override(override: str) -> None:
    sql = f"CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x' COLUMN TYPES ({override})"
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE FLEX EXTERNAL TABLE f AS COPY FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE OR REPLACE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() COPY FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json'",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM LOCAL '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM STDIN PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM VERTICA source.t",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' ON EACH NODE PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARTITION COLUMNS region PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "COLUMN OPTION (__raw__ NULL AS '') FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' NATIVE",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' NATIVE VARCHAR",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' FIXEDWIDTH COLSIZES (10)",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.orc' ORC",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.parquet' PARQUET",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' FILTER Gunzip() PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARSER FJSONPARSER() ERROR TOLERANCE",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARSER FJSONPARSER() REJECTED DATA AS TABLE rejects",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARSER FJSONPARSER() STREAM NAME 'stream'",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER() NO COMMIT",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER() AUTO",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER() DIRECT",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER() TRICKLE",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARSER FJSONPARSER() COLLECTIONOPEN '['",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM SOURCE HttpSource() FILTER GunzipFilter()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY SOURCE HttpSource() PARSER FlexParser()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY () FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f(x INT) AS COPY (x) FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f(x INT) AS COPY (__raw__ AS x) "
        "FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f(x INT) AS COPY (__raw__ FILLER VARBINARY) "
        "FROM '/x.json' PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' ABORT ON ERROR PARSER FJSONPARSER()",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY "
        "FROM '/x.json' PARSER FJSONPARSER() PARSER OtherParser()",
    ],
)
def test_flexible_external_table_rejects_non_subset_copy_syntax(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE sales STORED BY ICEBERG LOCATION '/sales'",
        "CREATE FLEX EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER()",
    ],
)
def test_external_variant_roots_fail_atomically_in_foreign_dialects(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_iceberg_statement_restrictions() -> None:
    expression = parse_one(
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x'",
        read="vertica",
    )
    assert isinstance(expression, vexp.CreateIcebergExternalTable)

    expression.set("exists", True)
    with pytest.raises(UnsupportedError, match="IF NOT EXISTS"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    expression.set("exists", False)
    expression.set("this", exp.Schema(this=exp.to_table("t"), expressions=[]))
    with pytest.raises(UnsupportedError, match="without ordinary columns"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_iceberg_spec_restrictions() -> None:
    expression = parse_one(
        "CREATE EXTERNAL TABLE t STORED BY ICEBERG LOCATION '/x'",
        read="vertica",
    )
    spec = expression.args["expression"]
    assert isinstance(spec, vexp.IcebergExternalTableSpec)

    spec.set("glue_db", exp.Literal.string("db"))
    with pytest.raises(UnsupportedError, match="specified together"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    spec.set("glue_table", exp.Literal.string("t"))
    spec.set("rest_auth", exp.Literal.string("{}"))
    with pytest.raises(UnsupportedError, match="mutually exclusive"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    spec.set("glue_db", None)
    spec.set("glue_table", None)
    spec.set("rest_auth", None)
    spec.set(
        "column_types",
        [
            vexp.IcebergColumnType(
                this=exp.to_identifier("id"),
                kind=exp.DataType.build("INT"),
            )
        ],
    )
    with pytest.raises(UnsupportedError, match="only supports sized"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_programmatic_flexible_copy_restrictions() -> None:
    expression = parse_one(
        "CREATE FLEXIBLE EXTERNAL TABLE f() AS COPY FROM '/x.json' PARSER FJSONPARSER()",
        read="vertica",
    )
    definition = expression.args["expression"]
    assert isinstance(definition, vexp.FlexibleCopyDefinition)

    definition.set("params", [])
    with pytest.raises(UnsupportedError, match="require one compatible PARSER"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    definition.set(
        "params",
        [
            exp.CopyParameter(
                this=exp.var("PARSER"),
                expression=vexp.CopyLoadFunction(this=exp.to_identifier("FJSONPARSER")),
            )
        ],
    )
    definition.set("expressions", [vexp.CopyColumn(this=exp.to_identifier("value"))])
    with pytest.raises(UnsupportedError, match="plain __raw__"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    definition.set("expressions", [])
    definition.set("format", vexp.CopyFormat(this=exp.var("NATIVE")))
    with pytest.raises(UnsupportedError, match="not a built-in COPY format"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    definition.set("format", None)
    definition.set("source", vexp.CopyFromVertica(this=exp.to_table("source.t")))
    with pytest.raises(UnsupportedError, match="FROM VERTICA"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
