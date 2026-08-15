"""Document syntax accepted here but rejected by Vertica semantic analysis.

These cases require query-shape, type, catalog, or server-extension knowledge.
Keeping the corpus executable prevents accidental fallback to opaque Commands
without pretending that the syntax parser is a Vertica server validator.
"""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t TIMESERIES s AS '1 month' OVER (ORDER BY ts)",
        "SELECT x, AVG(y) FROM t TIMESERIES s AS '1 minute' OVER (ORDER BY ts) GROUP BY x",
        "SELECT * FROM t WHERE a.ts INTERPOLATE PREVIOUS VALUE b.ts",
        "SELECT * FROM a JOIN b ON a.ts INTERPOLATE PREVIOUS VALUE b.ts OR a.x = b.x",
        "SELECT DISTINCT * FROM events MATCH (ORDER BY ts DEFINE A AS TRUE PATTERN p AS (A))",
        "SELECT * FROM events MATCH (ORDER BY ts DEFINE A AS EXISTS(SELECT 1) PATTERN p AS (A))",
    ],
)
def test_server_semantic_negative_corpus_remains_structured(sql: str) -> None:
    expression = parse_one(sql, read="vertica")
    assert not isinstance(expression, exp.Command)
