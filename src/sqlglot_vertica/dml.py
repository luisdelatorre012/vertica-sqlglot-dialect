"""Pure structural validation for Vertica data-modification statements."""

from __future__ import annotations

from sqlglot import exp

from sqlglot_vertica import expressions as vexp


def _hint_errors(expression: exp.Expr, statement: str) -> list[str]:
    hint = expression.args.get("hint")
    if hint is None:
        return []
    if not isinstance(hint, exp.Hint) or len(hint.expressions) != 1:
        return [f"Vertica {statement} supports exactly one LABEL hint"]

    directive = hint.expressions[0]
    if directive.name.upper() != "LABEL" or len(directive.expressions) != 1:
        return [f"Vertica {statement} supports only LABEL with one argument"]
    return []


def _alias_has_columns(expression: exp.Expr) -> bool:
    alias = expression.args.get("alias")
    return isinstance(alias, exp.TableAlias) and bool(alias.args.get("columns"))


def _named_table(expression: exp.Expr | None) -> bool:
    return isinstance(expression, exp.Table) and isinstance(expression.this, exp.Identifier)


def _unqualified_column(expression: exp.Expr | None) -> bool:
    return isinstance(expression, exp.Column) and not any(
        expression.args.get(part) for part in ("catalog", "db", "table")
    )


def _assignment_errors(expressions: list[exp.Expr], statement: str) -> list[str]:
    if not expressions:
        return [f"Vertica {statement} requires at least one assignment"]

    errors: list[str] = []
    for assignment in expressions:
        if not isinstance(assignment, exp.EQ):
            errors.append(f"Vertica {statement} assignments require column = expression")
        elif not _unqualified_column(assignment.this):
            errors.append(f"Vertica {statement} assignment targets must be unqualified columns")
    return errors


def _insert_target(expression: exp.Insert) -> tuple[exp.Table | None, list[exp.Expr]]:
    target = expression.this
    if isinstance(target, exp.Schema):
        return (target.this if isinstance(target.this, exp.Table) else None, target.expressions)
    return (target if isinstance(target, exp.Table) else None, [])


def _query_source(expression: exp.Expr) -> bool:
    if isinstance(expression, exp.Values):
        return False
    if isinstance(expression, exp.Subquery):
        return isinstance(expression.this, exp.Query) and not isinstance(
            expression.this, exp.Values
        )
    return isinstance(expression, exp.Query)


def insert_errors(expression: exp.Insert) -> list[str]:
    """Return deterministic, catalog-independent INSERT validation failures."""

    errors = _hint_errors(expression, "INSERT")
    target, columns = _insert_target(expression)
    if target is None or not _named_table(target):
        errors.append("Vertica INSERT requires a table target")
    elif target.args.get("alias"):
        errors.append("Vertica INSERT target tables do not support aliases")
    elif target.args.get("hints") or target.args.get("joins"):
        errors.append("Vertica INSERT target tables do not support hints or joins")

    if isinstance(expression.this, exp.Schema) and not columns:
        errors.append("Vertica INSERT target column lists cannot be empty")
    elif columns and not all(isinstance(column, exp.Identifier) for column in columns):
        errors.append("Vertica INSERT target columns must be unqualified names")

    forbidden = {
        "alternative": "OR alternatives",
        "by_name": "BY NAME",
        "conflict": "ON CONFLICT",
        "exists": "IF EXISTS",
        "ignore": "IGNORE",
        "is_function": "FUNCTION targets",
        "overwrite": "OVERWRITE",
        "partition": "PARTITION clauses",
        "returning": "RETURNING",
        "settings": "SETTINGS",
        "source": "TABLE sources",
        "stored": "STORED clauses",
        "where": "REPLACE WHERE",
        "with_": "a leading WITH clause",
    }
    for key, description in forbidden.items():
        if expression.args.get(key):
            errors.append(f"Vertica INSERT does not support {description}")

    default_values = bool(expression.args.get("default"))
    source = expression.args.get("expression")
    if default_values:
        if columns:
            errors.append("Vertica INSERT DEFAULT VALUES cannot include a target column list")
        if source is not None:
            errors.append("Vertica INSERT requires exactly one source form")
    elif source is None:
        errors.append("Vertica INSERT requires DEFAULT VALUES, VALUES, or a query source")
    elif isinstance(source, exp.Values):
        if source.args.get("alias"):
            errors.append("Vertica INSERT VALUES does not support an alias")
        if not source.expressions:
            errors.append("Vertica INSERT VALUES requires at least one row")
        for row in source.expressions:
            if not isinstance(row, exp.Tuple) or not row.expressions:
                errors.append("Vertica INSERT VALUES rows cannot be empty")
                continue
            if any(isinstance(node, exp.Query) for node in row.walk()):
                errors.append("Vertica INSERT VALUES does not support subqueries")
    elif not isinstance(source, exp.Expr) or not _query_source(source):
        errors.append("Vertica INSERT source must be VALUES or a query")

    return errors


def _merge_action_errors(when: exp.When) -> list[str]:
    matched = when.args.get("matched") is True
    action = when.args.get("then")
    errors: list[str] = []

    if when.args.get("source"):
        errors.append("Vertica MERGE does not support MATCHED BY SOURCE or TARGET")

    if matched:
        if not isinstance(action, exp.Update):
            return [*errors, "Vertica WHEN MATCHED requires UPDATE"]
        errors.extend(_assignment_errors(action.expressions, "MERGE UPDATE SET"))
        for key in ("from_", "hint", "limit", "options", "order", "returning", "this", "with_"):
            if action.args.get(key):
                errors.append(f"Vertica MERGE UPDATE does not support {key.upper()}")
    else:
        if not isinstance(action, exp.Insert):
            return [*errors, "Vertica WHEN NOT MATCHED requires INSERT"]

        columns = action.this
        if columns is not None:
            if not isinstance(columns, exp.Tuple) or not columns.expressions:
                errors.append("Vertica MERGE INSERT column lists cannot be empty")
            elif not all(_unqualified_column(column) for column in columns.expressions):
                errors.append("Vertica MERGE INSERT target columns must be unqualified")

        values = action.args.get("expression")
        if not isinstance(values, exp.Tuple) or not values.expressions:
            errors.append("Vertica MERGE INSERT requires a nonempty VALUES tuple")

        for key in (
            "alternative",
            "by_name",
            "conflict",
            "default",
            "exists",
            "hint",
            "ignore",
            "is_function",
            "overwrite",
            "partition",
            "returning",
            "settings",
            "source",
            "stored",
            "with_",
        ):
            if action.args.get(key):
                errors.append(f"Vertica MERGE INSERT does not support {key.upper()}")

    if (
        when.args.get("condition") is not None
        and isinstance(action, (exp.Insert, exp.Update))
        and action.args.get("where") is not None
    ):
        errors.append("Vertica MERGE branches cannot use both AND and trailing WHERE filters")
    return errors


def merge_errors(expression: exp.Merge) -> list[str]:
    """Return deterministic, catalog-independent MERGE validation failures."""

    errors = _hint_errors(expression, "MERGE")
    target = expression.this
    if not _named_table(target):
        errors.append("Vertica MERGE requires a table target")
    elif _alias_has_columns(target):
        errors.append("Vertica MERGE target aliases cannot include column aliases")
    elif target.args.get("hints") or target.args.get("joins"):
        errors.append("Vertica MERGE target tables do not support hints or joins")

    source = expression.args.get("using")
    if not isinstance(source, (exp.Table, exp.Subquery)):
        errors.append("Vertica MERGE USING requires a table or subquery source")
    elif isinstance(source, exp.Subquery):
        if not isinstance(source.this, exp.Query):
            errors.append("Vertica MERGE subquery sources require a query")
        if not source.alias:
            errors.append("Vertica MERGE subquery sources require an alias")
        elif _alias_has_columns(source):
            errors.append("Vertica MERGE source aliases cannot include column aliases")
    elif not _named_table(source):
        errors.append("Vertica MERGE USING requires a named table source")
    elif _alias_has_columns(source):
        errors.append("Vertica MERGE source aliases cannot include column aliases")
    elif source.args.get("hints") or source.args.get("joins"):
        errors.append("Vertica MERGE source tables do not support hints or joins")

    if not isinstance(expression.args.get("on"), exp.Expr):
        errors.append("Vertica MERGE requires ON")
    if expression.args.get("using_cond"):
        errors.append("Vertica MERGE does not support a second USING condition")
    if expression.args.get("returning"):
        errors.append("Vertica MERGE does not support RETURNING")
    if expression.args.get("with_"):
        errors.append("Vertica MERGE does not support a leading WITH clause")

    whens = expression.args.get("whens")
    branches = whens.expressions if isinstance(whens, exp.Whens) else []
    if not branches:
        errors.append("Vertica MERGE requires at least one matching clause")

    matched_count = 0
    not_matched_count = 0
    for branch in branches:
        if not isinstance(branch, exp.When):
            errors.append("Vertica MERGE matching clauses require WHEN nodes")
            continue
        if branch.args.get("matched") is True:
            matched_count += 1
        elif branch.args.get("matched") is False:
            not_matched_count += 1
        else:
            errors.append("Vertica MERGE WHEN requires MATCHED or NOT MATCHED")
        errors.extend(_merge_action_errors(branch))

    if matched_count > 1:
        errors.append("Vertica MERGE supports at most one WHEN MATCHED clause")
    if not_matched_count > 1:
        errors.append("Vertica MERGE supports at most one WHEN NOT MATCHED clause")
    return errors


def _is_default_table(table: exp.Table) -> bool:
    identifier = table.this
    return (
        isinstance(identifier, exp.Identifier)
        and not identifier.args.get("quoted")
        and identifier.name.upper() == "DEFAULT"
        and not table.args.get("db")
        and not table.args.get("catalog")
    )


def update_errors(expression: exp.Update) -> list[str]:
    """Return deterministic, catalog-independent UPDATE validation failures."""

    errors: list[str] = []
    if not _named_table(expression.this):
        errors.append("Vertica UPDATE requires a table target")
    errors.extend(_assignment_errors(expression.expressions, "UPDATE SET"))

    for assignment in expression.expressions:
        if (
            isinstance(assignment, exp.EQ)
            and assignment.expression is not None
            and any(isinstance(node, exp.Query) for node in assignment.expression.walk())
        ):
            errors.append("Vertica UPDATE SET expressions do not support subqueries")

    for key, description in {
        "limit": "LIMIT",
        "options": "OPTION",
        "order": "ORDER BY",
        "returning": "RETURNING",
        "with_": "a leading WITH clause",
    }.items():
        if expression.args.get(key):
            errors.append(f"Vertica UPDATE does not support {description}")

    from_ = expression.args.get("from_")
    if isinstance(from_, exp.From):
        relation = from_.this
        if isinstance(relation, vexp.UpdateDefaultRelation):
            joins = relation.args.get("joins") or []
            if not joins:
                errors.append("Vertica UPDATE FROM DEFAULT requires a JOIN")
            elif not all(isinstance(join, exp.Join) for join in joins):
                errors.append("Vertica UPDATE FROM DEFAULT requires JOIN nodes")
            elif not any(
                joins[0].args.get(key) for key in ("kind", "method", "on", "side", "using")
            ):
                errors.append("Vertica UPDATE FROM DEFAULT requires explicit JOIN syntax")
        elif any(_is_default_table(table) for table in from_.find_all(exp.Table)):
            errors.append("Vertica UPDATE DEFAULT must be the first FROM relation")

        if isinstance(relation, vexp.UpdateDefaultRelation) and any(
            _is_default_table(table) for table in from_.find_all(exp.Table)
        ):
            errors.append("Vertica UPDATE FROM can contain DEFAULT only once")
    return errors


def delete_errors(expression: exp.Delete) -> list[str]:
    """Return deterministic, catalog-independent DELETE validation failures."""

    errors = _hint_errors(expression, "DELETE")
    target = expression.this
    if not _named_table(target):
        errors.append("Vertica DELETE requires a table target")
    elif target.args.get("alias") or target.args.get("joins"):
        errors.append("Vertica DELETE targets do not support aliases or joins")
    elif target.args.get("hints"):
        errors.append("Vertica DELETE targets do not support table hints")

    for key, description in {
        "cluster": "ON CLUSTER",
        "limit": "LIMIT",
        "order": "ORDER BY",
        "returning": "RETURNING",
        "tables": "multiple target tables",
        "using": "USING",
        "with_": "a leading WITH clause",
    }.items():
        if expression.args.get(key):
            errors.append(f"Vertica DELETE does not support {description}")
    return errors


def truncate_errors(expression: exp.TruncateTable) -> list[str]:
    """Return deterministic, catalog-independent TRUNCATE validation failures."""

    errors: list[str] = []
    if len(expression.expressions) != 1:
        errors.append("Vertica TRUNCATE TABLE requires exactly one table")
    elif not _named_table(expression.expressions[0]):
        errors.append("Vertica TRUNCATE TABLE requires a table target")
    elif expression.expressions[0].args.get("alias"):
        errors.append("Vertica TRUNCATE TABLE does not support target aliases")
    elif expression.expressions[0].args.get("hints") or expression.expressions[0].args.get("joins"):
        errors.append("Vertica TRUNCATE TABLE does not support target hints or joins")

    for key, description in {
        "cluster": "ON CLUSTER",
        "exists": "IF EXISTS",
        "identity": "identity options",
        "is_database": "DATABASE targets",
        "only": "ONLY",
        "option": "CASCADE or RESTRICT",
        "partition": "PARTITION clauses",
    }.items():
        if expression.args.get(key):
            errors.append(f"Vertica TRUNCATE TABLE does not support {description}")
    return errors
