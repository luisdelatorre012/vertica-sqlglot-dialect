"""Regular external-table and external-procedure semantic regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE IF NOT EXISTS analytics.events "
        "(event_id INT, payload VARCHAR) INCLUDE SCHEMA PRIVILEGES "
        "AS COPY FROM 's3://warehouse/events/*.csv' ON ANY NODE GZIP "
        "DELIMITER '|' NULL AS '' TRAILING NULLCOLS",
        "CREATE EXTERNAL TABLE ext_transform (id INT, payload VARCHAR) "
        "AS COPY (raw_id FILLER VARCHAR, id AS raw_id::INT, payload) "
        "COLUMN OPTION (payload NULL AS 'NULL') FROM '/data/events.csv'",
        "CREATE EXTERNAL TABLE ext_orc (event_id INT, event_date DATE) "
        "EXCLUDE PRIVILEGES AS COPY FROM 's3://warehouse/events/*.orc' "
        "ORC(hive_partition_cols='event_date', allow_no_match=TRUE, "
        "do_soft_schema_match_by_name=FALSE, "
        "reject_on_materialized_type_error=TRUE)",
        "CREATE EXTERNAL TABLE ext_parquet (event_id INT, payload LONG VARCHAR) "
        "AS COPY FROM 's3://warehouse/events/*.parquet' "
        "PARQUET(hive_partition_cols='event_date', allow_no_match=TRUE, "
        "allow_long_varbinary_match_complex_type=FALSE, "
        "do_soft_schema_match_by_name=TRUE, "
        "reject_on_materialized_type_error=FALSE)",
        "CREATE EXTERNAL TABLE ext_json (payload LONG VARCHAR) "
        "AS COPY FROM '/data/*.json' WITH FILTER EventFilter(strict=TRUE) "
        "WITH PARSER FJSONParser(flatten_arrays=TRUE)",
        "CREATE EXTERNAL TABLE ext_udl AS COPY "
        "WITH SOURCE S3Source(bucket='warehouse') "
        "WITH FILTER EventFilter(strict=TRUE) "
        "WITH PARSER EventParser(version=2)",
        "CREATE EXTERNAL TABLE ext_remote (id INT, payload VARCHAR) "
        "AS COPY FROM VERTICA remote_ns.public.events(id, payload)",
    ],
)
def test_create_regular_external_table_matrix(sql: str) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, vexp.CreateExternalTable)
    assert isinstance(expression, exp.Create)
    assert expression.kind == "TABLE"
    assert isinstance(expression.args["expression"], vexp.ExternalCopyDefinition)
    assert not isinstance(expression.args["expression"], exp.Copy)


def test_external_table_udl_without_columns_is_canonicalized_with_from() -> None:
    expression = assert_roundtrip(
        "CREATE EXTERNAL TABLE ext_udl AS COPY SOURCE EventSource(path='/data')",
        "CREATE EXTERNAL TABLE ext_udl AS COPY FROM SOURCE EventSource(path = '/data')",
    )

    definition = expression.args["expression"]
    assert isinstance(definition.args["source"], vexp.CopyUDL)


def test_external_table_orc_and_parquet_parameters_are_structured() -> None:
    expression = assert_roundtrip(
        "CREATE EXTERNAL TABLE ext_data (id INT) AS COPY FROM '/data/*.parquet' "
        "PARQUET(hive_partition_cols='region', allow_no_match=TRUE)"
    )

    source_format = expression.args["expression"].args["format"]
    assert isinstance(source_format, vexp.CopyFormat)
    assert source_format.name == "PARQUET"
    assert all(isinstance(parameter, exp.EQ) for parameter in source_format.expressions)
    assert [parameter.this.name for parameter in source_format.expressions] == [
        "hive_partition_cols",
        "allow_no_match",
    ]


def test_file_filter_and_parser_are_shared_with_executable_copy() -> None:
    expression = assert_roundtrip(
        "COPY events FROM '/data/*.json' WITH FILTER EventFilter(strict=TRUE) "
        "WITH PARSER EventParser(version=2)"
    )

    assert isinstance(expression, vexp.VerticaCopy)
    assert [parameter.name for parameter in expression.args["params"]] == [
        "FILTER",
        "PARSER",
    ]


@pytest.mark.parametrize(
    "type_name",
    [
        "BIGINT",
        "BOOLEAN",
        "DECIMAL",
        "DOUBLE PRECISION",
        "FLOAT",
        "FLOAT8",
        "INT",
        "INT8",
        "INTEGER",
        "MONEY",
        "NUMBER",
        "NUMERIC",
        "REAL",
        "SMALLINT",
        "TINYINT",
        "VARCHAR",
    ],
)
def test_create_external_procedure_type_whitelist(type_name: str) -> None:
    expression = assert_roundtrip(
        f"CREATE PROCEDURE IF NOT EXISTS external_{type_name.replace(' ', '_')}"
        f"(argument_value {type_name}, {type_name}) "
        "AS '/opt/vertica/bin/external_proc' LANGUAGE 'EXTERNAL' USER 'dbadmin'"
    )

    assert isinstance(expression, vexp.CreateExternalProcedure)
    assert isinstance(expression.this, vexp.ExternalProcedureSignature)
    assert len(expression.this.expressions) == 2
    assert isinstance(expression.this.expressions[0], vexp.ExternalProcedureParameter)
    assert expression.this.expressions[0].name == "argument_value"
    assert expression.this.expressions[1].this is None


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE PROCEDURE refresh() AS '/opt/refresh' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "DROP PROCEDURE refresh()",
        "DROP PROCEDURE IF EXISTS analytics.refresh(batch_id INT, VARCHAR)",
    ],
)
def test_external_procedure_create_and_typed_drop(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, (vexp.CreateExternalProcedure, vexp.DropExternalProcedure))


@pytest.mark.parametrize(
    "sql",
    [
        'CREATE PROCEDURE p("user" INT) AS $$BEGIN NULL; END;$$',
        'CREATE PROCEDURE "user"() AS $$BEGIN NULL; END;$$',
    ],
)
def test_external_procedure_lookahead_ignores_quoted_user_identifiers(sql: str) -> None:
    expression = assert_roundtrip(sql)

    assert isinstance(expression, exp.Create)
    assert not isinstance(expression, vexp.CreateExternalProcedure)


def test_external_procedure_lookahead_still_dispatches_after_quoted_user_parameter() -> None:
    expression = assert_roundtrip(
        'CREATE PROCEDURE external_user("user" INT) '
        "AS '/opt/external_user' LANGUAGE 'EXTERNAL' USER 'dbadmin'"
    )

    assert isinstance(expression, vexp.CreateExternalProcedure)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE ext (id INT) COPY FROM '/data'",
        "CREATE OR REPLACE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data'",
        "CREATE EXTERNAL VIEW ext AS SELECT 1",
        "CREATE EXTERNAL TABLE ext (id INT) AS FROM '/data'",
        "CREATE EXTERNAL TABLE ext AS COPY FROM '/data'",
        "CREATE EXTERNAL TABLE ext () AS COPY FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id) AS COPY FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM LOCAL '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM STDIN",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' STREAM NAME 'stream'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' AUTO",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' DIRECT",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' TRICKLE",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' REJECTED DATA AS TABLE rejects",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' NO COMMIT",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' COLLECTIONOPEN '['",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' DELIMITER ',' DELIMITER '|'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data' SKIP 1 DELIMITER ','",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY (id AS raw_id::INT) FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY "
        "(raw FILLER VARCHAR, id AS raw::INT FORMAT 'X') FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY (raw FILLER VARCHAR FILLER INT) FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY "
        "(raw FILLER VARCHAR, id AS raw::INT FILLER VARCHAR) FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY (raw FILLER ARRAY[INT]) FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY "
        "COLUMN OPTION (id NULL AS '', id TRIM ' ') FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY "
        "COLUMN OPTION (id NULL AS '' DELIMITER ',') FROM '/data'",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.orc' GZIP ORC",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.orc' ORC(foo=TRUE)",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.orc' "
        "ORC(allow_no_match=TRUE, allow_no_match=FALSE)",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.orc' ORC(allow_no_match)",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.orc' ORC SKIP 1",
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data.parquet' PARQUET PARSER P()",
    ],
)
def test_external_table_rejects_invalid_or_unsafe_copy_definition(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


def test_shared_copy_validation_rejects_conflicting_rejection_destinations() -> None:
    with pytest.raises(ParseError):
        parse_one(
            "COPY t FROM '/data' EXCEPTIONS '/errors' REJECTED DATA AS TABLE rejects",
            read="vertica",
        )


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE PROCEDURE p AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p() LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p() AS /p LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p() AS '/p' USER 'dbadmin' LANGUAGE 'EXTERNAL'",
        "CREATE PROCEDURE p() AS '/p' LANGUAGE EXTERNAL USER 'dbadmin'",
        "CREATE PROCEDURE p() AS '/p' LANGUAGE 'C' USER 'dbadmin'",
        "CREATE PROCEDURE p() AS '/p' LANGUAGE 'EXTERNAL' USER dbadmin",
        "CREATE PROCEDURE p() AS '/p' LANGUAGE 'EXTERNAL'",
        "CREATE PROCEDURE p(DATE) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p(CHAR) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p(VARCHAR(10)) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p(a INT, a VARCHAR) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p(a INT b VARCHAR) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "CREATE PROCEDURE p() AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin' EXTRA",
        "DROP PROCEDURE p",
        "DROP PROCEDURE p(DATE)",
        "DROP PROCEDURE p(INT) CASCADE",
    ],
)
def test_external_procedure_rejects_invalid_signature_or_clause_order(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data'",
        "CREATE PROCEDURE p(INT) AS '/p' LANGUAGE 'EXTERNAL' USER 'dbadmin'",
        "DROP PROCEDURE p(INT)",
    ],
)
def test_external_roots_fail_atomically_in_foreign_dialects(sql: str) -> None:
    expression = parse_one(sql, read="vertica")

    with pytest.raises((UnsupportedError, ValueError)):
        expression.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


def _external_table_ast() -> vexp.CreateExternalTable:
    expression = parse_one(
        "CREATE EXTERNAL TABLE ext (id INT) AS COPY FROM '/data'",
        read="vertica",
    )
    assert isinstance(expression, vexp.CreateExternalTable)
    return expression


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (vexp.CopyStdin(), "LOCAL or STDIN"),
        (
            vexp.CopyFiles(
                expressions=[vexp.CopyFile(this=exp.Literal.string("/data"))],
                local=True,
            ),
            "LOCAL or STDIN",
        ),
    ],
)
def test_external_copy_programmatic_source_exclusions(source: exp.Expr, message: str) -> None:
    expression = _external_table_ast()
    expression.args["expression"].set("source", source)

    with pytest.raises(UnsupportedError, match=message):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_external_copy_programmatic_parameter_and_no_commit_exclusions() -> None:
    expression = _external_table_ast()
    definition = expression.args["expression"]
    definition.set(
        "params",
        [
            exp.CopyParameter(
                this=exp.var("STREAM NAME"),
                expression=exp.Literal.string("stream"),
            )
        ],
    )

    with pytest.raises(UnsupportedError, match="STREAM NAME"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    definition.set("params", [])
    definition.set("no_commit", True)
    with pytest.raises(UnsupportedError, match="NO COMMIT"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_external_copy_programmatic_format_validation() -> None:
    expression = _external_table_ast()
    definition = expression.args["expression"]
    definition.set(
        "format",
        vexp.CopyFormat(this=exp.var("ORC"), expressions=[exp.var("allow_no_match")]),
    )

    with pytest.raises(UnsupportedError, match="name=value"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


def test_external_table_programmatic_columns_and_source_are_required() -> None:
    expression = _external_table_ast()
    expression.set("this", exp.to_table("ext"))

    with pytest.raises(UnsupportedError, match="require columns"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)

    expression = _external_table_ast()
    expression.args["expression"].set("source", None)
    with pytest.raises(UnsupportedError, match="requires a source"):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
