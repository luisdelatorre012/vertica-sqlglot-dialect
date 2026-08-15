"""Contextual Vertica keyword and identifier collision regressions."""

from __future__ import annotations

import pytest

from tests.helpers import assert_roundtrip


@pytest.mark.parametrize(
    "identifier",
    [
        "define",
        "pattern",
        "ksafe",
        "segmented",
        "unsegmented",
        "timeseries",
        "match",
    ],
)
def test_clause_keyword_is_legal_as_column_and_table_identifier(identifier: str) -> None:
    assert_roundtrip(f"SELECT {identifier} FROM keywords")
    assert_roundtrip(f"SELECT * FROM {identifier}")


def test_clause_keywords_are_legal_as_explicit_aliases() -> None:
    assert_roundtrip("SELECT 1 AS timeseries, 2 AS match, 3 AS define FROM source AS pattern")


def test_contextual_query_clauses_still_terminate_implicit_table_aliases() -> None:
    assert_roundtrip("SELECT * FROM ticks TIMESERIES slice_time AS '1 minute' OVER (ORDER BY ts)")
    assert_roundtrip(
        "SELECT * FROM events MATCH ("
        "ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A) ROWS MATCH FIRST EVENT)"
    )
