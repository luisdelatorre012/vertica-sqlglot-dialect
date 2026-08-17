"""Fail-atomic ``PROPERTIES_LOCATION`` registration for foreign generators.

``sqlglot.generator.Generator.locate_properties``/``properties_sql`` index
``PROPERTIES_LOCATION`` with a plain ``dict.__getitem__`` before any per-node
dispatch runs, so a foreign dialect that has never heard of a Vertica-only
``exp.Property`` subclass raises a raw ``KeyError`` instead of the atomic
failure every other custom Vertica node gives (see ``ARCHITECTURE.md``'s AST
policy section). This module gives PostgreSQL, DuckDB, MySQL, and SQLite's
generators a ``PROPERTIES_LOCATION`` whose lookup raises the same
``ValueError("Unsupported expression type <Name>")`` SQLGlot's own dispatch
fallback already raises for an unregistered custom root such as
``vexp.DropViews``, for Vertica-only property classes specifically, while any
other missing key keeps the original ``KeyError`` so non-Vertica trees are
unaffected.
"""

from __future__ import annotations

import inspect
import typing as t

from sqlglot import exp

from sqlglot_vertica import expressions as vexp


def _vertica_property_classes() -> frozenset[type[exp.Property]]:
    return frozenset(
        obj
        for _, obj in inspect.getmembers(vexp, inspect.isclass)
        if obj.__module__ == vexp.__name__ and issubclass(obj, exp.Property)
    )


_VERTICA_PROPERTY_CLASSES = _vertica_property_classes()


class _FailAtomicPropertiesLocation(dict[type[exp.Expression], exp.PropertiesLocation]):
    """A ``PROPERTIES_LOCATION`` that fails like an unregistered custom root.

    Every already-registered key keeps ordinary ``dict`` behavior; only a
    lookup miss is special-cased, and only for classes this plugin defines.
    """

    __slots__ = ()

    def __missing__(self, key: type[exp.Expression]) -> t.NoReturn:
        if key in _VERTICA_PROPERTY_CLASSES:
            raise ValueError(f"Unsupported expression type {key.__name__}")
        raise KeyError(key)


def patch_foreign_properties_location() -> None:
    """Make embedding a Vertica-only property foreign-atomic, everywhere.

    Imports the four target generator modules directly, so the patch reaches
    the same, single, canonical class object no matter whether the foreign
    dialect or the Vertica dialect is imported first: SQLGlot lazily imports
    dialect submodules on first attribute access
    (``sqlglot/dialects/__init__.py``'s module ``__getattr__``), but a direct
    ``from sqlglot.generators.<x> import <X>Generator`` import here forces
    that submodule to load before this function inspects it, and Python's
    import cache guarantees only one such class object ever exists per
    process regardless of import order.
    """

    from sqlglot.generators.duckdb import DuckDBGenerator
    from sqlglot.generators.mysql import MySQLGenerator
    from sqlglot.generators.postgres import PostgresGenerator
    from sqlglot.generators.sqlite import SQLiteGenerator

    for foreign_generator in (PostgresGenerator, DuckDBGenerator, MySQLGenerator, SQLiteGenerator):
        foreign_generator.PROPERTIES_LOCATION = _FailAtomicPropertiesLocation(
            foreign_generator.PROPERTIES_LOCATION
        )
