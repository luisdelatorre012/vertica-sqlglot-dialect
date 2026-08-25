"""Source-defined contracts for the optimizer hints modeled by this dialect."""

from __future__ import annotations

import typing as t

from sqlglot import exp

HintOwner = t.Literal["select", "explain", "with", "table", "join", "ctas", "dml", "copy"]

MODELED_HINT_NAMES = {
    "ALLNODES",
    "DISTRIB",
    "ENABLE_WITH_CLAUSE_MATERIALIZATION",
    "JTYPE",
    "LABEL",
    "PROJS",
    "SKIP_PROJS",
    "SYN_JOIN",
    "SYNTACTIC_JOIN",
    "VERBATIM",
}

OWNER_HINT_NAMES: dict[HintOwner, set[str]] = {
    "select": {"LABEL", "SYN_JOIN", "SYNTACTIC_JOIN", "VERBATIM"},
    "explain": {"ALLNODES"},
    "with": {"ENABLE_WITH_CLAUSE_MATERIALIZATION"},
    "table": {"PROJS", "SKIP_PROJS"},
    "join": {"DISTRIB", "JTYPE"},
    "ctas": {"LABEL"},
    "dml": {"LABEL"},
    "copy": {"LABEL"},
}

_ARGUMENT_FREE = {
    "ALLNODES",
    "ENABLE_WITH_CLAUSE_MATERIALIZATION",
    "SYN_JOIN",
    "SYNTACTIC_JOIN",
    "VERBATIM",
}


def _simple_value(expression: exp.Expr) -> str | None:
    if isinstance(expression, exp.Literal) and expression.is_string:
        return expression.this if isinstance(expression.this, str) else None
    if isinstance(expression, (exp.Identifier, exp.Var)):
        return expression.name
    if isinstance(expression, exp.Column) and not any(
        expression.args.get(part) for part in ("catalog", "db", "table")
    ):
        identifier = expression.this
        if isinstance(identifier, exp.Identifier) and not identifier.args.get("quoted"):
            return identifier.name
    return None


def _projection_name(expression: exp.Expr) -> bool:
    if isinstance(expression, exp.Literal) and expression.is_string:
        try:
            parts = expression.this.split(".")
            expression.this.encode("utf-8")
        except (UnicodeEncodeError, AttributeError):
            return False
        return 1 <= len(parts) <= 3 and all(parts)

    if not isinstance(expression, exp.Column):
        return False
    if expression.args.get("catalog") is not None:
        return False
    if set(expression.args) - {"this", "table", "db"}:
        return False
    identifiers = [expression.args.get(part) for part in ("db", "table", "this")]
    present = [identifier for identifier in identifiers if identifier is not None]
    if not present or any(not isinstance(identifier, exp.Identifier) for identifier in present):
        return False
    if expression.args.get("db") is not None and expression.args.get("table") is None:
        return False
    try:
        return all(
            bool(identifier.name) and bool(identifier.name.encode("utf-8"))
            for identifier in present
        )
    except UnicodeEncodeError:
        return False


def _label_value(expression: exp.Expr) -> bool:
    value = _simple_value(expression)
    if not isinstance(value, str) or not value:
        return False
    try:
        return len(value.encode("utf-8")) <= 128
    except UnicodeEncodeError:
        return False


def _directive_error(directive: exp.Expr, owner: HintOwner) -> str | None:
    name = directive.name.upper()
    if name not in MODELED_HINT_NAMES:
        return None
    if name not in OWNER_HINT_NAMES[owner]:
        return f"Vertica {name} optimizer hint is not valid at the {owner.upper()} owner"

    if name in _ARGUMENT_FREE:
        if not isinstance(directive, exp.Var) or set(directive.args) != {"this"}:
            return f"Vertica {name} optimizer hint does not accept arguments"
        return None

    if not isinstance(directive, exp.Anonymous) or set(directive.args) != {
        "this",
        "expressions",
    }:
        return f"Vertica {name} optimizer hint requires arguments"
    arguments = directive.args.get("expressions")
    if not isinstance(arguments, list):
        return f"Vertica {name} optimizer hint requires an argument list"

    if name == "JTYPE":
        values = [_simple_value(argument) for argument in arguments]
        if len(values) != 1 or values[0] is None or values[0].upper() not in {"H", "M", "FM"}:
            return "Vertica JTYPE requires exactly one of H, M, or FM"
    elif name == "DISTRIB":
        values = [_simple_value(argument) for argument in arguments]
        if (
            len(values) != 2
            or any(value is None for value in values)
            or any(value.upper() not in {"L", "R", "B", "F", "A"} for value in values if value)
        ):
            return "Vertica DISTRIB requires exactly two values from L, R, B, F, or A"
    elif name in {"PROJS", "SKIP_PROJS"}:
        if not arguments or any(not _projection_name(argument) for argument in arguments):
            return f"Vertica {name} requires at least one one-, two-, or three-part projection name"
    elif name == "LABEL":
        if len(arguments) != 1 or not _label_value(arguments[0]):
            return "Vertica LABEL requires one valid label string of at most 128 UTF-8 octets"
    return None


def optimizer_hint_error(
    hint: exp.Hint | None,
    owner: HintOwner,
    *,
    require_modeled_only: bool = False,
) -> str | None:
    """Return the first deterministic owner/domain error for a structured hint."""

    if not isinstance(hint, exp.Hint):
        return f"Vertica {owner.upper()} optimizer hint requires a typed Hint"
    directives = hint.args.get("expressions")
    if not isinstance(directives, list) or not directives:
        return f"Vertica {owner.upper()} optimizer hint requires at least one directive"
    for directive in directives:
        if not isinstance(directive, (exp.Var, exp.Anonymous)) or not directive.name:
            return f"Vertica {owner.upper()} optimizer hint requires structured directives"
        name = directive.name.upper()
        if require_modeled_only and name not in OWNER_HINT_NAMES[owner]:
            return f"Vertica {owner.upper()} optimizer hint does not support {name}"
        error = _directive_error(directive, owner)
        if error:
            return error
    return None


def canonicalize_optimizer_hint(hint: exp.Hint) -> None:
    """Normalize modeled directive aliases and finite enum values in place."""

    for directive in hint.expressions:
        if not isinstance(directive, (exp.Var, exp.Anonymous)):
            continue
        name = directive.name.upper()
        directive.set("this", "SYNTACTIC_JOIN" if name == "SYN_JOIN" else name)
        if name not in {"DISTRIB", "JTYPE"}:
            continue
        values = []
        for argument in directive.expressions:
            value = _simple_value(argument)
            values.append(exp.var(value.upper()) if value is not None else argument)
        directive.set("expressions", values)
