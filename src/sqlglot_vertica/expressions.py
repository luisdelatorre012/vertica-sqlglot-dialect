"""Stable Vertica-specific SQLGlot expression nodes.

Only syntax that cannot be represented faithfully by SQLGlot's canonical AST
belongs here. Published class names are part of serialized-tree compatibility.
"""

from __future__ import annotations

import typing as t

from sqlglot import exp


class SetLiteral(exp.Expression):
    """A directly constructed Vertica ``SET[...]`` value.

    This intentionally does not inherit :class:`sqlglot.exp.Array`: a Vertica
    SET has uniqueness semantics and must not silently transpile as either an
    array or a made-up ``SET_LITERAL`` function in another dialect.
    """

    arg_types: t.ClassVar = {"expressions": False}


class RowAlias(exp.Alias):
    """A ROW value alias with an explicit outer field-name list."""

    arg_types: t.ClassVar = {
        **exp.Alias.arg_types,
        "columns": True,
    }


class VerticaInterval(exp.Interval):
    """An interval literal with precision attached to the INTERVAL keyword."""

    arg_types: t.ClassVar = {
        **exp.Interval.arg_types,
        "precision": True,
    }


class StatementTimestamp(exp.Expression):
    """Statement-start ``TIMESTAMP`` returned by ``GETDATE`` and ``SYSDATE``."""

    arg_types: t.ClassVar = {}

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args:
            errors.append(
                f"The number of provided arguments ({len(args)}) is greater than "
                "the maximum number of supported arguments (0)"
            )
        return errors


class UtcStatementTimestamp(StatementTimestamp):
    """Statement-start ``TIMESTAMP`` in UTC returned by ``GETUTCDATE``."""

    arg_types: t.ClassVar = {}


class DirectedConstantHint(exp.Expression):
    """A constant expression carrying a Vertica directed-query annotation.

    SQLGlot normally stores a postfix ``/*+...*/`` as an ordinary comment.
    Making the directive and its optional pairing index children preserves its
    query-matching semantics through traversal, typing, and serialization.
    """

    arg_types: t.ClassVar = {
        "this": True,
        "directive": True,
        "index": False,
    }


class ListAgg(exp.Expression):
    """Vertica ``LISTAGG`` around a canonical aggregate child.

    ``this`` is an :class:`sqlglot.exp.GroupConcat`, which keeps aggregate
    discovery and operand traversal canonical while ensuring unsupported
    foreign generators fail instead of emitting a fictitious ``LIST_AGG``.
    """

    arg_types: t.ClassVar = {
        "this": True,
        "parameters": False,
    }


class UsingParameters(exp.Expression):
    """A function call followed by Vertica's ``USING PARAMETERS`` clause.

    ``this`` remains the canonical or Vertica-specific function node so
    aggregate discovery, lambda traversal, and optimizer inspection do not
    have to recover a function name from an opaque string.
    """

    arg_types: t.ClassVar = {
        "this": True,
        "parameters": True,
    }


class VerticaExplode(exp.Expression):
    """Vertica ``EXPLODE`` around a canonical :class:`exp.Explode` child."""

    arg_types: t.ClassVar = {"this": True}

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args is not None and not args:
            errors.append("Vertica EXPLODE requires at least one argument")
        return errors


class VerticaArrayLength(exp.Expression):
    """Vertica ``ARRAY_LENGTH`` around a canonical :class:`exp.ArraySize` child."""

    arg_types: t.ClassVar = {"this": True}

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args is not None and len(args) != 1:
            errors.append("Vertica ARRAY_LENGTH requires exactly one argument")
        return errors


class VerticaRegexpLike(exp.Expression, exp.Predicate):
    """Modifier-preserving wrapper around a canonical ``RegexpLike`` child."""

    arg_types: t.ClassVar = {
        "this": True,
        "modifiers": False,
    }

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args is not None and len(args) < 2:
            errors.append("Vertica REGEXP_LIKE requires at least two arguments")
        return errors


class VerticaInstr(exp.Expression):
    """Vertica ``INSTR`` around a canonical :class:`exp.StrPosition` child."""

    arg_types: t.ClassVar = {"this": True}

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args is not None and not 2 <= len(args) <= 4:
            errors.append("Vertica INSTR requires between two and four arguments")
        return errors


class StringUnit(exp.Expression):
    """A function call with Vertica's ``USING CHARACTERS|OCTETS`` unit."""

    arg_types: t.ClassVar = {
        "this": True,
        "unit": True,
        "name": False,
    }


class VerticaToChar(exp.Expression):
    """Vertica's one-argument ``TO_CHAR`` around an inspectable call child."""

    arg_types: t.ClassVar = {"this": True}

    def error_messages(self, args: t.Sequence[object] | None = None) -> list[str]:
        errors = super().error_messages(args)
        if args is not None and len(args) != 1:
            errors.append("Vertica TO_CHAR requires one or two arguments")
        return errors


class VerticaWindow(exp.Window):
    """A window carrying Vertica's non-expression partition mode."""

    arg_types: t.ClassVar = {
        **exp.Window.arg_types,
        "partition_mode": True,
    }


class TableOptimizerHint(exp.Hint):
    """A Vertica optimizer hint attached to a table reference."""


class WithHint(exp.With):
    """A ``WITH`` clause carrying a Vertica optimizer hint."""

    arg_types: t.ClassVar = {
        **exp.With.arg_types,
        "hint": True,
    }


class MaterializedWithMarker(exp.QueryOption):
    """Internal optimizer barrier for a materialized Vertica WITH clause.

    The marker is stored in each marked CTE query's ``options`` list. SQLGlot
    deliberately does not merge SELECTs with query options, and its subquery
    elimination rule preserves the CTE query subtree. Vertica generation hides
    the option itself and recovers the clause-level hint from ``this``.
    """

    arg_types: t.ClassVar = {"this": True}


class SaveQuery(exp.Expression):
    """Save one input query for a subsequent custom directed query."""

    arg_types: t.ClassVar = {"this": True}


class GetDirectedQuery(exp.Expression):
    """Look up the directed query mapped to an input query."""

    arg_types: t.ClassVar = {"this": True}


class CreateDirectedQuery(exp.Expression):
    """Create an optimizer-generated or custom Vertica directed query."""

    arg_types: t.ClassVar = {
        "this": True,
        "mode": True,
        "expression": True,
        "comment": False,
        "optimizer_version": False,
        "plan_date": False,
    }


class DirectedQueryAction(exp.Expression):
    """Activate, deactivate, or drop directed queries by one typed target."""

    arg_types: t.ClassVar = {
        "action": True,
        "this": False,
        "expression": False,
        "where": False,
    }


class Explain(exp.Describe):
    """Vertica ``EXPLAIN`` with structured options and optimizer hint."""

    arg_types: t.ClassVar = {
        **exp.Describe.arg_types,
        "hint": False,
        "options": False,
    }


class VerticaMerge(exp.Merge):
    """Vertica ``MERGE`` with a statement-level optimizer hint."""

    arg_types: t.ClassVar = {
        **exp.Merge.arg_types,
        "hint": False,
    }


class UpdateDefaultRelation(exp.Expression):
    """Vertica's ``DEFAULT`` relation in an ``UPDATE ... FROM`` join.

    ``DEFAULT`` is a grammar marker rather than a catalog table. Keeping it
    out of :class:`exp.Table` prevents table discovery and lineage tools from
    reporting a fictitious table named ``DEFAULT``.
    """

    arg_types: t.ClassVar = {"joins": True}


class VerticaCopy(exp.Copy):
    """Vertica's bulk loader with structured targets, sources, and options."""

    arg_types: t.ClassVar = {
        "this": True,
        "hint": False,
        "expressions": False,
        "column_options": False,
        "source": True,
        "format": False,
        "params": False,
        "no_commit": False,
    }


class CopyColumn(exp.Expression):
    """A COPY input column, optional transform, and per-column parameters."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
        "params": False,
    }


class CopyStdin(exp.Expression):
    """A local or server STDIN COPY source."""

    arg_types: t.ClassVar = {"local": False, "compression": False}


class CopyFiles(exp.Expression):
    """One or more server-side or client-local COPY files."""

    arg_types: t.ClassVar = {
        "expressions": True,
        "local": False,
        "partition_by": False,
    }


class CopyFile(exp.Expression):
    """A single COPY path, node selection, and compression setting."""

    arg_types: t.ClassVar = {"this": True, "on": False, "compression": False}


class CopyNodeSelection(exp.Expression):
    """The node or node set on which a COPY file is available."""

    arg_types: t.ClassVar = {
        "kind": True,
        "this": False,
        "expressions": False,
    }


class CopyFromVertica(exp.Expression):
    """A table source in another connected Vertica database or namespace."""

    arg_types: t.ClassVar = {"this": True, "expressions": False}


class CopyUDL(exp.Expression):
    """A user-defined SOURCE/FILTER/PARSER load pipeline."""

    arg_types: t.ClassVar = {"this": True, "filters": False, "parser": False}


class CopyLoadFunction(exp.Expression):
    """A named UDL function with key/value arguments."""

    arg_types: t.ClassVar = {"this": True, "expressions": False}


class CopyFormat(exp.Expression):
    """A native, fixed-width, ORC, or Parquet COPY source format."""

    arg_types: t.ClassVar = {"this": True, "expressions": False}


class CopyOutputTarget(exp.Expression):
    """An exceptions or rejected-data path and optional destination node."""

    arg_types: t.ClassVar = {"this": True, "node": False}


class ExternalCopyDefinition(exp.Expression):
    """A targetless COPY body stored by a regular Vertica external table.

    The child nodes intentionally match :class:`VerticaCopy`, but a separate
    root prevents a catalog definition from masquerading as an executable COPY
    with a missing target table.
    """

    arg_types: t.ClassVar = {
        "expressions": False,
        "column_options": False,
        "source": True,
        "format": False,
        "params": False,
        "no_commit": False,
    }


class CreateExternalTable(exp.Create):
    """A regular ``CREATE EXTERNAL TABLE ... AS COPY`` statement."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "expression": True,
    }


class FlexibleCopyDefinition(ExternalCopyDefinition):
    """The narrowed COPY body stored by a flexible external table."""

    arg_types: t.ClassVar = {**ExternalCopyDefinition.arg_types}


class CreateFlexibleExternalTable(exp.Create):
    """A ``CREATE FLEXIBLE EXTERNAL TABLE ... AS COPY`` statement."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "expression": True,
    }


class IcebergColumnType(exp.Expression):
    """A length or collection-bound override read against Iceberg metadata."""

    arg_types: t.ClassVar = {
        "this": True,
        "kind": True,
    }


class IcebergExternalTableSpec(exp.Expression):
    """Location, catalog, authentication, and type overrides for Iceberg."""

    arg_types: t.ClassVar = {
        "location": True,
        "glue_db": False,
        "glue_table": False,
        "hms_db": False,
        "hms_table": False,
        "rest_auth": False,
        "column_types": False,
    }


class CreateIcebergExternalTable(exp.Create):
    """A metadata-backed ``CREATE EXTERNAL TABLE ... STORED BY ICEBERG``."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "expression": True,
    }


class ExternalProcedureParameter(exp.Expression):
    """An external-procedure argument with an optional descriptive name."""

    arg_types: t.ClassVar = {
        "this": False,
        "kind": True,
    }


class ExternalProcedureSignature(exp.UserDefinedFunction):
    """The overload-resolving name and typed arguments of a procedure."""

    arg_types: t.ClassVar = {
        "this": True,
        "expressions": False,
    }


class CreateExternalProcedure(exp.Create):
    """An external executable registered as a Vertica procedure."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "executable": True,
        "os_user": True,
    }


class DropExternalProcedure(exp.Drop):
    """Drop an external procedure by its typed, optionally named signature."""

    arg_types: t.ClassVar = {
        **exp.Drop.arg_types,
        "this": True,
    }


class UDxFactorySpec(exp.Expression):
    """The catalog factory and execution mode of a bodyless Vertica UDx."""

    arg_types: t.ClassVar = {
        "language": False,
        "factory": True,
        "library": True,
        "fenced": False,
    }


class CreateUserDefinedExtension(exp.Create):
    """Register a library-backed scalar, analytic, aggregate, or load UDx."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "expression": True,
    }


class DropUserDefinedExtension(exp.Drop):
    """Drop one UDx by its explicit overload-resolving signature."""

    arg_types: t.ClassVar = {
        **exp.Drop.arg_types,
        "this": True,
    }


class CreateLibrary(exp.Create):
    """Load a native, Java, Python, or R library into the Vertica catalog."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "path": True,
        "depends": False,
        "language": False,
    }


class DropLibrary(exp.Drop):
    """Drop one catalog library and optionally its dependent UDxs."""

    arg_types: t.ClassVar = {
        **exp.Drop.arg_types,
        "this": True,
    }


class CommentConstraintTarget(exp.Expression):
    """A named table constraint and the table that owns it."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
    }


class CommentOn(exp.Comment):
    """Add, replace, or remove a comment on a Vertica catalog object."""

    arg_types: t.ClassVar = {
        **exp.Comment.arg_types,
        "this": True,
        "kind": True,
        "expression": True,
    }


class ProjectionColumn(exp.Expression):
    """A column declaration in a Vertica projection definition."""

    arg_types: t.ClassVar = {
        "this": True,
        "encoding": False,
        "access_rank": False,
    }


class GroupedProjectionColumns(exp.Expression):
    """Projection columns that Vertica stores as a grouped unit."""

    arg_types: t.ClassVar = {"expressions": True}


class ProjectionSegmentation(exp.Expression):
    """The physical distribution clause of a Vertica projection."""

    arg_types: t.ClassVar = {
        "this": False,
        "segmented": True,
        "all_nodes": False,
        "nodes": False,
        "offset": False,
    }


class AccessRankColumnConstraint(exp.Expression, exp.ColumnConstraintKind):
    """Physical access priority assigned to a table column."""

    arg_types: t.ClassVar = {"this": True}


class TableSegmentationProperty(exp.Property):
    """Segmentation design for a table's automatically created projections."""

    arg_types: t.ClassVar = {"this": True}


class KsafeProperty(exp.Property):
    """K-safety level for automatically created table projections."""

    arg_types: t.ClassVar = {"this": False}


class TablePartitionProperty(exp.PartitionedByProperty):
    """Vertica table partitioning, optional grouping, and active count."""

    arg_types: t.ClassVar = {
        "this": True,
        "group": False,
        "active_partition_count": False,
    }


class InheritedPrivilegesProperty(exp.Property):
    """Whether a table inherits privileges granted on its schema."""

    arg_types: t.ClassVar = {"include": True, "schema": False}


class DiskQuotaProperty(exp.Property):
    """Storage quota assigned to a table."""

    arg_types: t.ClassVar = {"this": True}


class LocalProperty(exp.Property):
    """LOCAL visibility for a temporary table definition."""

    arg_types: t.ClassVar = {}


class NoProjectionProperty(exp.Property):
    """Suppress automatic projection creation for a temporary table."""

    arg_types: t.ClassVar = {}


class CtasHintProperty(exp.Property):
    """Optimizer hint placed immediately after the AS keyword in CTAS."""

    arg_types: t.ClassVar = {"this": True}


class AtEpochProperty(exp.Property):
    """Historical snapshot qualifier placed before a CTAS query."""

    arg_types: t.ClassVar = {"this": True, "kind": True}


class EncodedByProperty(exp.Property):
    """Post-query CTAS column encoding and access-rank declarations."""

    arg_types: t.ClassVar = {"expressions": True}


class CtasSegmentationProperty(TableSegmentationProperty):
    """Post-query segmentation design for a persistent CTAS statement."""


class CtasDiskQuotaProperty(DiskQuotaProperty):
    """Trailing disk quota for CTAS, after all query design clauses."""


class SchemaAuthorizationProperty(exp.Property):
    """Owner assigned by a Vertica ``CREATE SCHEMA`` statement."""

    arg_types: t.ClassVar = {"this": True}


class DefaultInheritedPrivilegesProperty(InheritedPrivilegesProperty):
    """Default privilege inheritance policy for new objects in a schema."""


class SequenceSetSchemaAction(exp.Expression):
    """Move a named sequence to another schema."""

    arg_types: t.ClassVar = {"this": True}


class SequenceOwnerToAction(exp.Expression):
    """Transfer ownership of a named sequence."""

    arg_types: t.ClassVar = {"this": True}


class AlterTablePartition(exp.Alter):
    """Replace table partition metadata and optionally reorganize existing data."""

    arg_types: t.ClassVar = {
        **exp.Alter.arg_types,
        "actions": False,
        "partition": True,
        "reorganize": False,
    }


class ReorganizeTable(exp.Alter):
    """Apply a table's existing partition scheme to stored data."""


class DropRoles(exp.Drop):
    """A comma-delimited, multi-role ``DROP ROLE`` statement.

    SQLGlot 30.13's canonical ``Drop.expressions`` generator renders secondary
    targets in parentheses.  A distinct root prevents that malformed spelling
    from leaking into foreign dialects while keeping the ordinary single-role
    form canonical.
    """

    arg_types: t.ClassVar = {**exp.Drop.arg_types}


class UserAction(exp.Expression):
    """A typed account-state or password-expiry USER lifecycle action."""

    arg_types: t.ClassVar = {"this": True}


class UserParameter(exp.Expression):
    """One ordered, non-secret CREATE/ALTER USER account parameter."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
        "subcluster": False,
        "scope": False,
    }


class UserSearchPath(exp.Expression):
    """An explicit ordered schema path or the database DEFAULT sentinel."""

    arg_types: t.ClassVar = {
        "expressions": False,
        "default": False,
    }


class UserDefaultRoles(exp.Expression):
    """One of the finite ALTER USER default-role selection modes."""

    arg_types: t.ClassVar = {
        "expressions": False,
        "mode": True,
    }


class UserConfigurationParameter(exp.Expression):
    """One USER-level configuration name and optional reviewed SET value."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
    }


class UserConfiguration(exp.Expression):
    """A value-bearing SET or value-free CLEAR USER configuration action."""

    arg_types: t.ClassVar = {
        "expressions": True,
        "set": True,
    }


class CreateUser(exp.Create):
    """Create one Vertica user without retaining credential material."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "action": False,
        "parameters": False,
    }


class AlterUser(exp.Alter):
    """Apply ordered, bounded, non-secret changes to a Vertica user."""


class DropUsers(exp.Drop):
    """Drop one or more Vertica users with optional dependency cascading."""


class ProfileParameter(exp.Expression):
    """One named password-policy setting inside a PROFILE LIMIT clause."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
    }


class ProfileLimit(exp.Expression):
    """An ordered, nonempty set of PROFILE policy parameters."""

    arg_types: t.ClassVar = {"expressions": True}


class CreateProfile(exp.Create):
    """Create a Vertica password-policy profile."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "limit": True,
    }


class AlterProfile(exp.Alter):
    """Alter PROFILE limits or rename one profile."""


class DropProfiles(exp.Drop):
    """Drop one or more profiles with optional user reassignment."""


class ProfileStatement(exp.Expression):
    """Execute one traversable query or DML statement with profiling enabled."""

    arg_types: t.ClassVar = {"this": True}


class ResourcePoolSubcluster(exp.Expression):
    """A named or current-subcluster resource-pool selector."""

    arg_types: t.ClassVar = {
        "this": False,
        "current": False,
    }


class ResourcePoolKeyword(exp.Expression):
    """A typed resource-pool keyword or sentinel value.

    ``quoted`` distinguishes QUEUETIMEOUT's documented ``'NONE'`` sentinel
    from the bare ``NONE`` accepted by other parameters.
    """

    arg_types: t.ClassVar = {
        "this": True,
        "quoted": False,
    }


class ResourcePoolParameter(exp.Property):
    """One ordered resource-pool parameter and its typed value."""

    arg_types: t.ClassVar = {**exp.Property.arg_types}


class CreateResourcePool(exp.Create):
    """Create a global or subcluster-specific Vertica resource pool."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "subcluster": False,
    }


class AlterResourcePool(exp.Alter):
    """Change one or more ordered settings on a Vertica resource pool."""

    arg_types: t.ClassVar = {
        **exp.Alter.arg_types,
        "subcluster": False,
    }


class DropResourcePool(exp.Drop):
    """Drop one global or subcluster-specific Vertica resource pool."""

    arg_types: t.ClassVar = {
        **exp.Drop.arg_types,
        "subcluster": False,
    }


class LoadBalanceGroupSpec(exp.Expression):
    """The typed members, filter, and policy of a load balance group."""

    arg_types: t.ClassVar = {
        "this": True,
        "expressions": True,
        "filter": False,
        "policy": False,
    }


class LoadBalanceGroupAction(exp.Expression):
    """A typed non-rename action in ``ALTER LOAD BALANCE GROUP``."""

    arg_types: t.ClassVar = {
        "this": True,
        "member_kind": False,
        "expression": False,
        "expressions": False,
    }


class CreateLoadBalanceGroup(exp.Create):
    """Create one address-, fault-group-, or subcluster-backed group."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "spec": True,
    }


class AlterLoadBalanceGroup(exp.Alter):
    """Apply exactly one typed change to a load balance group."""


class DropLoadBalanceGroup(exp.Drop):
    """Drop one load balance group with optional dependency cascading."""


class NetworkAddressSpec(exp.Expression):
    """The node endpoint, optional port, and optional state of a network address."""

    arg_types: t.ClassVar = {
        "this": True,
        "node": True,
        "port": False,
        "state": False,
    }


class NetworkAddressAction(exp.Expression):
    """A typed non-rename action in ``ALTER NETWORK ADDRESS``."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
        "port": False,
    }


class CreateNetworkAddress(exp.Create):
    """Create one named connection-load-balancing endpoint on a node."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "spec": True,
    }


class AlterNetworkAddress(exp.Alter):
    """Apply exactly one typed change to a network address."""


class DropNetworkAddress(exp.Drop):
    """Drop one network address with optional dependency cascading."""


class RoutingRuleSpec(exp.Expression):
    """The source and destinations of one classic or workload routing rule."""

    arg_types: t.ClassVar = {
        "mode": True,
        "this": True,
        "expressions": True,
        "priority": False,
    }


class RoutingRuleTarget(exp.Expression):
    """A routing-rule name or a ``FOR WORKLOAD`` target."""

    arg_types: t.ClassVar = {
        "this": True,
        "workload": False,
    }


class RoutingRuleAction(exp.Expression):
    """A typed non-rename action in ``ALTER ROUTING RULE``."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
        "expressions": False,
    }


class CreateRoutingRule(exp.Create):
    """Create a classic CIDR or workload-to-subcluster routing rule."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "this": False,
        "route": True,
    }


class AlterRoutingRule(exp.Alter):
    """Apply exactly one typed change to a routing rule."""


class DropRoutingRule(exp.Drop):
    """Drop one named or workload routing rule."""


class SetSessionRouting(exp.Set):
    """Set the current session's workload or resource pool exactly."""


class ShowWorkload(exp.Show):
    """Show the current or available session workloads."""

    arg_types: t.ClassVar = {
        **exp.Show.arg_types,
        "available": False,
    }


class ExtendedGrantPrivilege(exp.GrantPrivilege):
    """Vertica ``ALL [PRIVILEGES] EXTEND`` privilege semantics."""

    arg_types: t.ClassVar = {
        **exp.GrantPrivilege.arg_types,
        "privileges": False,
        "extend": True,
    }


class VerticaPrivilegeTarget(exp.Expression):
    """One structured target group in an object GRANT or REVOKE.

    ``expressions`` stores named objects, schemas, a location path, or routine
    signatures according to ``kind``. Qualifiers are explicit arguments so
    consumers never need to recover them from an opaque identifier string.
    """

    arg_types: t.ClassVar = {
        "kind": False,
        "expressions": True,
        "all_in_schema": False,
        "subcluster": False,
        "current_subcluster": False,
        "node": False,
    }


class RoutineSignature(exp.Expression):
    """A procedure or UDx name and its overload-resolving argument types."""

    arg_types: t.ClassVar = {
        "this": True,
        "expressions": False,
    }


class RoleGrant(exp.Grant):
    """Assign one or more roles, optionally with ``ADMIN OPTION``."""

    arg_types: t.ClassVar = {
        "roles": True,
        "principals": True,
        "admin_option": False,
    }


class RoleRevoke(exp.Revoke):
    """Revoke roles or only their administration authority."""

    arg_types: t.ClassVar = {
        "roles": True,
        "principals": True,
        "admin_option": False,
        "cascade": False,
    }


class AuthenticationGrant(exp.Grant):
    """Associate a Vertica authentication method with principals."""

    arg_types: t.ClassVar = {
        "this": True,
        "principals": True,
    }


class AuthenticationRevoke(exp.Revoke):
    """Remove an authentication-method association from principals."""

    arg_types: t.ClassVar = {
        "this": True,
        "principals": True,
    }


class AuthenticationAccess(exp.Expression):
    """The LOCAL or HOST connection matcher of an authentication record."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
        "tls": False,
    }


class CreateAuthentication(exp.Create):
    """Create one non-secret Vertica authentication record."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "method": True,
        "access": True,
        "enforce_mfa": False,
        "fallthrough": False,
    }


class AuthenticationAction(exp.Expression):
    """One non-access, non-rename ``ALTER AUTHENTICATION`` action."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": False,
    }


class AuthenticationParameter(exp.Expression):
    """One reviewed non-secret ``ALTER AUTHENTICATION SET`` parameter."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
    }


class AuthenticationSet(exp.Expression):
    """An ordered nonempty list of reviewed authentication parameters."""

    arg_types: t.ClassVar = {
        "expressions": True,
    }


class AlterAuthentication(exp.Alter):
    """Apply exactly one reviewed change to an authentication record."""


class DropAuthentication(exp.Drop):
    """Drop one Vertica authentication record."""


class CreateProjection(exp.Create):
    """`CREATE PROJECTION` with lineage-relevant query and design clauses."""

    arg_types: t.ClassVar = {
        **exp.Create.arg_types,
        "columns": False,
        "order": False,
        "segmentation": False,
        "ksafe": False,
        "exists": False,
        "replace": False,
    }


class TimeseriesSelect(exp.Select):
    """A SELECT whose Vertica ``TIMESERIES`` clause must never be dropped."""

    arg_types: t.ClassVar = {
        **exp.Select.arg_types,
        "timeseries": True,
    }


class TimeseriesSlice(exp.Expression):
    """Reference to the synthetic timestamp column created by TIMESERIES."""

    arg_types: t.ClassVar = {"this": True}

    @property
    def output_name(self) -> str:
        return self.name


class Timeseries(exp.Expression):
    """Vertica's relational gap-filling `TIMESERIES` query clause."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
        "partition_by": False,
        "order": True,
    }


class Interpolate(exp.Expression, exp.Binary, exp.Predicate):
    """An event-series join interpolation predicate."""

    arg_types: t.ClassVar = {
        "this": True,
        "expression": True,
        "direction": True,
    }


class PartitionedLimit(exp.Limit):
    """Vertica's partitioned top-k `LIMIT n OVER (...)` clause."""

    arg_types: t.ClassVar = {
        **exp.Limit.arg_types,
        "partition_by": False,
        "order": True,
    }


class MatchDefinition(exp.Expression):
    """A named event predicate in a Vertica MATCH clause."""

    arg_types: t.ClassVar = {"this": True, "expression": True}


class Match(exp.Expression):
    """Vertica event-series pattern matching clause."""

    arg_types: t.ClassVar = {
        "partition_by": False,
        "order": True,
        "definitions": True,
        "pattern_name": True,
        "pattern": True,
        "rows_match": False,
    }
