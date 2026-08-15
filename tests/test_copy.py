"""Vertica COPY parser and generator regressions."""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    "sql",
    [
        "COPY public.t FROM '/data/t.csv'",
        "COPY t FROM STDIN",
        "COPY t FROM LOCAL STDIN GZIP NO COMMIT",
        "COPY t FROM '/a' ON node1 GZIP, '/b' ON (node2, node3) BZIP, "
        "'/c' ON ANY NODE ZSTD, '/d' ON EACH NODE UNCOMPRESSED",
        "COPY t FROM LOCAL '/client/a.csv' GZIP, '/client/b.csv' ZSTD",
        "COPY t FROM 's3://bucket/t/*/*/*.parquet' ON ANY NODE "
        "PARTITION COLUMNS event_date, region PARQUET",
        "COPY target_t(id, value) FROM VERTICA "
        "source_ns.source_schema.source_t(source_id, source_value) "
        "STREAM NAME 'replication' NO COMMIT",
        "COPY t FROM '/data/t.native' NATIVE",
        "COPY t FROM '/data/t.native_varchar' NATIVE VARCHAR",
        "COPY t FROM '/data/t.fixed' FIXEDWIDTH COLSIZES (4, 8, 12) SKIP BYTES 2",
        "COPY t FROM '/data/t.orc' ORC",
        "COPY t FROM '/data/t.parquet' PARQUET",
        "COPY t FROM SOURCE CustomSource(path='s3://bucket/data') "
        "FILTER FirstFilter(mode='strict') FILTER SecondFilter(trim=TRUE) "
        "PARSER CustomParser(version=2)",
        "COPY t FROM 's3://bucket/events/*.json' ON ANY NODE "
        "PARSER FJSONPARSER(flatten_arrays=TRUE, flatten_maps=FALSE)",
        "COPY t FROM '/data/t.csv' REJECTED DATA AS TABLE load_rejects",
    ],
)
def test_copy_source_and_format_matrix(sql: str) -> None:
    expression = assert_roundtrip(sql)
    assert isinstance(expression, vexp.VerticaCopy)
    assert isinstance(expression, exp.Copy)


def test_copy_columns_hint_and_options() -> None:
    expression = assert_roundtrip(
        "COPY /*+ LABEL('daily_load') */ ns.s.t "
        "(raw_id FILLER VARCHAR, id AS raw_id::INT, "
        "event_ts FORMAT 'YYYY-MM-DD HH24:MI:SS' NULL AS '', "
        "payload DELIMITER '|' ENCLOSED BY '\"' ENFORCELENGTH NO ESCAPE) "
        "FROM '/data/events.dat'"
    )
    assert isinstance(expression, vexp.VerticaCopy)
    assert expression.args.get("hint")
    assert len(expression.expressions) == 4


def test_copy_separate_column_options() -> None:
    expression = assert_roundtrip(
        "COPY t COLUMN OPTION "
        "(c1 DELIMITER ',', c2 ESCAPE AS '\\' NULL AS 'NULL') "
        "FROM '/data/t.csv'"
    )
    assert len(expression.args["column_options"]) == 2


def test_copy_rejection_outputs_and_handling_parameters() -> None:
    expression = assert_roundtrip(
        "COPY t FROM '/data/t.csv' ERROR TOLERANCE "
        "EXCEPTIONS '/reject/e1' ON node1, '/reject/e2' ON node2 "
        "REJECTED DATA '/reject/r1' ON node1, '/reject/r2' ON node2 "
        "REJECTMAX 100 STREAM NAME 'messy_load' NO COMMIT"
    )
    assert [parameter.name for parameter in expression.args["params"]] == [
        "ERROR TOLERANCE",
        "EXCEPTIONS",
        "REJECTED DATA",
        "REJECTMAX",
        "STREAM NAME",
    ]


def test_copy_global_and_collection_parameters() -> None:
    assert_roundtrip(
        "COPY t FROM '/data/t.csv' ABORT ON ERROR DELIMITER ',' ENCLOSED BY '\"' "
        "ENFORCELENGTH ESCAPE AS '\\' NULL AS 'NULL' RECORD TERMINATOR E'\\n' "
        "SKIP 1 TRAILING NULLCOLS"
    )
    assert_roundtrip(
        "COPY t FROM '/data/t.txt' COLLECTIONDELIMITER ',' COLLECTIONOPEN '[' "
        "COLLECTIONCLOSE ']' COLLECTIONNULLELEMENT 'null' COLLECTIONENCLOSE '\"'"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "COPY t '/data/t.csv'",
        "COPY t FROM LOCAL '/data/t.csv' ON node1",
        "COPY t COLUMN OPTION (c1 FILLER INT) FROM '/data/t.csv'",
        "COPY t (c1 ESCAPE AS '\\' NO ESCAPE) FROM '/data/t.csv'",
        "COPY t FROM '/data/t.csv' ESCAPE AS '\\' NO ESCAPE",
        "COPY t FROM '/data/t.csv' SKIP 1 DELIMITER ','",
        "COPY t FROM '/data/t.csv' REJECTMAX 1 REJECTMAX 2",
        "COPY t FROM LOCAL '/data/t.csv' PARTITION COLUMNS event_date",
        "COPY t FROM '/data/t.csv' NATIVE PARQUET",
        "COPY t FROM '/data/t.csv' NO COMMIT SKIP 1",
        "COPY t FROM FILTER F(mode='strict') SOURCE S()",
        "COPY FROM '/data/t.csv'",
        "COPY t COLUMN OPTION (c1 AS source_c1) FROM '/data/t.csv'",
        "COPY t (c1 AS) FROM '/data/t.csv'",
        "COPY t (c1 DELIMITER) FROM '/data/t.csv'",
        "COPY t FROM VERTICA",
        "COPY t FROM",
        "COPY t FROM '/data/t.csv' ON",
        "COPY t FROM '/data/t.csv' FIXEDWIDTH",
        "COPY t FROM SOURCE",
        "COPY t FROM '/data/t.csv' EXCEPTIONS",
        "COPY t FROM '/data/t.csv' EXCEPTIONS '/reject/e' ON",
        "COPY t FROM '/data/t.csv' DELIMITER",
    ],
)
def test_copy_rejects_invalid_clause_combinations(sql: str) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica")


@pytest.mark.parametrize(
    ("compact", "multiline"),
    [
        ("COPY t () FROM '/data/t.csv'", "COPY t (\n)\nFROM '/data/t.csv'"),
        (
            "COPY t COLUMN OPTION () FROM '/data/t.csv'",
            "COPY t\nCOLUMN OPTION (\n)\nFROM '/data/t.csv'",
        ),
        (
            "COPY t FROM '/data/t.csv' PARTITION COLUMNS",
            "COPY t\nFROM '/data/t.csv'\nPARTITION COLUMNS",
        ),
        ("COPY t FROM VERTICA source_t()", "COPY t\nFROM VERTICA source_t(\n)"),
        ("COPY t FROM '/data/t.csv' ON ()", "COPY t\nFROM '/data/t.csv' ON (\n)"),
    ],
)
def test_copy_rejects_explicit_empty_lists(compact: str, multiline: str) -> None:
    for sql in (compact, multiline):
        with pytest.raises(ParseError):
            parse_one(sql, read="vertica")
