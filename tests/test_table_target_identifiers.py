"""Shared identifier contract for Milestone 1 table targets."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip

TARGET_FORMS = (
    "CREATE TABLE {target} (id BIGINT)",
    "CREATE TABLE {target} LIKE source",
    "CREATE TABLE {target} AS SELECT 1 AS id",
    "INSERT INTO {target} SELECT 1",
    "SELECT 1 INTO TABLE {target}",
    "DROP TABLE {target}",
)
ALL_PARSE_LEVELS = tuple(ErrorLevel)


def _target(expression: exp.Expr) -> exp.Table:
    target: object
    if isinstance(expression, (exp.Create, exp.Insert)):
        target = expression.this
        if isinstance(target, exp.Schema):
            target = target.this
    elif isinstance(expression, exp.Select):
        clause = expression.args.get("into")
        assert isinstance(clause, vexp.IntoTableClause)
        target = clause.this
    elif isinstance(expression, exp.Drop):
        target = expression.this
    else:
        raise AssertionError(f"Unexpected target family: {type(expression).__name__}")
    assert isinstance(target, exp.Table)
    return target


def _with_target(expression: exp.Expr, target: exp.Table) -> exp.Expr:
    expression = expression.copy()
    target = target.copy()
    if isinstance(expression, (exp.Create, exp.Insert)):
        owner = expression.this
        if isinstance(owner, exp.Schema):
            owner.set("this", target)
        else:
            expression.set("this", target)
    elif isinstance(expression, exp.Select):
        clause = expression.args.get("into")
        assert isinstance(clause, vexp.IntoTableClause)
        clause.set("this", target)
    elif isinstance(expression, exp.Drop):
        expression.set("this", target)
    else:
        raise AssertionError(f"Unexpected target family: {type(expression).__name__}")
    return expression


ASCII_127 = "a" * 127
ASCII_128 = "a" * 128
ASCII_129 = "a" * 129
MULTIBYTE_127 = "a" + "é" * 63
MULTIBYTE_128 = f"{MULTIBYTE_127}b"
MULTIBYTE_129 = "a" + "é" * 64


@pytest.mark.parametrize("template", TARGET_FORMS)
@pytest.mark.parametrize(
    "name",
    [
        "t",
        "s.t",
        "db.s.t",
        "MiXeD",
        "local",
        "cascade",
        "a_Δ9$",
        '"SELECT"',
        '"Δ name"',
        ASCII_127,
        ASCII_128,
        MULTIBYTE_127,
        MULTIBYTE_128,
    ],
)
def test_all_target_families_share_valid_identifier_contract(template: str, name: str) -> None:
    sql = template.format(target=name)
    expression = assert_roundtrip(sql, sql)
    target = _target(expression)
    assert 1 <= len(target.parts) <= 3
    assert all(isinstance(part, exp.Identifier) for part in target.parts)
    assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression


@pytest.mark.parametrize("template", TARGET_FORMS)
@pytest.mark.parametrize(
    "name",
    [
        "a.b.c.d",
        "db..t",
        '""',
        's.""',
        "9table",
        "$table",
        "Δtable",
        "a-table",
        ASCII_129,
        f'"{ASCII_129}"',
        MULTIBYTE_129,
        f'"{MULTIBYTE_129}"',
        '"\ud800"',
    ],
)
@pytest.mark.parametrize("error_level", ALL_PARSE_LEVELS)
def test_all_target_families_reject_invalid_source_names_at_every_level(
    template: str, name: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(template.format(target=name), read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE db.s.t /* target */ (id BIGINT)",
        "CREATE TABLE db.s.t /* target */ LIKE source",
        "CREATE TABLE db.s.t /* target */ AS SELECT src.id AS id FROM source AS src",
        "INSERT INTO db.s.t /* target */ (id) SELECT src.id FROM source AS src",
        "SELECT src.id INTO TABLE db.s.t /* target */ FROM source AS src",
        "DROP TABLE db.s.t /* target */ CASCADE",
    ],
)
def test_target_comments_and_adjacent_legal_aliases_roundtrip(sql: str) -> None:
    expression = assert_roundtrip(sql, sql)
    assert "target" in expression.sql(dialect="vertica")


def test_case_and_qualification_metadata_are_preserved() -> None:
    for template in TARGET_FORMS:
        expression = assert_roundtrip(template.format(target="NameSpace.MixedSchema.MiXeDTable"))
        target = _target(expression)
        assert [part.name for part in target.parts] == [
            "NameSpace",
            "MixedSchema",
            "MiXeDTable",
        ]
        assert target.catalog == "NameSpace"
        assert target.db == "MixedSchema"
        assert target.name == "MiXeDTable"


def _invalid_programmatic_targets() -> list[exp.Table]:
    return [
        exp.Table(this=exp.Identifier(this="", quoted=True)),
        exp.Table(this=exp.Identifier(this="9table", quoted=False)),
        exp.Table(this=exp.Identifier(this=ASCII_129, quoted=False)),
        exp.Table(this=exp.Identifier(this="\ud800", quoted=True)),
        exp.Table(this=exp.to_identifier("t"), catalog=exp.to_identifier("db")),
        exp.Table(
            this=exp.Dot(this=exp.to_identifier("t"), expression=exp.to_identifier("fourth")),
            db=exp.to_identifier("s"),
            catalog=exp.to_identifier("db"),
        ),
        exp.Table(this=exp.to_identifier("t"), db="s"),
        exp.Table(this=None),
        exp.Table(this=exp.to_identifier("t"), alias=False),
        exp.Table(this=exp.Identifier(this="t", quoted=False, global_=False)),
        exp.Table(this=exp.Identifier(this="t", quoted="false")),
    ]


@pytest.mark.parametrize("template", TARGET_FORMS)
@pytest.mark.parametrize("target", _invalid_programmatic_targets())
def test_strict_generation_rejects_malformed_programmatic_targets(
    template: str, target: exp.Table
) -> None:
    expression = parse_one(template.format(target="valid_target"), read="vertica")
    malformed = _with_target(expression, target)
    with pytest.raises(UnsupportedError):
        malformed.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("template", TARGET_FORMS)
@pytest.mark.parametrize("name", ["t", "s.t", "db.s.t", '"Δ name"'])
def test_programmatic_targets_generate_and_reparse(template: str, name: str) -> None:
    expression = parse_one(template.format(target="valid_target"), read="vertica")
    target = exp.to_table(name, dialect="vertica")
    updated = _with_target(expression, target)
    generated = updated.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    assert parse_one(generated, read="vertica") == updated


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE db.s.t (id BIGINT)",
        "INSERT INTO db.s.t SELECT 1",
        "SELECT 1 INTO TABLE db.s.t",
        "DROP TABLE db.s.t",
    ],
)
def test_foreign_parsed_canonical_targets_generate_valid_vertica(sql: str) -> None:
    expression = parse_one(sql, read="postgres")
    generated = expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)
    reparsed = parse_one(generated, read="vertica")
    assert _target(reparsed).sql(dialect="vertica") == "db.s.t"


def test_temporary_target_forms_share_the_same_contract() -> None:
    assert_roundtrip("CREATE LOCAL TEMPORARY TABLE db.s.t (id BIGINT)")
    assert_roundtrip("CREATE GLOBAL TEMP TABLE db.s.t AS SELECT 1 AS id")
    assert_roundtrip("SELECT 1 INTO LOCAL TEMP TABLE db.s.t ON COMMIT PRESERVE ROWS")

    for sql in (
        "CREATE LOCAL TEMPORARY TABLE db..t (id BIGINT)",
        "CREATE GLOBAL TEMP TABLE a.b.c.d AS SELECT 1 AS id",
        "SELECT 1 INTO LOCAL TEMP TABLE db..t ON COMMIT PRESERVE ROWS",
    ):
        for error_level in ALL_PARSE_LEVELS:
            with pytest.raises(ParseError):
                parse_one(sql, read="vertica", error_level=error_level)
