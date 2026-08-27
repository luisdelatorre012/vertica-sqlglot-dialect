"""Packaging and dialect discovery regressions."""

from __future__ import annotations

import subprocess
import sys

from sqlglot import Dialect, parse_one

from sqlglot_vertica import Vertica


def test_entry_point_discovery() -> None:
    assert isinstance(Dialect.get_or_raise("vertica"), Vertica)
    assert parse_one("SELECT 1", read="vertica").sql(dialect="vertica") == "SELECT 1"


def test_entry_point_discovery_in_fresh_interpreter() -> None:
    """Exercise package metadata before the dialect can self-register on import."""

    code = (
        "import sys; "
        "assert 'sqlglot_vertica' not in sys.modules; "
        "from sqlglot import Dialect, parse_one; "
        "dialect = Dialect.get_or_raise('vertica'); "
        "assert dialect.__class__.__module__ == 'sqlglot_vertica.dialect'; "
        "assert parse_one('SELECT 1', read='vertica').sql(dialect='vertica') == 'SELECT 1'"
    )
    subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )


def test_postgres_interop_registration_after_generator_cache() -> None:
    """Loading Vertica invalidates a PostgreSQL dispatch table built first."""

    code = (
        "from sqlglot import parse_one; "
        "assert parse_one('SELECT 1', read='postgres').sql(dialect='postgres') == 'SELECT 1'; "
        "query = \"SELECT LISTAGG(a USING PARAMETERS separator=' | ') FROM t GROUP BY b\"; "
        "expression = parse_one(query, read='vertica'); "
        "assert expression.sql(dialect='postgres') == "
        "\"SELECT STRING_AGG(a, ' | ') FROM t GROUP BY b\""
    )
    subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )


def test_direct_dialect_class() -> None:
    expression = parse_one("SELECT 1", read=Vertica)
    assert expression.sql(dialect=Vertica) == "SELECT 1"
