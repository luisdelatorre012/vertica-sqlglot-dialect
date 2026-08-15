"""Internal token-comment provenance used by the Vertica parser."""

from __future__ import annotations


class DirectedPostfixComment(str):
    """A directed annotation scanned after a lexical value terminator."""


class MisplacedDirectedComment(str):
    """A directed annotation scanned before a complete value expression."""
