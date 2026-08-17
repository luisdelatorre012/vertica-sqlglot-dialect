"""Q05: embedded Vertica properties fail atomically in foreign dialects.

`sqlglot.generator.Generator.locate_properties` indexes `PROPERTIES_LOCATION`
with a plain `dict.__getitem__` before any per-node dispatch runs, so a
foreign dialect that has never heard of a Vertica-only `exp.Property`
subclass used to raise a raw `KeyError` once that property was actually
embedded in a real `exp.Properties` list, instead of the atomic
`UnsupportedError`/`ValueError` contract every other custom Vertica node
already gives (see `ARCHITECTURE.md`'s AST-policy section). This module pins
the fixed contract installed by `sqlglot_vertica.foreign_properties`: every
Vertica-only property, once embedded, raises
`ValueError("Unsupported expression type <Name>")` -- matching
`vexp.DropViews` -- at every `unsupported_level`, against every release-gate
foreign dialect, while canonical properties and non-Vertica `Property`
subclasses keep today's behavior unchanged.
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import pytest
from sqlglot import ErrorLevel, exp, parse_one
from sqlglot.errors import UnsupportedError

from sqlglot_vertica import expressions as vexp

FOREIGN_DIALECTS = ["postgres", "duckdb", "mysql", "sqlite"]
ERROR_LEVELS = [ErrorLevel.IMMEDIATE, ErrorLevel.RAISE, ErrorLevel.WARN, ErrorLevel.IGNORE]

CUSTOM_PROPERTY_TYPES = sorted(
    (
        expression_type
        for _, expression_type in inspect.getmembers(vexp, inspect.isclass)
        if expression_type.__module__ == vexp.__name__ and issubclass(expression_type, exp.Property)
    ),
    key=lambda expression_type: expression_type.__name__,
)

# ResourcePoolParameter is only ever embedded inside CreateResourcePool/
# AlterResourcePool (see tests/test_roles_resource_pools.py), custom exp.Create/
# exp.Alter roots that already fail atomically on their own unregistered class
# name before locate_properties ever runs. It deliberately has no
# PROPERTIES_LOCATION entry anywhere, native or foreign; embedding it in a
# generic exp.Create the way every other property here is exercised would not
# represent a real Vertica AST, so it is audited on its own below instead of
# through the generic sweep.
GENERIC_SWEEP_PROPERTY_TYPES = [
    property_type
    for property_type in CUSTOM_PROPERTY_TYPES
    if property_type is not vexp.ResourcePoolParameter
]


def test_custom_property_types_are_exhaustively_enumerated() -> None:
    """Freezes the audited set so a newly added `vexp` `Property` subclass is
    caught here -- and must join `GENERIC_SWEEP_PROPERTY_TYPES` or gain a
    documented exclusion like `ResourcePoolParameter`'s -- instead of silently
    reintroducing the foreign `KeyError` gap this module closes."""

    assert {expression_type.__name__ for expression_type in CUSTOM_PROPERTY_TYPES} == {
        "AtEpochProperty",
        "CtasDiskQuotaProperty",
        "CtasHintProperty",
        "CtasSegmentationProperty",
        "DefaultInheritedPrivilegesProperty",
        "DiskQuotaProperty",
        "EncodedByProperty",
        "InheritedPrivilegesProperty",
        "KsafeProperty",
        "LocalProperty",
        "NoProjectionProperty",
        "ResourcePoolParameter",
        "SchemaAuthorizationProperty",
        "TablePartitionProperty",
        "TableSegmentationProperty",
    }
    assert len(GENERIC_SWEEP_PROPERTY_TYPES) == 14


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("level", ERROR_LEVELS, ids=lambda level: level.name)
@pytest.mark.parametrize("property_type", GENERIC_SWEEP_PROPERTY_TYPES, ids=lambda t: t.__name__)
def test_every_vertica_property_fails_atomically_when_embedded(
    property_type: type[exp.Property], level: ErrorLevel, dialect: str
) -> None:
    """A future `Property` subclass is caught here the moment it is embedded
    and generated abroad, without waiting for a dedicated regression."""

    tree = exp.Create(
        this=exp.table_("t"),
        kind="TABLE",
        properties=exp.Properties(expressions=[property_type()]),
    )
    with pytest.raises(ValueError, match=f"Unsupported expression type {property_type.__name__}"):
        tree.sql(dialect=dialect, unsupported_level=level)


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("level", ERROR_LEVELS, ids=lambda level: level.name)
def test_resource_pool_parameter_is_never_reached_through_locate_properties(
    level: ErrorLevel, dialect: str
) -> None:
    """`ResourcePoolParameter`'s real container fails first, atomically, as an
    unregistered custom root, confirming it never needs -- and could not
    safely be given -- a `PROPERTIES_LOCATION` entry of its own."""

    expression = parse_one("CREATE RESOURCE POOL rp MAXMEMORYSIZE '1G'", read="vertica")
    assert isinstance(expression, vexp.CreateResourcePool)

    with pytest.raises(ValueError, match="Unsupported expression type CreateResourcePool"):
        expression.sql(dialect=dialect, unsupported_level=level)


EMBEDDED_CONTEXT_SQL = [
    (
        "definition_form_full_physical_design",
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
        "DISK_QUOTA '20G'",
    ),
    (
        "ctas_full_physical_design",
        "CREATE TABLE IF NOT EXISTS analytics.promotions "
        "EXCLUDE SCHEMA PRIVILEGES "
        "AS /*+ LABEL('promotion_ctas') */ AT EPOCH LATEST "
        "SELECT customer_state, customer_zip FROM customer_dimension "
        "ORDER BY customer_state "
        "ENCODED BY customer_state ENCODING RLE ACCESSRANK 1, "
        "customer_zip ACCESSRANK 2 "
        "SEGMENTED BY HASH(customer_state) ALL NODES "
        "DISK_QUOTA '5G'",
    ),
    (
        "global_temporary_table",
        "CREATE GLOBAL TEMPORARY TABLE session_stage (id BIGINT, payload VARCHAR) "
        "ON COMMIT PRESERVE ROWS NO PROJECTION "
        "INCLUDE PRIVILEGES DISK_QUOTA '1G'",
    ),
    (
        "local_temporary_table_as",
        "CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS id",
    ),
    (
        "schema_lifecycle",
        "CREATE SCHEMA IF NOT EXISTS tenant.analytics "
        "AUTHORIZATION data_owner "
        "DEFAULT INCLUDE SCHEMA PRIVILEGES "
        "DISK_QUOTA '20G'",
    ),
]


@pytest.mark.parametrize("dialect", FOREIGN_DIALECTS)
@pytest.mark.parametrize("level", ERROR_LEVELS, ids=lambda level: level.name)
@pytest.mark.parametrize(
    "sql",
    [sql for _, sql in EMBEDDED_CONTEXT_SQL],
    ids=[name for name, _ in EMBEDDED_CONTEXT_SQL],
)
def test_real_statements_with_embedded_properties_fail_atomically(
    sql: str, level: ErrorLevel, dialect: str
) -> None:
    """Definition-form, CTAS, temporary-table, and schema statements that mix
    several properties in one list still fail atomically -- on the first
    unsupported property `locate_properties` reaches -- instead of emitting a
    truncated `CREATE` missing some of its clauses.

    The first unsupported property is not always the Vertica-only one this
    task fixes: at `IMMEDIATE`, DuckDB/SQLite blanket-map most *canonical*
    properties to `Properties.Location.UNSUPPORTED` too, and `exp.Order`/
    `exp.GlobalProperty` precede the Vertica-only property in two of these
    fixtures, so `UnsupportedError` fires first there, pre-existing and
    unrelated to this task. `KeyError` is deliberately excluded: it must
    never reach a caller for a Vertica-embedding statement any more."""

    expression = parse_one(sql, read="vertica")
    with pytest.raises((ValueError, UnsupportedError)):
        expression.sql(dialect=dialect, unsupported_level=level)


def test_unrelated_property_subclass_keeps_the_original_keyerror() -> None:
    """The patch only special-cases classes this plugin defines: a
    hypothetical third-party `Property` subclass SQLGlot has never heard of
    keeps today's raw `KeyError`, proving foreign dialects' behavior for
    non-Vertica trees is unchanged."""

    class _ThirdPartyProperty(exp.Property):
        arg_types = {}  # noqa: RUF012

    tree = exp.Create(
        this=exp.table_("t"),
        kind="TABLE",
        properties=exp.Properties(expressions=[_ThirdPartyProperty()]),
    )
    with pytest.raises(KeyError):
        tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)


@pytest.mark.parametrize(
    ("level", "expect_raise"),
    [
        (ErrorLevel.RAISE, True),
        (ErrorLevel.WARN, False),
        (ErrorLevel.IGNORE, False),
    ],
)
def test_canonical_unsupported_property_keeps_warn_and_drop_semantics(
    level: ErrorLevel, expect_raise: bool
) -> None:
    """A canonical property PostgreSQL already maps to
    `Properties.Location.UNSUPPORTED` (`exp.TransientProperty`) keeps
    dropping-with-a-warning at `WARN`/`IGNORE` and raising only at `RAISE`;
    the patch only changes behavior for *missing* keys, never registered
    ones, so this pre-existing upstream contract is untouched."""

    tree = exp.Create(
        this=exp.table_("t"),
        kind="TABLE",
        properties=exp.Properties(expressions=[exp.TransientProperty()]),
    )
    if expect_raise:
        with pytest.raises(UnsupportedError, match="transientproperty"):
            tree.sql(dialect="postgres", unsupported_level=level)
    else:
        assert tree.sql(dialect="postgres", unsupported_level=level) == "CREATE TABLE t"


def test_vertica_native_generation_is_unaffected() -> None:
    """Vertica's own `PROPERTIES_LOCATION` is a separate dict built by a
    plain `{**PostgresGenerator.PROPERTIES_LOCATION, ...}` spread at class
    definition time (see `generator.py`); patching the four foreign
    generators' dicts in place must not touch it."""

    for _, sql in EMBEDDED_CONTEXT_SQL:
        expression = parse_one(sql, read="vertica")
        assert expression.sql(dialect="vertica") == sql


def test_global_property_foreign_behavior_is_unaffected() -> None:
    """Canonical `exp.GlobalProperty` is explicitly excluded from this task
    and already present (not missing) in every foreign dialect's dict, so
    `__missing__` never fires for it: PostgreSQL/MySQL still render it and
    DuckDB/SQLite still cleanly reject it, exactly as before this patch."""

    expression = parse_one("CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id", read="vertica")

    assert expression.sql(dialect="postgres") == "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id"
    assert expression.sql(dialect="mysql") == "CREATE GLOBAL TEMPORARY TABLE t AS SELECT 1 AS id"

    for dialect in ("duckdb", "sqlite"):
        with pytest.raises(UnsupportedError, match="globalproperty"):
            expression.sql(dialect=dialect, unsupported_level=ErrorLevel.RAISE)


def test_patch_survives_vertica_dialect_imported_before_foreign_generators() -> None:
    """Proves the registration mechanism reaches DuckDB's generator when the
    Vertica dialect is imported first, in a fresh interpreter untouched by
    this test session's own import history."""

    code = (
        "from sqlglot import ErrorLevel, parse_one; "
        "import sqlglot_vertica; "
        "tree = parse_one('CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS id', read='vertica'); "
        "sql = tree.sql(dialect='duckdb', unsupported_level=ErrorLevel.RAISE)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "ValueError: Unsupported expression type LocalProperty" in result.stderr


def test_patch_survives_foreign_generator_imported_before_vertica_dialect() -> None:
    """Proves the same registration mechanism reaches DuckDB's generator when
    something else imports it before the Vertica dialect ever loads, in a
    fresh interpreter untouched by this test session's own import history."""

    code = (
        "import sys; "
        "from sqlglot.generators.duckdb import DuckDBGenerator; "
        "assert 'sqlglot_vertica' not in sys.modules; "
        "from sqlglot import ErrorLevel, parse_one; "
        "import sqlglot_vertica; "
        "tree = parse_one('CREATE LOCAL TEMPORARY TABLE t AS SELECT 1 AS id', read='vertica'); "
        "sql = tree.sql(dialect='duckdb', unsupported_level=ErrorLevel.RAISE)"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "ValueError: Unsupported expression type LocalProperty" in result.stderr
