"""Vertica CREATE TABLE physical-design regressions."""

from __future__ import annotations

import pytest
from sqlglot import ErrorLevel, exp, parse, parse_one
from sqlglot.errors import ParseError, UnsupportedError

from sqlglot_vertica import expressions as vexp
from tests.helpers import assert_roundtrip


def test_create_table_full_physical_design() -> None:
    sql = (
        "CREATE TABLE IF NOT EXISTS analytics.orders "
        "(order_id BIGINT ENCODING DELTAVAL ACCESSRANK 1, "
        "customer_id BIGINT NOT NULL ENCODING RLE, "
        "order_ts TIMESTAMP, amount DECIMAL(18, 2)) "
        "ORDER BY customer_id, order_ts "
        "SEGMENTED BY HASH(customer_id) ALL NODES "
        "KSAFE 1 "
        "PARTITION BY YEAR(order_ts) GROUP BY YEAR(order_ts) "
        "ACTIVEPARTITIONCOUNT 12 "
        "INCLUDE SCHEMA PRIVILEGES "
        "DISK_QUOTA '20G'"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert expression.kind == "TABLE"
    assert isinstance(expression.this, exp.Schema)

    first_column = expression.this.expressions[0]
    assert isinstance(first_column, exp.ColumnDef)
    assert first_column.find(exp.EncodeColumnConstraint)
    assert first_column.find(vexp.AccessRankColumnConstraint)

    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        exp.Order,
        vexp.TableSegmentationProperty,
        vexp.KsafeProperty,
        vexp.TablePartitionProperty,
        vexp.InheritedPrivilegesProperty,
        vexp.DiskQuotaProperty,
    ]

    segmentation = properties[1].this
    assert isinstance(segmentation, vexp.ProjectionSegmentation)
    assert segmentation.args["segmented"] is True
    assert segmentation.args["all_nodes"] is True

    partition = properties[3]
    assert partition.args["group"]
    assert partition.args["active_partition_count"].to_py() == 12


def test_create_table_unsegmented_and_bare_ksafe() -> None:
    expression = assert_roundtrip(
        "CREATE TABLE small_dimension (id BIGINT, name VARCHAR) "
        "UNSEGMENTED ALL NODES KSAFE EXCLUDE PRIVILEGES DISK_QUOTA '1G'",
        "CREATE TABLE small_dimension (id BIGINT, name VARCHAR) "
        "UNSEGMENTED ALL NODES KSAFE EXCLUDE PRIVILEGES DISK_QUOTA '1G'",
    )

    segmentation = expression.find(vexp.TableSegmentationProperty)
    assert segmentation
    assert segmentation.this.args["segmented"] is False

    ksafe = expression.find(vexp.KsafeProperty)
    assert ksafe
    assert ksafe.this is None

    privileges = expression.find(vexp.InheritedPrivilegesProperty)
    assert privileges
    assert privileges.args["include"] is False
    assert privileges.args.get("schema") is False


@pytest.mark.parametrize(
    "clause",
    [
        "PARTITION BY YEAR(ts)",
        "PARTITION BY YEAR(ts) ACTIVEPARTITIONCOUNT 6",
        "PARTITION BY YEAR(ts) GROUP BY YEAR(ts)",
    ],
)
def test_create_table_partition_optional_forms(clause: str) -> None:
    sql = f"CREATE TABLE events (id BIGINT, ts TIMESTAMP) {clause}"
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression.find(vexp.TablePartitionProperty), vexp.TablePartitionProperty)


def test_create_table_generator_enforces_clause_order_without_mutation() -> None:
    canonical = (
        "CREATE TABLE t (id BIGINT, ts TIMESTAMP) ORDER BY id "
        "SEGMENTED BY HASH(id) ALL NODES KSAFE 1 "
        "PARTITION BY YEAR(ts) INCLUDE PRIVILEGES DISK_QUOTA '1G'"
    )
    expression = parse_one(canonical, read="vertica")
    properties = expression.args["properties"]
    reversed_properties = list(reversed(properties.expressions))
    properties.set("expressions", reversed_properties)

    assert expression.sql(dialect="vertica") == canonical
    assert properties.expressions == reversed_properties


def _add_create_property(sql: str, prop: exp.Expr) -> exp.Create:
    expression = parse_one(sql, read="vertica")
    assert isinstance(expression, exp.Create)
    properties = expression.args.get("properties")
    if properties is None:
        properties = exp.Properties(expressions=[])
        expression.set("properties", properties)
    assert isinstance(properties, exp.Properties)
    properties.append("expressions", prop)
    return expression


def _property_from(sql: str, property_type: type[exp.Expr]) -> exp.Expr:
    expression = parse_one(sql, read="vertica")
    prop = expression.find(property_type)
    assert prop is not None
    return prop.copy()


def _invalid_create_table_ast(case: str) -> exp.Create:
    if case == "local-without-temporary":
        return _add_create_property("CREATE TABLE t (id BIGINT)", vexp.LocalProperty())
    if case == "contradictory-scopes":
        return _add_create_property(
            "CREATE GLOBAL TEMPORARY TABLE t (id BIGINT)", vexp.LocalProperty()
        )
    if case == "permanent-on-commit":
        return _add_create_property("CREATE TABLE t (id BIGINT)", exp.OnCommitProperty(delete=True))
    if case == "local-quota":
        return _add_create_property(
            "CREATE LOCAL TEMPORARY TABLE t (id BIGINT)",
            vexp.DiskQuotaProperty(this=exp.Literal.string("1G")),
        )
    if case == "temporary-ctas-segmentation":
        segmentation = _property_from(
            "CREATE TABLE source_copy AS SELECT id FROM source SEGMENTED BY HASH(id) ALL NODES",
            vexp.CtasSegmentationProperty,
        )
        return _add_create_property("CREATE TEMPORARY TABLE t AS SELECT 1 AS id", segmentation)
    if case == "ctas-no-projection":
        return _add_create_property(
            "CREATE TEMPORARY TABLE t AS SELECT 1 AS id", vexp.NoProjectionProperty()
        )
    if case == "definition-at-epoch":
        epoch = _property_from(
            "CREATE TABLE snapshot AS AT EPOCH LATEST SELECT 1 AS id",
            vexp.AtEpochProperty,
        )
        return _add_create_property("CREATE TABLE t (id BIGINT)", epoch)
    if case == "wrong-properties-container":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        expression.set("properties", exp.Literal.string("not properties"))
        return expression
    if case == "wrong-property-node":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        expression.set("properties", exp.Properties(expressions=[exp.Literal.number(1)]))
        return expression
    if case == "empty-properties-container":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        expression.set("properties", exp.Properties(expressions=[]))
        return expression
    if case == "duplicate-property":
        return _add_create_property(
            "CREATE GLOBAL TEMPORARY TABLE t (id BIGINT)", exp.GlobalProperty()
        )
    if case == "falsey-foreign-create-field":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        expression.set("foreign_extra", False)
        return expression
    if case == "mixed-definition-columns":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        assert isinstance(expression.this, exp.Schema)
        expression.this.append("expressions", exp.to_identifier("untyped"))
        return expression
    if case == "like-with-query":
        expression = parse_one("CREATE TABLE t LIKE source", read="vertica")
        expression.set("expression", exp.select("1"))
        return expression
    if case == "ctas-with-definition-schema":
        expression = parse_one("CREATE TABLE t AS SELECT 1 AS id", read="vertica")
        definition = parse_one("CREATE TABLE x (id BIGINT)", read="vertica")
        expression.set("this", definition.this.copy())
        return expression
    if case == "missing-form":
        return exp.Create(this=exp.to_table("t"), kind="TABLE")
    if case == "non-string-table-kind":
        expression = parse_one("CREATE TABLE t (id BIGINT)", read="vertica")
        expression.set("kind", exp.var("TABLE"))
        return expression
    if case == "invalid-on-commit-state":
        expression = parse_one(
            "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DELETE ROWS", read="vertica"
        )
        on_commit = expression.find(exp.OnCommitProperty)
        assert on_commit is not None
        on_commit.set("delete", "yes")
        return expression
    if case == "invalid-encoded-by-child":
        expression = parse_one(
            "CREATE TABLE t AS SELECT 1 AS id ENCODED BY id ENCODING RLE", read="vertica"
        )
        encoded = expression.find(vexp.EncodedByProperty)
        assert encoded is not None
        encoded.set("expressions", [exp.to_identifier("id")])
        return expression
    if case == "invalid-like-option":
        expression = parse_one("CREATE TABLE t LIKE source INCLUDING PROJECTIONS", read="vertica")
        like = expression.find(exp.LikeProperty)
        assert like is not None
        like.set(
            "expressions",
            [exp.Property(this=exp.var("INCLUDING"), value=exp.var("CONSTRAINTS"))],
        )
        return expression
    raise AssertionError(f"unknown CREATE TABLE mutation case: {case}")


@pytest.mark.parametrize(
    "case",
    [
        "local-without-temporary",
        "contradictory-scopes",
        "permanent-on-commit",
        "local-quota",
        "temporary-ctas-segmentation",
        "ctas-no-projection",
        "definition-at-epoch",
        "wrong-properties-container",
        "wrong-property-node",
        "empty-properties-container",
        "duplicate-property",
        "falsey-foreign-create-field",
        "mixed-definition-columns",
        "like-with-query",
        "ctas-with-definition-schema",
        "missing-form",
        "non-string-table-kind",
        "invalid-on-commit-state",
        "invalid-encoded-by-child",
        "invalid-like-option",
    ],
)
def test_create_table_programmatic_mutation_matrix_fails_atomically(case: str) -> None:
    expression = _invalid_create_table_ast(case)
    with pytest.raises(UnsupportedError):
        expression.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    "case",
    ["local-without-temporary", "like-with-query", "temporary-ctas-segmentation"],
)
def test_nested_create_table_mutations_fail_atomically(case: str) -> None:
    nested = exp.Paren(this=_invalid_create_table_ast(case))
    with pytest.raises(UnsupportedError):
        nested.sql(dialect="vertica", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "CREATE TABLE t (id BIGINT) ORDER BY id DESC",
            "does not support ASC or DESC",
        ),
        (
            "CREATE TABLE t (id BIGINT) SEGMENTED BY HASH(id) ALL NODES OFFSET 1",
            "forbids OFFSET",
        ),
        (
            "CREATE TABLE t (id BIGINT) SEGMENTED BY HASH(id)",
            "requires ALL NODES",
        ),
        (
            "CREATE TABLE t (id BIGINT) KSAFE 1 ORDER BY id",
            "out-of-order CREATE TABLE clause",
        ),
        (
            "CREATE TABLE t (id BIGINT) PARTITION BY id ACTIVEPARTITIONCOUNT 1.5",
            "requires an integer",
        ),
        (
            "CREATE TABLE t (id BIGINT) DISK_QUOTA 1",
            "requires a quoted quota",
        ),
    ],
)
def test_create_table_rejects_invalid_physical_design(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


def test_create_table_as_full_physical_design() -> None:
    sql = (
        "CREATE TABLE IF NOT EXISTS analytics.promotions "
        "EXCLUDE SCHEMA PRIVILEGES "
        "AS /*+ LABEL('promotion_ctas') */ AT EPOCH LATEST "
        "SELECT customer_state, customer_zip FROM customer_dimension "
        "ORDER BY customer_state "
        "ENCODED BY customer_state ENCODING RLE ACCESSRANK 1, "
        "customer_zip ACCESSRANK 2 "
        "SEGMENTED BY HASH(customer_state) ALL NODES "
        "DISK_QUOTA '5G'"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert isinstance(expression.this, exp.Table)
    assert isinstance(expression.expression, exp.Select)

    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        vexp.InheritedPrivilegesProperty,
        vexp.CtasHintProperty,
        vexp.AtEpochProperty,
        vexp.EncodedByProperty,
        vexp.CtasSegmentationProperty,
        vexp.CtasDiskQuotaProperty,
    ]
    assert len(properties[3].expressions) == 2


def test_create_table_as_label_only() -> None:
    sql = "CREATE TABLE labeled AS /*+ LABEL('job') */ SELECT 1 AS id"
    expression = assert_roundtrip(sql, sql)

    properties = expression.args["properties"].expressions
    assert len(properties) == 1
    assert isinstance(properties[0], vexp.CtasHintProperty)


def test_create_table_as_without_optional_clauses() -> None:
    sql = "CREATE TABLE simple_copy AS SELECT id FROM source"
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression.expression, exp.Select)
    assert expression.args.get("properties") is None


def test_create_table_as_column_names_with_physical_design() -> None:
    sql = (
        "CREATE TABLE promotions "
        "(state ENCODING RLE ACCESSRANK 1, zip, GROUPED(state, zip)) "
        "INCLUDE PRIVILEGES AS "
        "SELECT customer_state, customer_zip, customer_state FROM customer_dimension"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression.this, exp.Schema)
    assert isinstance(expression.this.expressions[0], vexp.ProjectionColumn)
    assert isinstance(expression.this.expressions[1], exp.Identifier)
    assert isinstance(expression.this.expressions[2], vexp.GroupedProjectionColumns)


@pytest.mark.parametrize(
    "epoch",
    [
        "AT EPOCH 42",
        "AT TIME '2026-08-15 12:30:00'",
    ],
)
def test_create_table_as_historical_epoch_forms(epoch: str) -> None:
    sql = f"CREATE TABLE snapshot AS {epoch} SELECT id FROM source"
    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression.find(vexp.AtEpochProperty), vexp.AtEpochProperty)


CTAS_AT_EPOCH_POSITIONS = [
    "CREATE TABLE t AS {clause} SELECT 1",
    "CREATE TEMPORARY TABLE t AS {clause} SELECT 1",
    "CREATE LOCAL TEMPORARY TABLE t AS {clause} SELECT 1",
]


@pytest.mark.parametrize(
    ("clause", "message"),
    [
        ("AT EPOCH 1.5", "AT EPOCH requires LATEST or an integer"),
        ("AT TIME now", "AT TIME requires a quoted timestamp"),
        ("AT SNAPSHOT 1", "AT requires EPOCH or TIME"),
    ],
)
@pytest.mark.parametrize("position", CTAS_AT_EPOCH_POSITIONS)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_ctas_at_epoch_malformed_forms_fail_closed_at_every_error_level(
    error_level: ErrorLevel, position: str, clause: str, message: str
) -> None:
    """``_parse_at_epoch_property``'s three malformed-value branches route through
    the CTAS family's guaranteed-raise wrapper (``_raise_create_table_error``)
    and must raise ``ParseError`` -- never ``UnboundLocalError``,
    ``AssertionError``, or silent acceptance of an invalid value -- at every
    error level and CTAS position (permanent, unscoped temporary, scoped
    temporary).
    """

    sql = position.format(clause=clause)
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "option",
    [
        "INCLUDING PROJECTIONS",
        "EXCLUDING PROJECTIONS",
    ],
)
def test_create_table_like_options_privileges_and_quota(option: str) -> None:
    sql = (
        f"CREATE TABLE IF NOT EXISTS archive LIKE analytics.source {option} "
        "INCLUDE SCHEMA PRIVILEGES DISK_QUOTA '3G'"
    )
    expression = assert_roundtrip(sql, sql)

    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        exp.LikeProperty,
        vexp.InheritedPrivilegesProperty,
        vexp.DiskQuotaProperty,
    ]


def test_create_table_like_without_optional_clauses() -> None:
    sql = "CREATE TABLE archive LIKE analytics.source"
    expression = assert_roundtrip(sql, sql)

    properties = expression.args["properties"].expressions
    assert len(properties) == 1
    assert isinstance(properties[0], exp.LikeProperty)
    assert properties[0].expressions == []


def test_create_global_temporary_table_without_projection() -> None:
    sql = (
        "CREATE GLOBAL TEMPORARY TABLE session_stage (id BIGINT, payload VARCHAR) "
        "ON COMMIT PRESERVE ROWS NO PROJECTION "
        "INCLUDE PRIVILEGES DISK_QUOTA '1G'"
    )
    expression = assert_roundtrip(sql, sql)

    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        exp.GlobalProperty,
        exp.TemporaryProperty,
        exp.OnCommitProperty,
        vexp.NoProjectionProperty,
        vexp.InheritedPrivilegesProperty,
        vexp.DiskQuotaProperty,
    ]


def test_create_local_temporary_table_with_physical_design() -> None:
    sql = (
        "CREATE LOCAL TEMPORARY TABLE session_stage (id BIGINT, payload VARCHAR) "
        "ON COMMIT DELETE ROWS ORDER BY id "
        "UNSEGMENTED ALL NODES KSAFE 0 EXCLUDE PRIVILEGES"
    )
    expression = assert_roundtrip(sql, sql)

    properties = expression.args["properties"].expressions
    assert isinstance(properties[0], vexp.LocalProperty)
    assert isinstance(properties[1], exp.TemporaryProperty)
    assert isinstance(properties[2], exp.OnCommitProperty)


def test_create_temporary_table_as() -> None:
    sql = (
        "CREATE TEMPORARY TABLE session_stage ON COMMIT PRESERVE ROWS "
        "AS /*+ LABEL('temp_ctas') */ AT TIME '2026-08-15 12:30:00' "
        "SELECT id FROM source "
        "ENCODED BY id ENCODING RLE DISK_QUOTA '1G'"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert isinstance(expression.expression, exp.Select)
    assert isinstance(expression.find(vexp.EncodedByProperty), vexp.EncodedByProperty)


@pytest.mark.parametrize("scope", ["GLOBAL", "LOCAL"])
@pytest.mark.parametrize("spelling", ["TEMP", "TEMPORARY"])
@pytest.mark.parametrize("on_commit", ["DELETE", "PRESERVE"])
def test_create_scoped_temporary_table_as_matrix(scope: str, spelling: str, on_commit: str) -> None:
    """Scoped temporary CTAS accepts both scopes, both spellings, and both ON COMMIT values."""

    sql = f"CREATE {scope} {spelling} TABLE t ON COMMIT {on_commit} ROWS AS SELECT 1 AS id"
    expected = f"CREATE {scope} TEMPORARY TABLE t ON COMMIT {on_commit} ROWS AS SELECT 1 AS id"
    expression = assert_roundtrip(sql, expected)

    assert isinstance(expression, exp.Create)
    assert isinstance(expression.this, exp.Table)
    assert isinstance(expression.expression, exp.Select)

    scope_type = exp.GlobalProperty if scope == "GLOBAL" else vexp.LocalProperty
    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        scope_type,
        exp.TemporaryProperty,
        exp.OnCommitProperty,
    ]
    assert properties[2].args["delete"] is (on_commit == "DELETE")


def test_create_scoped_temporary_table_as_full_physical_design() -> None:
    """Scoped temporary CTAS supports the full unscoped post-query clause set."""

    sql = (
        "CREATE GLOBAL TEMPORARY TABLE IF NOT EXISTS analytics.promotions "
        "ON COMMIT PRESERVE ROWS "
        "AS /*+ LABEL('promotion_ctas') */ AT EPOCH LATEST "
        "SELECT customer_state, customer_zip FROM customer_dimension "
        "ORDER BY customer_state "
        "ENCODED BY customer_state ENCODING RLE ACCESSRANK 1, "
        "customer_zip ACCESSRANK 2 "
        "DISK_QUOTA '5G'"
    )
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression, exp.Create)
    assert expression.args.get("exists") is True
    assert isinstance(expression.this, exp.Table)
    assert isinstance(expression.expression, exp.Select)

    properties = expression.args["properties"].expressions
    assert [type(prop) for prop in properties] == [
        exp.GlobalProperty,
        exp.TemporaryProperty,
        exp.OnCommitProperty,
        vexp.CtasHintProperty,
        vexp.AtEpochProperty,
        vexp.EncodedByProperty,
        vexp.CtasDiskQuotaProperty,
    ]
    assert len(properties[5].expressions) == 2


@pytest.mark.parametrize("scope", ["GLOBAL", "LOCAL"])
def test_create_scoped_temporary_table_as_column_names(scope: str) -> None:
    sql = f"CREATE {scope} TEMPORARY TABLE t (a, b) AS SELECT 1 AS a, 2 AS b"
    expression = assert_roundtrip(sql, sql)

    assert isinstance(expression.this, exp.Schema)
    assert expression.this.expressions == [exp.to_identifier("a"), exp.to_identifier("b")]
    assert isinstance(expression.expression, exp.Select)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE GLOBAL TEMPORARY TABLE t AS (SELECT 1 AS id)",
        "CREATE LOCAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS (SELECT 1 AS id)",
    ],
)
def test_create_scoped_temporary_table_as_parenthesized_query(sql: str) -> None:
    """Ecosystem tooling (for example dbt-vertica) emits parenthesized CTAS query bodies."""

    expression = assert_roundtrip(sql, sql)
    assert isinstance(expression.expression, exp.Subquery)
    assert isinstance(expression.expression.this, exp.Select)


def test_create_scoped_temporary_table_as_matches_unscoped_contract() -> None:
    """Scoped temporary CTAS keeps every unscoped property except the added scope marker."""

    unscoped = parse_one(
        "CREATE TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS SELECT id FROM source "
        "ENCODED BY id ENCODING RLE DISK_QUOTA '1G'",
        read="vertica",
    )
    scoped_global = parse_one(
        "CREATE GLOBAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS SELECT id FROM source "
        "ENCODED BY id ENCODING RLE DISK_QUOTA '1G'",
        read="vertica",
    )

    unscoped_props = [type(prop) for prop in unscoped.args["properties"].expressions]
    global_props = [type(prop) for prop in scoped_global.args["properties"].expressions]

    assert global_props[0] is exp.GlobalProperty
    assert global_props[1:] == unscoped_props
    assert scoped_global.this == unscoped.this
    assert scoped_global.expression == unscoped.expression


@pytest.mark.parametrize("scope", ["GLOBAL", "LOCAL"])
def test_create_scoped_temporary_table_dispatch_neighbors(scope: str) -> None:
    """Scope does not change definition-form-vs-CTAS disambiguation or LIKE dispatch."""

    definition = parse_one(
        f"CREATE {scope} TEMPORARY TABLE t (id BIGINT, payload VARCHAR) ON COMMIT PRESERVE ROWS",
        read="vertica",
    )
    assert isinstance(definition.this, exp.Schema)
    assert all(isinstance(item, exp.ColumnDef) for item in definition.this.expressions)
    assert definition.args.get("expression") is None

    ctas_with_columns = parse_one(
        f"CREATE {scope} TEMPORARY TABLE t (a, b) ON COMMIT PRESERVE ROWS AS SELECT 1 AS a, 2 AS b",
        read="vertica",
    )
    assert isinstance(ctas_with_columns.this, exp.Schema)
    assert not any(isinstance(item, exp.ColumnDef) for item in ctas_with_columns.this.expressions)
    assert isinstance(ctas_with_columns.expression, exp.Select)

    with pytest.raises(ParseError, match="does not support LIKE"):
        parse_one(f"CREATE {scope} TEMPORARY TABLE t LIKE source", read="vertica")


@pytest.mark.parametrize(
    ("sql", "target_sql"),
    [
        (
            "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id",
            "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id",
        ),
        (
            "CREATE GLOBAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS SELECT 1 AS id",
            "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id ON COMMIT PRESERVE ROWS",
        ),
    ],
)
def test_create_global_temporary_table_as_foreign_generation_matches_definition_form(
    sql: str, target_sql: str
) -> None:
    """GLOBAL-scoped CTAS foreign generation matches the existing GLOBAL definition-form/CTAS
    contract: canonical `exp.GlobalProperty` generates in PostgreSQL/MySQL and cleanly fails
    unsupported in DuckDB/SQLite, exactly as it already does for definition-form temporary
    tables and for the unscoped CTAS properties it now sits alongside."""

    expression = parse_one(sql, read="vertica")

    assert expression.sql(dialect="postgres") == target_sql
    assert expression.sql(dialect="mysql") == target_sql

    for dialect in ("duckdb", "sqlite"):
        with pytest.raises(UnsupportedError, match="globalproperty"):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize("dialect", ["postgres", "duckdb", "mysql", "sqlite"])
def test_create_local_temporary_table_as_foreign_generation_fails_atomically(
    dialect: str,
) -> None:
    """LOCAL-scoped CTAS foreign generation fails atomically in every tested foreign dialect,
    exactly as `vexp.LocalProperty` already does for definition-form LOCAL temporary tables
    today, and, independently of scope, as unscoped CTAS's own `InheritedPrivilegesProperty`
    does (`CREATE TABLE t INCLUDE PRIVILEGES AS SELECT 1 AS id` also raises `ValueError`
    against every tested foreign dialect). Before Q05, no foreign dialect's
    `PROPERTIES_LOCATION` map knew any Vertica-only property, so
    `sqlglot.Generator.locate_properties`'s direct dict lookup raised a raw `KeyError`; Q05
    registered every `vexp` `Property` subclass with
    `sqlglot_vertica.foreign_properties.patch_foreign_properties_location`, so the same lookup
    now raises the same `ValueError("Unsupported expression type <Name>")`
    `vexp.DropViews` already raises for an unregistered custom root, at every
    `unsupported_level` (see `tests/test_foreign_property_atomicity.py` for the exhaustive,
    all-property, all-level sweep this pin now mirrors for one representative statement)."""

    expression = parse_one("CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS id", read="vertica")

    with pytest.raises(ValueError, match="Unsupported expression type LocalProperty"):
        expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        (
            "CREATE TABLE t (id) AS SELECT id FROM source ENCODED BY id ENCODING RLE",
            "mutually exclusive",
        ),
        (
            "CREATE TEMPORARY TABLE t LIKE source",
            "does not support LIKE",
        ),
        (
            "CREATE GLOBAL TEMPORARY TABLE t LIKE source",
            "does not support LIKE",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t LIKE source",
            "does not support LIKE",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t AS SELECT id FROM source DISK_QUOTA '1G'",
            "LOCAL temporary tables cannot specify DISK_QUOTA",
        ),
        (
            "CREATE GLOBAL TEMPORARY TABLE t AS SELECT id FROM source "
            "SEGMENTED BY HASH(id) ALL NODES",
            "Temporary CTAS does not support a segmentation clause",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t AS SELECT id FROM source "
            "SEGMENTED BY HASH(id) ALL NODES",
            "Temporary CTAS does not support a segmentation clause",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) NO PROJECTION ORDER BY id",
            "NO PROJECTION cannot be combined",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) NO PROJECTION KSAFE 0",
            "NO PROJECTION cannot be combined",
        ),
        (
            "CREATE LOCAL TEMPORARY TABLE t (id BIGINT) DISK_QUOTA '1G'",
            "LOCAL temporary tables cannot specify DISK_QUOTA",
        ),
        (
            "CREATE TEMPORARY TABLE t AS SELECT id FROM source SEGMENTED BY HASH(id) ALL NODES",
            "Temporary CTAS does not support a segmentation clause",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) PARTITION BY id",
            "out-of-order CREATE TABLE clause",
        ),
        (
            "CREATE TABLE t AS SELECT id FROM source "
            "SEGMENTED BY HASH(id) ALL NODES ENCODED BY id ENCODING RLE",
            "out-of-order CREATE TABLE AS clause",
        ),
        (
            "CREATE TABLE t AS SELECT id FROM source ENCODED BY id",
            "require ENCODING or ACCESSRANK",
        ),
        (
            "CREATE TABLE t LIKE source INCLUDING CONSTRAINTS",
            "must be followed by PROJECTIONS",
        ),
        (
            "CREATE GLOBAL TABLE t (id BIGINT)",
            "scope requires TEMPORARY",
        ),
        (
            "CREATE OR REPLACE TABLE t (id BIGINT)",
            "OR REPLACE TABLE is not supported",
        ),
        (
            "CREATE TABLE",
            "Expected table name",
        ),
        (
            "CREATE TABLE t",
            "requires AS followed by a query",
        ),
        (
            "CREATE TABLE t AS",
            "requires a SELECT query",
        ),
        (
            "CREATE TABLE t AS SELECT 1 ENCODED BY",
            "requires at least one column reference",
        ),
        (
            "CREATE TABLE t AS SELECT 1 AS id ENCODED BY id ENCODING",
            "ENCODING requires an encoding type",
        ),
        (
            "CREATE TABLE t LIKE",
            "Expected table name",
        ),
        (
            "CREATE TABLE t LIKE source INCLUDING PROJECTIONS EXCLUDING PROJECTIONS",
            "accepts only one projection-copy option",
        ),
        (
            "CREATE TABLE t LIKE source DISK_QUOTA '1G' INCLUDE PRIVILEGES",
            "out-of-order CREATE TABLE LIKE clause",
        ),
        (
            "CREATE TABLE t () AS SELECT 1",
            "column-name list cannot be empty",
        ),
        (
            "CREATE TABLE t (GROUPED(id)) AS SELECT 1",
            "GROUPED requires at least two column references",
        ),
        (
            "CREATE TABLE t (id ENCODING) AS SELECT 1",
            "out-of-order CREATE TABLE clause",
        ),
        (
            "CREATE TABLE t (id ACCESSRANK 1.5) AS SELECT 1",
            "ACCESSRANK requires an integer",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) ON PRESERVE ROWS",
            "Expected COMMIT after ON",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DROP ROWS",
            "ON COMMIT requires DELETE or PRESERVE",
        ),
        (
            "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DELETE",
            "ON COMMIT requires ROWS",
        ),
        (
            "CREATE TABLE t AS AT EPOCH 1.5 SELECT 1",
            "AT EPOCH requires LATEST or an integer",
        ),
        (
            "CREATE TABLE t AS AT TIME now SELECT 1",
            "AT TIME requires a quoted timestamp",
        ),
        (
            "CREATE TABLE t AS AT SNAPSHOT 1 SELECT 1",
            "AT requires EPOCH or TIME",
        ),
        (
            "CREATE TABLE t (id BIGINT) KSAFE 1.5",
            "KSAFE requires an integer safety level",
        ),
        (
            "CREATE TABLE t (id BIGINT) ORDER BY",
            "ORDER BY requires a column name",
        ),
        (
            "CREATE TABLE t (id BIGINT) PARTITION BY",
            "PARTITION BY requires an expression",
        ),
        (
            "CREATE TABLE t (id BIGINT) PARTITION BY id GROUP BY",
            "Partition GROUP BY requires an expression",
        ),
        (
            "CREATE TABLE t (id BIGINT) INCLUDE SCHEMA",
            "Expected PRIVILEGES after INCLUDE or EXCLUDE",
        ),
    ],
)
def test_create_table_variants_reject_incompatible_clauses(sql: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_one(sql, read="vertica")


CREATE_TABLE_FAIL_CLOSED_NEGATIVES = [
    # CTAS column lists and physical design.
    "CREATE TABLE t () AS SELECT 1",
    "CREATE TABLE t (GROUPED(id)) AS SELECT 1",
    "CREATE TABLE t (id ENCODING) AS SELECT 1",
    "CREATE TABLE t (id ACCESSRANK 1.5) AS SELECT 1",
    "CREATE TABLE t AS SELECT 1 ENCODED BY",
    "CREATE TABLE t AS SELECT 1 ENCODED BY id",
    "CREATE TABLE t AS SELECT 1 ENCODED BY id ENCODING",
    "CREATE TABLE t AS SELECT 1 ENCODED BY id ACCESSRANK 1.5",
    # Temporary-table commit and quota clauses.
    "CREATE TEMPORARY TABLE t (id BIGINT) ON",
    "CREATE TEMPORARY TABLE t (id BIGINT) ON PRESERVE ROWS",
    "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT",
    "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DROP ROWS",
    "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DELETE",
    "CREATE TABLE t (id BIGINT) DISK_QUOTA 1",
    # Ordering, segmentation, partitioning, and inherited privileges.
    "CREATE TABLE t (id BIGINT) ORDER BY",
    "CREATE TABLE t (id BIGINT) ORDER BY id DESC",
    "CREATE TABLE t (id BIGINT) SEGMENTED HASH(id) ALL NODES",
    "CREATE TABLE t (id BIGINT) SEGMENTED BY HASH(id)",
    "CREATE TABLE t (id BIGINT) UNSEGMENTED ALL",
    "CREATE TABLE t (id BIGINT) PARTITION BY",
    "CREATE TABLE t (id BIGINT) PARTITION BY id GROUP BY",
    "CREATE TABLE t (id BIGINT) PARTITION BY id ACTIVEPARTITIONCOUNT 1.5",
    "CREATE TABLE t (id BIGINT) INCLUDE SCHEMA",
    # Front-door CREATE TABLE modifiers and scope/temporary prefixes.
    "CREATE GLOBAL TABLE t (id BIGINT)",
    "CREATE LOCAL TABLE t (id BIGINT)",
    "CREATE OR REPLACE TABLE t (id BIGINT)",
    "CREATE GLOBAL LOCAL TEMPORARY TABLE t (id BIGINT)",
    "CREATE LOCAL GLOBAL TEMPORARY TABLE t (id BIGINT)",
    "CREATE TEMPORARY TEMPORARY TABLE t (id BIGINT)",
    "CREATE GLOBAL GLOBAL TEMPORARY TABLE t (id BIGINT)",
    "CREATE LOCAL LOCAL TEMPORARY TABLE t (id BIGINT)",
    "CREATE GLOBAL TEMPORARY TEMPORARY TABLE t (id BIGINT)",
    "CREATE TEMPORARY GLOBAL TABLE t (id BIGINT)",
    "CREATE TEMPORARY LOCAL TABLE t (id BIGINT)",
    # Missing bodies and unexpected end of input.
    "CREATE TABLE",
    "CREATE TABLE t",
    "CREATE TABLE t AS",
    "CREATE TABLE t (id BIGINT",
    "CREATE TABLE t AS SELECT 1 ENCODED BY id ENCODING RLE,",
]


@pytest.mark.parametrize("sql", CREATE_TABLE_FAIL_CLOSED_NEGATIVES)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_create_table_malformed_forms_fail_closed_at_every_error_level(
    sql: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse_one(sql, read="vertica", error_level=error_level)


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE t (id BIGINT)",
        "CREATE TABLE t LIKE source",
        "CREATE TABLE t AS SELECT 1 AS id",
        "CREATE TEMPORARY TABLE t (id BIGINT) ON COMMIT DELETE ROWS",
        "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id",
        "CREATE LOCAL TEMPORARY TABLE t ON COMMIT PRESERVE ROWS AS SELECT 1 AS id",
    ],
)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_create_table_valid_forms_survive_fail_closed_transaction(
    sql: str, error_level: ErrorLevel
) -> None:
    expression = parse_one(sql, read="vertica", error_level=error_level)
    assert isinstance(expression, exp.Create)
    assert parse_one(expression.sql(dialect="vertica"), read="vertica") == expression


@pytest.mark.parametrize(
    "script",
    [
        "CREATE TABLE ok (id BIGINT); CREATE TABLE broken () AS SELECT 1; SELECT 2",
        "CREATE TABLE ok AS SELECT 1 AS id; CREATE TEMPORARY TABLE broken "
        "(id BIGINT) ON COMMIT; SELECT 2",
        "CREATE TABLE ok LIKE source; CREATE TABLE broken (id BIGINT; SELECT 2",
    ],
)
@pytest.mark.parametrize(
    "error_level",
    [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE],
)
def test_create_table_malformed_multi_statement_boundaries_are_atomic(
    script: str, error_level: ErrorLevel
) -> None:
    with pytest.raises(ParseError):
        parse(script, read="vertica", error_level=error_level)
