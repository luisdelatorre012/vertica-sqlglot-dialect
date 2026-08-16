"""SQL generation for the Vertica dialect."""

from __future__ import annotations

import re
import typing as t

from sqlglot import TokenType, exp
from sqlglot.dialects.dialect import rename_func
from sqlglot.generator import Generator
from sqlglot.generators.postgres import PostgresGenerator
from sqlglot.helper import csv

from sqlglot_vertica import dml as vdml
from sqlglot_vertica import expressions as vexp


class VerticaGenerator(PostgresGenerator):
    """Generate canonical Vertica SQL."""

    QUERY_HINTS = True
    TABLE_HINTS = True
    # Vertica places structured join hints immediately after JOIN, unlike the
    # generic SQLGlot string hint that is rendered before JOIN.
    JOIN_HINTS = False
    LIKE_PROPERTY_INSIDE_SCHEMA = False
    IGNORE_NULLS_IN_FUNC = True
    NVL2_SUPPORTED = True
    SUPPORTS_MERGE_WHERE = True
    SUPPORTS_MEDIAN = True

    TYPE_MAPPING: t.ClassVar = {
        **PostgresGenerator.TYPE_MAPPING,
        exp.DType.BINARY: "BINARY",
        exp.DType.BLOB: "LONG VARBINARY",
        exp.DType.LONGBLOB: "LONG VARBINARY",
        exp.DType.LONGTEXT: "LONG VARCHAR",
        exp.DType.ROWVERSION: "VARBINARY",
        exp.DType.TEXT: "LONG VARCHAR",
        exp.DType.VARBINARY: "VARBINARY",
    }

    PROPERTIES_LOCATION: t.ClassVar = {
        **PostgresGenerator.PROPERTIES_LOCATION,
        exp.OnCommitProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.AtEpochProperty: exp.Properties.Location.POST_ALIAS,
        vexp.CtasDiskQuotaProperty: exp.Properties.Location.POST_EXPRESSION,
        vexp.CtasHintProperty: exp.Properties.Location.POST_ALIAS,
        vexp.CtasSegmentationProperty: exp.Properties.Location.POST_EXPRESSION,
        vexp.DefaultInheritedPrivilegesProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.DiskQuotaProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.EncodedByProperty: exp.Properties.Location.POST_EXPRESSION,
        vexp.InheritedPrivilegesProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.KsafeProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.LocalProperty: exp.Properties.Location.POST_CREATE,
        vexp.NoProjectionProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.SchemaAuthorizationProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.TablePartitionProperty: exp.Properties.Location.POST_SCHEMA,
        vexp.TableSegmentationProperty: exp.Properties.Location.POST_SCHEMA,
    }

    TABLE_PROPERTY_ORDER: t.ClassVar = {
        exp.GlobalProperty: 10,
        vexp.LocalProperty: 10,
        exp.TemporaryProperty: 20,
        exp.LikeProperty: 30,
        exp.OnCommitProperty: 40,
        vexp.NoProjectionProperty: 50,
        exp.Order: 60,
        vexp.TableSegmentationProperty: 70,
        vexp.KsafeProperty: 80,
        vexp.TablePartitionProperty: 90,
        vexp.InheritedPrivilegesProperty: 100,
        vexp.DiskQuotaProperty: 110,
        vexp.CtasHintProperty: 120,
        vexp.AtEpochProperty: 130,
        vexp.EncodedByProperty: 140,
        vexp.CtasSegmentationProperty: 150,
        vexp.CtasDiskQuotaProperty: 160,
    }

    SCHEMA_PROPERTY_ORDER: t.ClassVar = {
        vexp.SchemaAuthorizationProperty: 10,
        vexp.DefaultInheritedPrivilegesProperty: 20,
        vexp.DiskQuotaProperty: 30,
    }

    EXTERNAL_PROCEDURE_TYPES: t.ClassVar = {
        "BIGINT",
        "BOOLEAN",
        "DECIMAL",
        "DOUBLE PRECISION",
        "FLOAT",
        "FLOAT8",
        "INT",
        "INT8",
        "INTEGER",
        "MONEY",
        "NUMBER",
        "NUMERIC",
        "REAL",
        "SMALLINT",
        "TINYINT",
        "VARCHAR",
    }
    USER_DEFINED_EXTENSION_LANGUAGES: t.ClassVar = {
        "AGGREGATE FUNCTION": {"C++"},
        "ANALYTIC FUNCTION": {"C++", "JAVA"},
        "TRANSFORM FUNCTION": {"C++", "JAVA", "PYTHON", "R"},
        "FUNCTION": {"C++", "JAVA", "PYTHON", "R"},
        "FILTER": {"C++", "JAVA", "PYTHON"},
        "PARSER": {"C++", "JAVA", "PYTHON"},
        "SOURCE": {"C++", "JAVA"},
        "LIBRARY": {"C++", "JAVA", "PYTHON", "R"},
    }
    USER_DEFINED_EXTENSION_LANGUAGE_NAMES: t.ClassVar = {
        "C++": "C++",
        "JAVA": "Java",
        "PYTHON": "Python",
        "R": "R",
    }
    USER_DEFINED_LOAD_FUNCTION_KINDS: t.ClassVar = {"FILTER", "PARSER", "SOURCE"}
    EXTERNAL_COPY_PARAMETERS: t.ClassVar = {
        "ABORT ON ERROR",
        "DELIMITER",
        "ENCLOSED BY",
        "ENFORCELENGTH",
        "ERROR TOLERANCE",
        "ESCAPE AS",
        "NO ESCAPE",
        "EXCEPTIONS",
        "FILTER",
        "NULL AS",
        "PARSER",
        "RECORD TERMINATOR",
        "REJECTED DATA",
        "REJECTMAX",
        "SKIP",
        "SKIP BYTES",
        "TRAILING NULLCOLS",
        "TRIM",
    }
    FLEXIBLE_COPY_PARAMETERS: t.ClassVar = {
        "PARSER",
        "ABORT ON ERROR",
        "DELIMITER",
        "ENCLOSED BY",
        "ENFORCELENGTH",
        "ESCAPE AS",
        "NO ESCAPE",
        "EXCEPTIONS",
        "NULL AS",
        "RECORD TERMINATOR",
        "REJECTED DATA",
        "REJECTMAX",
        "SKIP",
        "SKIP BYTES",
        "TRAILING NULLCOLS",
        "TRIM",
    }
    ICEBERG_SIZED_TYPES: t.ClassVar = {
        exp.DType.VARCHAR,
        exp.DType.LONGTEXT,
        exp.DType.VARBINARY,
        exp.DType.LONGBLOB,
    }
    RESOURCE_POOL_PARAMETERS: t.ClassVar = {
        "CASCADE TO",
        "CPUAFFINITYMODE",
        "CPUAFFINITYSET",
        "EXECUTIONPARALLELISM",
        "MAXCONCURRENCY",
        "MAXMEMORYSIZE",
        "MAXQUERYMEMORYSIZE",
        "MEMORYSIZE",
        "PLANNEDCONCURRENCY",
        "PRIORITY",
        "QUEUETIMEOUT",
        "RUNTIMECAP",
        "RUNTIMEPRIORITY",
        "RUNTIMEPRIORITYTHRESHOLD",
        "SINGLEINITIATOR",
    }
    LOAD_BALANCE_GROUP_MEMBER_KINDS: t.ClassVar = {
        "ADDRESS",
        "FAULT GROUP",
        "SUBCLUSTER",
    }
    LOAD_BALANCE_GROUP_POLICIES: t.ClassVar = {"NONE", "RANDOM", "ROUNDROBIN"}
    RESOURCE_POOL_EXTENDED_PRIORITY_NAMES: t.ClassVar = {"RECOVERY", "SYSQUERY", "TM"}
    COPY_FORMAT_PARAMETERS: t.ClassVar = {
        "ORC": {
            "HIVE_PARTITION_COLS",
            "ALLOW_NO_MATCH",
            "DO_SOFT_SCHEMA_MATCH_BY_NAME",
            "REJECT_ON_MATERIALIZED_TYPE_ERROR",
        },
        "PARQUET": {
            "HIVE_PARTITION_COLS",
            "ALLOW_NO_MATCH",
            "ALLOW_LONG_VARBINARY_MATCH_COMPLEX_TYPE",
            "DO_SOFT_SCHEMA_MATCH_BY_NAME",
            "REJECT_ON_MATERIALIZED_TYPE_ERROR",
        },
    }
    PROFILE_PARAMETERS: t.ClassVar[tuple[str, ...]] = (
        "PASSWORD_LIFE_TIME",
        "PASSWORD_MIN_LIFE_TIME",
        "PASSWORD_GRACE_TIME",
        "FAILED_LOGIN_ATTEMPTS",
        "PASSWORD_LOCK_TIME",
        "PASSWORD_REUSE_MAX",
        "PASSWORD_REUSE_TIME",
        "PASSWORD_MAX_LENGTH",
        "PASSWORD_MIN_LENGTH",
        "PASSWORD_MIN_LETTERS",
        "PASSWORD_MIN_UPPERCASE_LETTERS",
        "PASSWORD_MIN_LOWERCASE_LETTERS",
        "PASSWORD_MIN_DIGITS",
        "PASSWORD_MIN_SYMBOLS",
        "PASSWORD_MIN_CHAR_CHANGE",
    )
    PROFILE_POSITIVE_PARAMETERS: t.ClassVar[set[str]] = {
        "FAILED_LOGIN_ATTEMPTS",
        "PASSWORD_GRACE_TIME",
        "PASSWORD_LIFE_TIME",
        "PASSWORD_LOCK_TIME",
        "PASSWORD_REUSE_MAX",
        "PASSWORD_REUSE_TIME",
    }
    PROFILE_CHARACTER_MINIMUM_PARAMETERS: t.ClassVar[set[str]] = {
        "PASSWORD_MIN_CHAR_CHANGE",
        "PASSWORD_MIN_DIGITS",
        "PASSWORD_MIN_LENGTH",
        "PASSWORD_MIN_LETTERS",
        "PASSWORD_MIN_LOWERCASE_LETTERS",
        "PASSWORD_MIN_SYMBOLS",
        "PASSWORD_MIN_UPPERCASE_LETTERS",
    }

    TRANSFORMS: t.ClassVar = {
        **PostgresGenerator.TRANSFORMS,
        exp.Abs: lambda self, expression: f"@ {self.sql(expression, 'this')}",
        exp.AddMonths: rename_func("ADD_MONTHS"),
        exp.CurrentTimestamp: lambda self, expression: self.currenttimestamp_sql(expression),
        exp.DateAdd: lambda self, expression: self.vertica_date_delta_sql(
            expression, "TIMESTAMPADD"
        ),
        exp.DateDiff: lambda self, expression: self.vertica_date_delta_sql(expression, "DATEDIFF"),
        exp.DayOfMonth: rename_func("DAYOFMONTH"),
        exp.DayOfWeek: rename_func("DAYOFWEEK"),
        exp.DayOfWeekIso: rename_func("DAYOFWEEK_ISO"),
        exp.DayOfYear: rename_func("DAYOFYEAR"),
        exp.EncodeColumnConstraint: lambda self, expression: (
            f"ENCODING {self.sql(expression, 'this')}"
        ),
        exp.Factorial: lambda self, expression: f"{self.sql(expression, 'this')}!",
        exp.GroupConcat: rename_func("LISTAGG"),
        exp.ArrayFilter: lambda self, expression: self.vertica_array_filter_sql(expression),
        exp.Hex: lambda self, expression: self.func("TO_HEX", expression.this),
        exp.IntDiv: lambda self, expression: self.binary(expression, "//"),
        exp.LowerHex: lambda self, expression: self.func("TO_HEX", expression.this),
        exp.Merge: lambda self, expression: self.merge_sql(expression),
        exp.SHA: rename_func("SHA1"),
        exp.Struct: lambda self, expression: self.vertica_struct_sql(expression),
        exp.Stuff: rename_func("INSERT"),
        exp.TimeSlice: lambda self, expression: self.timeslice_sql(expression),
        exp.TsOrDsAdd: lambda self, expression: self.vertica_date_delta_sql(
            expression, "TIMESTAMPADD"
        ),
        exp.TsOrDsDiff: lambda self, expression: self.vertica_date_delta_sql(
            expression, "DATEDIFF"
        ),
        exp.UtcTimestamp: rename_func("GETUTCDATE"),
        vexp.AccessRankColumnConstraint: lambda self, expression: (
            f"ACCESSRANK {self.sql(expression, 'this')}"
        ),
        vexp.AtEpochProperty: lambda self, expression: self.atepochproperty_sql(expression),
        vexp.AuthenticationGrant: lambda self, expression: self.authenticationgrant_sql(expression),
        vexp.AuthenticationRevoke: lambda self, expression: self.authenticationrevoke_sql(
            expression
        ),
        vexp.AlterLoadBalanceGroup: lambda self, expression: self.alterloadbalancegroup_sql(
            expression
        ),
        vexp.AlterNetworkAddress: lambda self, expression: self.alternetworkaddress_sql(expression),
        vexp.AlterProfile: lambda self, expression: self.alterprofile_sql(expression),
        vexp.AlterResourcePool: lambda self, expression: self.alterresourcepool_sql(expression),
        vexp.AlterRoutingRule: lambda self, expression: self.alterroutingrule_sql(expression),
        vexp.AlterTablePartition: lambda self, expression: self.altertablepartition_sql(expression),
        vexp.AlterUser: lambda self, expression: self.alteruser_sql(expression),
        vexp.CreateDirectedQuery: lambda self, expression: self.createdirectedquery_sql(expression),
        vexp.CreateExternalProcedure: lambda self, expression: self.createexternalprocedure_sql(
            expression
        ),
        vexp.CreateExternalTable: lambda self, expression: self.createexternaltable_sql(expression),
        vexp.CreateFlexibleExternalTable: lambda self, expression: (
            self.createflexibleexternaltable_sql(expression)
        ),
        vexp.CreateIcebergExternalTable: lambda self, expression: (
            self.createicebergexternaltable_sql(expression)
        ),
        vexp.CreateLibrary: lambda self, expression: self.createlibrary_sql(expression),
        vexp.CreateLoadBalanceGroup: lambda self, expression: self.createloadbalancegroup_sql(
            expression
        ),
        vexp.CreateNetworkAddress: lambda self, expression: self.createnetworkaddress_sql(
            expression
        ),
        vexp.CreateProjection: lambda self, expression: self.createprojection_sql(expression),
        vexp.CreateProfile: lambda self, expression: self.createprofile_sql(expression),
        vexp.CreateResourcePool: lambda self, expression: self.createresourcepool_sql(expression),
        vexp.CreateRoutingRule: lambda self, expression: self.createroutingrule_sql(expression),
        vexp.CreateUserDefinedExtension: lambda self, expression: (
            self.createuserdefinedextension_sql(expression)
        ),
        vexp.CreateUser: lambda self, expression: self.createuser_sql(expression),
        vexp.CopyColumn: lambda self, expression: self.copycolumn_sql(expression),
        vexp.CopyFile: lambda self, expression: self.copyfile_sql(expression),
        vexp.CopyFiles: lambda self, expression: self.copyfiles_sql(expression),
        vexp.CopyFormat: lambda self, expression: self.copyformat_sql(expression),
        vexp.CopyFromVertica: lambda self, expression: self.copyfromvertica_sql(expression),
        vexp.CopyLoadFunction: lambda self, expression: self.copyloadfunction_sql(expression),
        vexp.CopyNodeSelection: lambda self, expression: self.copynodeselection_sql(expression),
        vexp.CopyOutputTarget: lambda self, expression: self.copyoutputtarget_sql(expression),
        vexp.CopyStdin: lambda self, expression: self.copystdin_sql(expression),
        vexp.CopyUDL: lambda self, expression: self.copyudl_sql(expression),
        vexp.CtasDiskQuotaProperty: lambda self, expression: (
            f"DISK_QUOTA {self.sql(expression, 'this')}"
        ),
        vexp.CtasHintProperty: lambda self, expression: self.sql(expression, "this").lstrip(),
        vexp.CtasSegmentationProperty: lambda self, expression: self.sql(expression, "this"),
        vexp.DefaultInheritedPrivilegesProperty: lambda self, expression: (
            f"DEFAULT {self.inheritedprivilegesproperty_sql(expression)}"
        ),
        vexp.DirectedConstantHint: lambda self, expression: self.directedconstanthint_sql(
            expression
        ),
        vexp.DirectedQueryAction: lambda self, expression: self.directedqueryaction_sql(expression),
        vexp.DiskQuotaProperty: lambda self, expression: (
            f"DISK_QUOTA {self.sql(expression, 'this')}"
        ),
        vexp.DropExternalProcedure: lambda self, expression: self.dropexternalprocedure_sql(
            expression
        ),
        vexp.DropLibrary: lambda self, expression: self.droplibrary_sql(expression),
        vexp.DropLoadBalanceGroup: lambda self, expression: self.droploadbalancegroup_sql(
            expression
        ),
        vexp.DropNetworkAddress: lambda self, expression: self.dropnetworkaddress_sql(expression),
        vexp.DropProfiles: lambda self, expression: self.dropprofiles_sql(expression),
        vexp.DropResourcePool: lambda self, expression: self.dropresourcepool_sql(expression),
        vexp.DropRoutingRule: lambda self, expression: self.droproutingrule_sql(expression),
        vexp.DropRoles: lambda self, expression: self.droproles_sql(expression),
        vexp.DropUserDefinedExtension: lambda self, expression: self.dropuserdefinedextension_sql(
            expression
        ),
        vexp.DropUsers: lambda self, expression: self.dropusers_sql(expression),
        vexp.EncodedByProperty: lambda self, expression: (
            f"ENCODED BY {self.expressions(expression, flat=True)}"
        ),
        vexp.ExternalCopyDefinition: lambda self, expression: self.externalcopydefinition_sql(
            expression
        ),
        vexp.ExternalProcedureParameter: lambda self, expression: (
            self.externalprocedureparameter_sql(expression)
        ),
        vexp.ExternalProcedureSignature: lambda self, expression: (
            self.externalproceduresignature_sql(expression)
        ),
        vexp.Explain: lambda self, expression: self.explain_sql(expression),
        vexp.ExtendedGrantPrivilege: lambda self, expression: self.extendedgrantprivilege_sql(
            expression
        ),
        vexp.FlexibleCopyDefinition: lambda self, expression: self.flexiblecopydefinition_sql(
            expression
        ),
        vexp.GroupedProjectionColumns: lambda self, expression: (
            f"GROUPED({self.expressions(expression, flat=True)})"
        ),
        vexp.GetDirectedQuery: lambda self, expression: self.getdirectedquery_sql(expression),
        vexp.Interpolate: lambda self, expression: self.interpolate_sql(expression),
        vexp.IcebergColumnType: lambda self, expression: self.icebergcolumntype_sql(expression),
        vexp.IcebergExternalTableSpec: lambda self, expression: self.icebergexternaltablespec_sql(
            expression
        ),
        vexp.InheritedPrivilegesProperty: lambda self, expression: (
            self.inheritedprivilegesproperty_sql(expression)
        ),
        vexp.KsafeProperty: lambda self, expression: self.ksafeproperty_sql(expression),
        vexp.ListAgg: lambda self, expression: self.vertica_listagg_sql(expression),
        vexp.LoadBalanceGroupAction: lambda self, expression: self.loadbalancegroupaction_sql(
            expression
        ),
        vexp.LoadBalanceGroupSpec: lambda self, expression: self.loadbalancegroupspec_sql(
            expression
        ),
        vexp.NetworkAddressAction: lambda self, expression: self.networkaddressaction_sql(
            expression
        ),
        vexp.NetworkAddressSpec: lambda self, expression: self.networkaddressspec_sql(expression),
        vexp.LocalProperty: lambda *_: "LOCAL",
        vexp.MaterializedWithMarker: lambda *_: "",
        vexp.Match: lambda self, expression: self.vertica_match_sql(expression),
        vexp.MatchDefinition: lambda self, expression: self.matchdefinition_sql(expression),
        vexp.NoProjectionProperty: lambda *_: "NO PROJECTION",
        vexp.PartitionedLimit: lambda self, expression: self.partitionedlimit_sql(expression),
        vexp.ProjectionColumn: lambda self, expression: self.projectioncolumn_sql(expression),
        vexp.ProjectionSegmentation: lambda self, expression: self.projectionsegmentation_sql(
            expression
        ),
        vexp.ProfileLimit: lambda self, expression: self.profilelimit_sql(expression),
        vexp.ProfileParameter: lambda self, expression: self.profileparameter_sql(expression),
        vexp.ProfileStatement: lambda self, expression: self.profilestatement_sql(expression),
        vexp.RoleGrant: lambda self, expression: self.rolegrant_sql(expression),
        vexp.RoleRevoke: lambda self, expression: self.rolerevoke_sql(expression),
        vexp.RoutingRuleAction: lambda self, expression: self.routingruleaction_sql(expression),
        vexp.RoutingRuleSpec: lambda self, expression: self.routingrulespec_sql(expression),
        vexp.RoutingRuleTarget: lambda self, expression: self.routingruletarget_sql(expression),
        vexp.RowAlias: lambda self, expression: self.rowalias_sql(expression),
        vexp.RoutineSignature: lambda self, expression: self.routinesignature_sql(expression),
        vexp.ResourcePoolKeyword: lambda self, expression: self.resourcepoolkeyword_sql(expression),
        vexp.ResourcePoolParameter: lambda self, expression: self.resourcepoolparameter_sql(
            expression
        ),
        vexp.ResourcePoolSubcluster: lambda self, expression: self.resourcepoolsubcluster_sql(
            expression
        ),
        vexp.ReorganizeTable: lambda self, expression: self.reorganizetable_sql(expression),
        vexp.SchemaAuthorizationProperty: lambda self, expression: (
            f"AUTHORIZATION {self.sql(expression, 'this')}"
        ),
        vexp.SaveQuery: lambda self, expression: self.savequery_sql(expression),
        vexp.SequenceOwnerToAction: lambda self, expression: (
            f"OWNER TO {self.sql(expression, 'this')}"
        ),
        vexp.SequenceSetSchemaAction: lambda self, expression: (
            f"SET SCHEMA {self.sql(expression, 'this')}"
        ),
        vexp.SetLiteral: lambda self, expression: f"SET[{self.expressions(expression, flat=True)}]",
        vexp.SetSessionRouting: lambda self, expression: self.setsessionrouting_sql(expression),
        vexp.ShowWorkload: lambda self, expression: self.showworkload_sql(expression),
        vexp.StatementTimestamp: lambda self, expression: "GETDATE()",
        vexp.StringUnit: lambda self, expression: self.stringunit_sql(expression),
        vexp.TableOptimizerHint: lambda self, expression: (
            f"/*+ {self.expressions(expression, sep=self.QUERY_HINT_SEP).strip()} */"
        ),
        vexp.TablePartitionProperty: lambda self, expression: self.tablepartitionproperty_sql(
            expression
        ),
        vexp.TableSegmentationProperty: lambda self, expression: self.sql(expression, "this"),
        vexp.Timeseries: lambda self, expression: self.timeseries_sql(expression),
        vexp.TimeseriesSelect: lambda self, expression: self.select_sql(expression),
        vexp.TimeseriesSlice: lambda self, expression: self.sql(expression, "this"),
        vexp.UDxFactorySpec: lambda self, expression: self.udxfactoryspec_sql(expression),
        vexp.UpdateDefaultRelation: lambda self, expression: self.updatedefaultrelation_sql(
            expression
        ),
        vexp.UtcStatementTimestamp: lambda self, expression: "GETUTCDATE()",
        vexp.UsingParameters: lambda self, expression: self.usingparameters_sql(expression),
        vexp.UserAction: lambda self, expression: self.useraction_sql(expression),
        vexp.VerticaArrayLength: lambda self, expression: self.verticaarraylength_sql(expression),
        vexp.VerticaCopy: lambda self, expression: self.verticacopy_sql(expression),
        vexp.VerticaExplode: lambda self, expression: self.verticaexplode_sql(expression),
        vexp.VerticaInstr: lambda self, expression: self.verticainstr_sql(expression),
        vexp.VerticaInterval: lambda self, expression: self.interval_sql(expression),
        vexp.VerticaMerge: lambda self, expression: self.verticamerge_sql(expression),
        vexp.VerticaPrivilegeTarget: lambda self, expression: self.verticaprivilegetarget_sql(
            expression
        ),
        vexp.VerticaRegexpLike: lambda self, expression: self.verticaregexplike_sql(expression),
        vexp.VerticaToChar: lambda self, expression: self.verticatochar_sql(expression),
        vexp.VerticaWindow: lambda self, expression: self.verticawindow_sql(expression),
        vexp.WithHint: lambda self, expression: self.withhint_sql(expression),
    }

    def join_sql(self, expression: exp.Join) -> str:
        sql = super().join_sql(expression)
        hint = expression.args.get("hint")
        if not isinstance(hint, exp.Hint):
            return sql

        join_index = sql.find("JOIN")
        if join_index < 0:
            self.unsupported("Vertica join hints require an explicit JOIN")
            return sql

        hint_sql = self.sql(hint)
        return f"{sql[: join_index + 4]}{hint_sql}{sql[join_index + 4 :]}"

    def _vertica_with_sql(self, expression: exp.With, hint: str) -> str:
        sql = self.expressions(expression, flat=True)
        recursive = (
            "RECURSIVE "
            if self.CTE_RECURSIVE_KEYWORD_REQUIRED and expression.args.get("recursive")
            else ""
        )
        search = self.sql(expression, "search")
        search = f" {search}" if search else ""
        return f"WITH{hint} {recursive}{sql}{search}"

    def withhint_sql(self, expression: vexp.WithHint) -> str:
        return self._vertica_with_sql(expression, self.sql(expression, "hint"))

    def with_sql(self, expression: exp.With) -> str:
        """Recover a materialization hint after SQLGlot rebuilds exp.With."""

        for cte in expression.expressions:
            if not isinstance(cte, exp.CTE):
                continue
            for marker in cte.find_all(vexp.MaterializedWithMarker):
                if marker.find_ancestor(exp.CTE) is cte:
                    return self._vertica_with_sql(expression, self.sql(marker, "this"))

        return super().with_sql(expression)

    def _valid_directed_query(self, query: object, *, allow_subquery: bool = False) -> bool:
        if isinstance(query, exp.Select):
            return bool(query.expressions) and all(
                select.expressions for select in query.find_all(exp.Select)
            )
        if isinstance(query, exp.Subquery):
            return allow_subquery and self._valid_directed_query(
                query.args.get("this"), allow_subquery=True
            )
        if isinstance(query, exp.SetOperation):
            return self._valid_directed_query(
                query.args.get("this"), allow_subquery=True
            ) and self._valid_directed_query(query.args.get("expression"), allow_subquery=True)
        return False

    def _directed_query_input_sql(self, expression: exp.Expr, statement: str) -> str:
        query = expression.args.get("this")
        if not self._valid_directed_query(query):
            self.unsupported(f"Vertica {statement} requires a nonempty SELECT query child")
            return ""
        assert isinstance(query, exp.Expr)
        return self.sql(query)

    def savequery_sql(self, expression: vexp.SaveQuery) -> str:
        query = self._directed_query_input_sql(expression, "SAVE QUERY")
        return f"SAVE QUERY{self.sep()}{query}" if query else "SAVE QUERY"

    def getdirectedquery_sql(self, expression: vexp.GetDirectedQuery) -> str:
        query = self._directed_query_input_sql(expression, "GET DIRECTED QUERY")
        return f"GET DIRECTED QUERY{self.sep()}{query}" if query else "GET DIRECTED QUERY"

    def _directed_query_name_sql(self, name: object, statement: str) -> str:
        if isinstance(name, exp.Identifier) or (isinstance(name, exp.Literal) and name.is_string):
            return self.sql(name)
        self.unsupported(f"Vertica {statement} requires an identifier or string-literal name")
        return ""

    def createdirectedquery_sql(self, expression: vexp.CreateDirectedQuery) -> str:
        mode = expression.args.get("mode")
        mode_name = mode.name.upper() if isinstance(mode, exp.Var) else ""
        if mode_name not in {"OPT", "OPTIMIZER", "CUSTOM"}:
            self.unsupported("Vertica CREATE DIRECTED QUERY mode must be OPT, OPTIMIZER, or CUSTOM")

        name = self._directed_query_name_sql(expression.args.get("this"), "CREATE DIRECTED QUERY")
        query = expression.args.get("expression")
        if not self._valid_directed_query(query):
            self.unsupported("Vertica CREATE DIRECTED QUERY requires a nonempty SELECT query child")

        clauses = [f"CREATE DIRECTED QUERY {mode_name} {name}".rstrip()]
        for key, keyword in (
            ("comment", "COMMENT"),
            ("optimizer_version", "OPTVER"),
            ("plan_date", "PSDATE"),
        ):
            value = expression.args.get(key)
            if value is None:
                continue
            if not isinstance(value, exp.Literal) or not value.is_string:
                self.unsupported(f"Vertica CREATE DIRECTED QUERY {keyword} requires a string")
                continue
            if key == "comment" and len(value.this) > 128:
                self.unsupported("Vertica directed-query comments cannot exceed 128 characters")
            if key != "comment" and mode_name != "CUSTOM":
                self.unsupported(f"Vertica {keyword} is valid only for CUSTOM export scripts")
            clauses.append(f"{keyword} {self.sql(value)}")

        prefix = " ".join(clauses)
        return f"{prefix}{self.sep()}{self.sql(query)}" if isinstance(query, exp.Expr) else prefix

    def directedqueryaction_sql(self, expression: vexp.DirectedQueryAction) -> str:
        action = expression.args.get("action")
        action_name = action.name.upper() if isinstance(action, exp.Var) else ""
        if action_name not in {"ACTIVATE", "DEACTIVATE", "DROP"}:
            self.unsupported("Vertica directed-query action must be ACTIVATE, DEACTIVATE, or DROP")

        name = expression.args.get("this")
        query = expression.args.get("expression")
        where = expression.args.get("where")
        targets = [target for target in (name, query, where) if target is not None]
        if len(targets) != 1:
            self.unsupported("Vertica directed-query actions require exactly one target")

        prefix = f"{action_name} DIRECTED QUERY".lstrip()
        if name is not None:
            name_sql = self._directed_query_name_sql(name, f"{action_name} DIRECTED QUERY")
            return f"{prefix} {name_sql}".rstrip()
        if query is not None:
            if action_name != "DEACTIVATE":
                self.unsupported(
                    f"Vertica {action_name} DIRECTED QUERY does not accept an input query"
                )
            if not self._valid_directed_query(query):
                self.unsupported("Directed-query input targets must be nonempty SELECT queries")
                return prefix
            assert isinstance(query, exp.Expr)
            return f"{prefix}{self.sep()}{self.sql(query)}"
        if where is not None:
            if not isinstance(where, exp.Where) or where.this is None:
                self.unsupported("Directed-query WHERE targets require a condition")
                return prefix
            return f"{prefix}{self.sql(where)}"
        return prefix

    def directedconstanthint_sql(self, expression: vexp.DirectedConstantHint) -> str:
        this = expression.args.get("this")
        directive = expression.args.get("directive")
        index = expression.args.get("index")
        if not isinstance(this, exp.Expr):
            self.unsupported("A directed-query constant annotation requires an expression child")
            return ""
        if not isinstance(directive, exp.Var):
            self.unsupported("A directed-query constant annotation requires a typed directive")
            return self.sql(this)

        directive_name = directive.name.upper()
        if directive_name == ":C":
            if index is not None:
                self.unsupported("The :c directed-query annotation does not accept an index")
            annotation = ":c"
        elif directive_name in {":V", "IGNORECONST"}:
            if not isinstance(index, exp.Literal) or not index.is_int:
                self.unsupported(
                    "The :v and IGNORECONST directed-query annotations require an integer index"
                )
                annotation = ":v"
            else:
                name = ":v" if directive_name == ":V" else "IGNORECONST"
                annotation = f"{name}({index.this})"
        else:
            self.unsupported(f"Unknown directed-query constant annotation {directive.name!r}")
            annotation = directive.name

        return f"{self.sql(this)} /*+{annotation}*/"

    def _alter_table_target_sql(self, expression: exp.Alter, statement: str) -> str:
        table = expression.args.get("this")
        if not isinstance(table, exp.Table):
            self.unsupported(f"Vertica {statement} requires a table target")
        if expression.kind != "TABLE" or any(
            expression.args.get(key)
            for key in (
                "cascade",
                "check",
                "cluster",
                "exists",
                "iceberg",
                "not_valid",
                "only",
                "options",
            )
        ):
            self.unsupported(f"Vertica {statement} does not accept ALTER modifiers")
        return self.sql(table) if isinstance(table, exp.Table) else ""

    def _alter_table_partition_clause_sql(self, partition: object) -> str:
        if not isinstance(partition, vexp.TablePartitionProperty) or partition.this is None:
            self.unsupported("Vertica ALTER TABLE PARTITION BY requires a partition expression")
            return ""

        sql = f"PARTITION BY {self.sql(partition, 'this')}"
        group = self.sql(partition, "group")
        if group:
            sql += f" GROUP BY {group}"
        active_count = partition.args.get("active_partition_count")
        if active_count is not None:
            if not isinstance(active_count, exp.Literal) or not active_count.is_int:
                self.unsupported("SET ACTIVEPARTITIONCOUNT requires an integer")
            sql += f" SET ACTIVEPARTITIONCOUNT {self.sql(active_count)}"
        return sql

    def altertablepartition_sql(self, expression: vexp.AlterTablePartition) -> str:
        table = self._alter_table_target_sql(expression, "ALTER TABLE PARTITION BY")
        if expression.actions:
            self.unsupported("Vertica ALTER TABLE PARTITION BY stores its action structurally")

        partition_sql = self._alter_table_partition_clause_sql(expression.args.get("partition"))
        reorganize = expression.args.get("reorganize")
        if reorganize is not None and not isinstance(reorganize, bool):
            self.unsupported("Vertica ALTER TABLE PARTITION BY REORGANIZE must be boolean")
        clauses = [f"ALTER TABLE {table}".rstrip(), partition_sql]
        if reorganize:
            clauses.append("REORGANIZE")
        return self.sep().join(clause for clause in clauses if clause)

    def reorganizetable_sql(self, expression: vexp.ReorganizeTable) -> str:
        table = self._alter_table_target_sql(expression, "ALTER TABLE REORGANIZE")
        action = expression.actions[0] if len(expression.actions) == 1 else None
        if not isinstance(action, exp.Var) or action.name.upper() != "REORGANIZE":
            self.unsupported("Vertica table reorganization requires exactly one REORGANIZE action")

        clauses = [f"ALTER TABLE {table}".rstrip()]
        partition = expression.args.get("partition")
        if partition is not None:
            self.unsupported("Standalone REORGANIZE cannot carry a new partition clause")
        clauses.append("REORGANIZE")
        return self.sep().join(clauses)

    def explain_sql(self, expression: vexp.Explain) -> str:
        hint = self.sql(expression, "hint")
        options = self.expressions(expression, key="options", flat=True, sep=" ")
        options = f" {options}" if options else ""
        return f"EXPLAIN{hint}{options} {self.sql(expression, 'this')}"

    def _valid_dml(self, errors: list[str]) -> bool:
        for error in errors:
            self.unsupported(error)
        return not errors

    def insert_sql(self, expression: exp.Insert) -> str:
        if not self._valid_dml(vdml.insert_errors(expression)):
            return ""
        return super().insert_sql(expression)

    def merge_sql(self, expression: exp.Merge) -> str:
        if not self._valid_dml(vdml.merge_errors(expression)):
            return ""
        return super().merge_sql(expression)

    def verticamerge_sql(self, expression: vexp.VerticaMerge) -> str:
        sql = self.merge_sql(expression)
        if not sql:
            return ""
        hint = self.sql(expression, "hint")
        return f"MERGE{hint}{sql[5:]}"

    def update_sql(self, expression: exp.Update) -> str:
        if not self._valid_dml(vdml.update_errors(expression)):
            return ""
        return super().update_sql(expression)

    def updatedefaultrelation_sql(self, expression: vexp.UpdateDefaultRelation) -> str:
        joins = "".join(self.sql(join) for join in expression.args.get("joins") or [])
        return f"DEFAULT{joins}"

    def delete_sql(self, expression: exp.Delete) -> str:
        if not self._valid_dml(vdml.delete_errors(expression)):
            return ""
        return super().delete_sql(expression)

    def truncatetable_sql(self, expression: exp.TruncateTable) -> str:
        if not self._valid_dml(vdml.truncate_errors(expression)):
            return ""
        return super().truncatetable_sql(expression)

    def vertica_listagg_sql(self, expression: vexp.ListAgg) -> str:
        aggregate = expression.this
        if not isinstance(aggregate, exp.GroupConcat):
            self.unsupported("Vertica LISTAGG requires a canonical GroupConcat child")
            return ""

        arguments = [self.sql(aggregate, "this")]
        separator = self.sql(aggregate, "separator")
        if separator:
            arguments.append(separator)

        sql = f"LISTAGG({', '.join(arguments)}"
        parameters = self.expressions(expression, key="parameters", flat=True)
        if parameters:
            sql += f" USING PARAMETERS {parameters}"
        return f"{sql})"

    def usingparameters_sql(self, expression: vexp.UsingParameters) -> str:
        function = expression.this
        if not isinstance(
            function,
            (
                exp.Func,
                vexp.VerticaArrayLength,
                vexp.VerticaExplode,
                vexp.VerticaInstr,
                vexp.VerticaRegexpLike,
                vexp.VerticaToChar,
            ),
        ):
            self.unsupported("USING PARAMETERS requires a function-call child")
            return ""

        parameters = expression.args.get("parameters") or []
        if not parameters:
            self.unsupported("USING PARAMETERS requires at least one parameter")
            return ""

        parameter_sql: list[str] = []
        for parameter in parameters:
            if (
                not isinstance(parameter, exp.PropertyEQ)
                or not isinstance(parameter.this, exp.Identifier)
                or parameter.expression is None
            ):
                self.unsupported("USING PARAMETERS entries require identifier=value")
                return ""
            parameter_sql.append(
                f"{self.sql(parameter, 'this')} = {self.sql(parameter, 'expression')}"
            )

        function_sql = self.sql(function)
        if not function_sql.endswith(")"):
            self.unsupported("USING PARAMETERS requires a parenthesized function call")
            return ""
        function_prefix = function_sql[:-1]
        separator = "" if function_prefix.endswith("(") else " "
        return f"{function_prefix}{separator}USING PARAMETERS {', '.join(parameter_sql)})"

    def stringunit_sql(self, expression: vexp.StringUnit) -> str:
        unit = expression.args.get("unit")
        if not isinstance(unit, exp.Var) or unit.name.upper() not in {
            "CHARACTERS",
            "OCTETS",
        }:
            self.unsupported("String units must be CHARACTERS or OCTETS")
            return ""

        function = expression.this
        function_sql = self.sql(function)
        open_paren = function_sql.find("(")
        if open_paren <= 0 or not function_sql.endswith(")"):
            self.unsupported("A string unit requires a parenthesized function call")
            return ""

        name = expression.args.get("name")
        if name is not None:
            if not isinstance(name, exp.Var) or not re.fullmatch(
                r"[A-Z_][A-Z0-9_$]*", name.name.upper()
            ):
                self.unsupported("A string-unit function name must be an unquoted identifier")
                return ""
            function_sql = f"{name.name.upper()}{function_sql[open_paren:]}"

        if name and name.name.upper() == "POSITION" and isinstance(function, exp.StrPosition):
            if function.args.get("position") or function.args.get("occurrence"):
                self.unsupported("POSITION does not support start or occurrence arguments")
                return ""
            return (
                f"POSITION({self.sql(function, 'substr')} IN {self.sql(function, 'this')} "
                f"USING {unit.name.upper()})"
            )

        return f"{function_sql[:-1]} USING {unit.name.upper()})"

    def verticatochar_sql(self, expression: vexp.VerticaToChar) -> str:
        function = expression.this
        if (
            not isinstance(function, exp.Anonymous)
            or function.name.upper() != "TO_CHAR"
            or len(function.expressions) != 1
        ):
            self.unsupported("VerticaToChar requires a one-argument TO_CHAR call")
            return ""
        return self.func("TO_CHAR", function.expressions[0])

    def verticawindow_sql(self, expression: vexp.VerticaWindow) -> str:
        mode = expression.args.get("partition_mode")
        if (
            not isinstance(mode, exp.Var)
            or mode.name.upper() not in {"BEST", "NODES", "ROW", "LEFT JOIN"}
            or expression.args.get("partition_by")
        ):
            self.unsupported(
                "VerticaWindow requires one special partition mode and no PARTITION BY list"
            )
            return ""

        this = self.sql(expression, "this")
        order = expression.args.get("order")
        order_sql = self.order_sql(order, flat=True) if order else ""
        spec = self.sql(expression, "spec")
        alias = self.sql(expression, "alias")
        over = self.sql(expression, "over") or "OVER"
        this = f"{this} {'AS' if expression.arg_key == 'windows' else over}"

        first = expression.args.get("first")
        first_sql = "" if first is None else "FIRST" if first else "LAST"
        partition = f"PARTITION {mode.name.upper()}"
        args = self.format_args(
            *[arg for arg in (alias, first_sql, partition, order_sql, spec) if arg],
            sep=" ",
        )
        return f"{this} ({args})"

    def verticaexplode_sql(self, expression: vexp.VerticaExplode) -> str:
        function = expression.this
        if not isinstance(function, exp.Explode):
            self.unsupported("VerticaExplode requires a canonical Explode child")
            return ""
        return self.func("EXPLODE", function.this, *function.expressions)

    def verticaarraylength_sql(self, expression: vexp.VerticaArrayLength) -> str:
        function = expression.this
        if not isinstance(function, exp.ArraySize) or function.expression is not None:
            self.unsupported("VerticaArrayLength requires a one-dimensional ArraySize child")
            return ""
        return self.func("ARRAY_LENGTH", function.this)

    def vertica_array_filter_sql(self, expression: exp.ArrayFilter) -> str:
        return self.func("FILTER", expression.this, expression.expression)

    def verticaregexplike_sql(self, expression: vexp.VerticaRegexpLike) -> str:
        predicate = expression.this
        if not isinstance(predicate, exp.RegexpLike):
            self.unsupported("VerticaRegexpLike requires a canonical RegexpLike child")
            return ""
        return self.func(
            "REGEXP_LIKE",
            predicate.this,
            predicate.expression,
            *(expression.args.get("modifiers") or []),
        )

    def verticainstr_sql(self, expression: vexp.VerticaInstr) -> str:
        function = expression.this
        if not isinstance(function, exp.StrPosition):
            self.unsupported("VerticaInstr requires a canonical StrPosition child")
            return ""
        return self.func(
            "INSTR",
            function.this,
            function.args.get("substr"),
            function.args.get("position"),
            function.args.get("occurrence"),
        )

    def tonumber_sql(self, expression: exp.ToNumber) -> str:
        unsupported_args = ("nlsparam", "precision", "scale", "safe_name", "default")
        if any(
            expression.args.get(key) is not None for key in unsupported_args
        ) or expression.args.get("safe"):
            self.unsupported("Vertica TO_NUMBER supports only value and format arguments")
            return ""
        return self.func("TO_NUMBER", expression.this, expression.args.get("format"))

    def vertica_struct_sql(self, expression: exp.Struct) -> str:
        fields = []
        for field in expression.expressions:
            if isinstance(field, exp.PropertyEQ):
                fields.append(f"{self.sql(field, 'expression')} AS {self.sql(field, 'this')}")
            else:
                fields.append(self.sql(field))
        return f"ROW({', '.join(fields)})"

    def rowalias_sql(self, expression: vexp.RowAlias) -> str:
        columns = self.expressions(expression, key="columns", flat=True)
        return f"{self.alias_sql(expression)}({columns})"

    def properties(
        self,
        properties: exp.Properties,
        prefix: str = "",
        sep: str = ", ",
        suffix: str = "",
        wrapped: bool = True,
    ) -> str:
        if properties.expressions and all(
            isinstance(prop, (vexp.CtasHintProperty, vexp.AtEpochProperty))
            for prop in properties.expressions
        ):
            sep = " "
        return super().properties(
            properties,
            prefix=prefix,
            sep=sep,
            suffix=suffix,
            wrapped=wrapped,
        )

    def create_sql(self, expression: exp.Create) -> str:
        """Place Vertica DDL properties in their required order."""

        if expression.kind == "ROLE":
            return self._create_role_sql(expression)

        properties = expression.args.get("properties")
        property_order = (
            self.TABLE_PROPERTY_ORDER
            if expression.kind == "TABLE"
            else self.SCHEMA_PROPERTY_ORDER
            if expression.kind == "SCHEMA"
            else None
        )
        if (
            property_order
            and isinstance(properties, exp.Properties)
            and any(type(prop) in property_order for prop in properties.expressions)
        ):
            expression = expression.copy()
            copied_properties = expression.args["properties"]
            copied_properties.set(
                "expressions",
                sorted(
                    copied_properties.expressions,
                    key=lambda prop: property_order.get(type(prop), 0),
                ),
            )

        return super().create_sql(expression)

    def alter_sql(self, expression: exp.Alter) -> str:
        if expression.kind == "ROLE":
            return self._alter_role_sql(expression)
        if expression.kind != "SEQUENCE":
            return super().alter_sql(expression)

        actions = expression.actions
        if len(actions) != 1:
            self.unsupported("Vertica ALTER SEQUENCE requires exactly one action group")
            if not actions:
                return f"ALTER SEQUENCE {self.sql(expression, 'this')}"

        action = actions[0]
        action_sql = (
            self._vertica_sequence_properties_sql(action, restart=True)
            if isinstance(action, exp.SequenceProperties)
            else self.sql(action)
        )
        return f"ALTER SEQUENCE {self.sql(expression, 'this')} {action_sql}"

    def drop_sql(self, expression: exp.Drop) -> str:
        if expression.kind == "ROLE":
            return self._drop_role_sql(expression, require_multiple=False)
        if expression.kind != "SEQUENCE":
            return super().drop_sql(expression)

        if expression.args.get("cascade") or expression.args.get("restrict"):
            self.unsupported("Vertica DROP SEQUENCE does not support CASCADE or RESTRICT")

        targets = [self.sql(expression, "this")]
        targets.extend(self.sql(target) for target in expression.expressions)
        exists = " IF EXISTS" if expression.args.get("exists") else ""
        return f"DROP SEQUENCE{exists} {', '.join(targets)}"

    def _create_role_sql(self, expression: exp.Create) -> str:
        if not isinstance(expression.args.get("this"), exp.Identifier):
            self.unsupported("Vertica CREATE ROLE requires one unqualified role name")
        if any(
            expression.args.get(key)
            for key in (
                "begin",
                "clone",
                "clustered",
                "concurrently",
                "exists",
                "expression",
                "indexes",
                "no_schema_binding",
                "properties",
                "refresh",
                "replace",
                "unique",
                "with_",
            )
        ):
            self.unsupported("Vertica CREATE ROLE does not support CREATE modifiers or clauses")
        return f"CREATE ROLE {self.sql(expression, 'this')}"

    def _alter_role_sql(self, expression: exp.Alter) -> str:
        target = expression.args.get("this")
        actions = expression.actions
        action = actions[0] if len(actions) == 1 else None
        if not isinstance(target, exp.Identifier):
            self.unsupported("Vertica ALTER ROLE requires one unqualified role name")
        if not isinstance(action, exp.AlterRename) or not isinstance(
            action.args.get("this") if action else None, exp.Identifier
        ):
            self.unsupported("Vertica ALTER ROLE requires exactly one RENAME TO action")
        if any(
            expression.args.get(key)
            for key in (
                "cascade",
                "check",
                "cluster",
                "exists",
                "iceberg",
                "not_valid",
                "only",
                "options",
            )
        ):
            self.unsupported("Vertica ALTER ROLE does not support additional ALTER modifiers")
        return f"ALTER ROLE {self.sql(target)} {self.sql(action)}"

    def droproles_sql(self, expression: vexp.DropRoles) -> str:
        return self._drop_role_sql(expression, require_multiple=True)

    def _drop_role_sql(self, expression: exp.Drop, require_multiple: bool) -> str:
        targets = [expression.args.get("this"), *expression.expressions]
        if any(not isinstance(target, exp.Identifier) for target in targets):
            self.unsupported("Vertica DROP ROLE requires unqualified role names")
        if require_multiple and len(targets) < 2:
            self.unsupported("DropRoles requires at least two role names")
        if not require_multiple and expression.expressions:
            self.unsupported("Multiple DROP ROLE targets require the DropRoles expression")
        if expression.args.get("restrict"):
            self.unsupported("Vertica DROP ROLE does not support RESTRICT")
        if any(
            expression.args.get(key)
            for key in (
                "cluster",
                "concurrently",
                "constraints",
                "iceberg",
                "materialized",
                "purge",
                "sync",
                "temporary",
            )
        ):
            self.unsupported("Vertica DROP ROLE does not support additional DROP modifiers")

        exists = " IF EXISTS" if expression.args.get("exists") else ""
        cascade = " CASCADE" if expression.args.get("cascade") else ""
        targets_sql = ", ".join(self.sql(target) for target in targets)
        return f"DROP ROLE{exists} {targets_sql}{cascade}"

    def createuser_sql(self, expression: vexp.CreateUser) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "USER":
            self.unsupported("CreateUser requires kind USER")
        if self._has_user_extras(expression, {"this", "kind", "action"}):
            self.unsupported("CREATE USER does not support additional CREATE clauses")

        user = expression.args.get("this")
        user_valid = self._validate_user_identifier(user, "CREATE USER name")
        action = expression.args.get("action")
        action_sql = ""
        if action is not None:
            if not isinstance(action, vexp.UserAction):
                self.unsupported("CREATE USER account state requires a typed action")
            else:
                action_name = self._user_action_name(action)
                if action_name not in {
                    "ACCOUNT LOCK",
                    "ACCOUNT UNLOCK",
                    "PASSWORD EXPIRE",
                }:
                    self.unsupported(
                        "CREATE USER supports ACCOUNT LOCK, ACCOUNT UNLOCK, or PASSWORD EXPIRE"
                    )
                else:
                    action_sql = f" {self.sql(action)}"

        user_sql = self.sql(user) if user_valid else ""
        return f"CREATE USER {user_sql}{action_sql}".rstrip()

    def createprofile_sql(self, expression: vexp.CreateProfile) -> str:
        valid = self._validate_profile_root(
            expression,
            statement="CREATE PROFILE",
            allowed={"this", "kind", "limit"},
            allow_default_name=False,
        )
        limit = expression.args.get("limit")
        if not isinstance(limit, vexp.ProfileLimit):
            self.unsupported("CREATE PROFILE requires a structured LIMIT clause")
            valid = False
        elif not self._validate_profile_limit(limit, alter=False):
            valid = False
        if not valid:
            return ""
        return f"CREATE PROFILE {self.sql(expression, 'this')} LIMIT {self.sql(limit)}"

    def alterprofile_sql(self, expression: vexp.AlterProfile) -> str:
        valid = self._validate_profile_root(
            expression,
            statement="ALTER PROFILE",
            allowed={"this", "kind", "actions"},
            allow_default_name=True,
        )
        raw_actions = expression.args.get("actions")
        if not isinstance(raw_actions, list):
            self.unsupported("ALTER PROFILE actions must be a list")
            return ""
        if len(raw_actions) != 1:
            self.unsupported("ALTER PROFILE requires exactly one action")
            return ""
        action = raw_actions[0]
        target = expression.args.get("this")
        if isinstance(action, vexp.ProfileLimit):
            valid = self._validate_profile_limit(action, alter=True) and valid
            action_sql = f"LIMIT {self.sql(action)}" if valid else ""
        elif isinstance(action, exp.AlterRename):
            if self._has_user_extras(action, {"this"}):
                self.unsupported("ALTER PROFILE RENAME requires one unqualified name")
                valid = False
            if isinstance(target, exp.Identifier) and target.name.upper() == "DEFAULT":
                self.unsupported("ALTER PROFILE cannot rename the DEFAULT profile")
                valid = False
            rename = action.args.get("this")
            rename_valid = self._validate_profile_identifier(
                rename, "ALTER PROFILE RENAME TO", allow_default=False
            )
            valid = rename_valid and valid
            action_sql = self.sql(action) if valid else ""
        else:
            self.unsupported("ALTER PROFILE requires LIMIT or RENAME TO")
            return ""
        if not valid:
            return ""
        return f"ALTER PROFILE {self.sql(target)} {action_sql}"

    def dropprofiles_sql(self, expression: vexp.DropProfiles) -> str:
        valid = self._validate_profile_root(
            expression,
            statement="DROP PROFILE",
            allowed={"this", "expressions", "kind", "exists", "cascade"},
            allow_default_name=False,
        )
        raw_profiles = expression.args.get("expressions")
        if raw_profiles is None:
            secondary: list[exp.Expr] = []
        elif not isinstance(raw_profiles, list):
            self.unsupported("DROP PROFILE secondary targets must be a list")
            return ""
        else:
            secondary = raw_profiles
        profiles = [expression.args.get("this"), *secondary]
        if not profiles:
            self.unsupported("DROP PROFILE requires at least one target")
            return ""
        for profile in profiles:
            valid = (
                self._validate_profile_identifier(profile, "DROP PROFILE name", allow_default=False)
                and valid
            )
        exists = expression.args.get("exists")
        cascade = expression.args.get("cascade")
        if exists is not None and not isinstance(exists, bool):
            self.unsupported("DropProfiles exists must be boolean")
            valid = False
        if cascade is not None and not isinstance(cascade, bool):
            self.unsupported("DropProfiles cascade must be boolean")
            valid = False
        if not valid:
            return ""
        exists_sql = " IF EXISTS" if exists else ""
        cascade_sql = " CASCADE" if cascade else ""
        return (
            f"DROP PROFILE{exists_sql} {', '.join(self.sql(profile) for profile in profiles)}"
            f"{cascade_sql}"
        )

    def profilelimit_sql(self, expression: vexp.ProfileLimit) -> str:
        if not self._validate_profile_limit(
            expression, alter=isinstance(expression.parent, vexp.AlterProfile)
        ):
            return ""
        return " ".join(self.sql(parameter) for parameter in expression.expressions)

    def profileparameter_sql(self, expression: vexp.ProfileParameter) -> str:
        limit = expression.parent
        if not self._validate_profile_parameter(
            expression,
            alter=isinstance(limit, vexp.ProfileLimit)
            and isinstance(limit.parent, vexp.AlterProfile),
        ):
            return ""
        return f"{expression.name.upper()} {self.sql(expression, 'expression')}"

    def profilestatement_sql(self, expression: vexp.ProfileStatement) -> str:
        if self._has_user_extras(expression, {"this"}):
            self.unsupported("ProfileStatement contains unsupported fields")
            return ""
        statement = expression.args.get("this")
        if isinstance(statement, vexp.ProfileStatement):
            self.unsupported("Nested PROFILE statements are not supported")
            return ""
        if not self._is_profile_statement_body(statement):
            self.unsupported(
                "PROFILE requires a structured SELECT, INSERT, UPDATE, DELETE, COPY, or MERGE"
            )
            return ""
        return f"PROFILE {self.sql(statement)}"

    @classmethod
    def _is_profile_statement_body(cls, statement: object) -> bool:
        if isinstance(statement, exp.Select):
            return bool(statement.expressions)
        if isinstance(statement, exp.SetOperation):
            return cls._is_profile_statement_body(
                statement.args.get("this")
            ) and cls._is_profile_statement_body(statement.args.get("expression"))
        return isinstance(
            statement,
            (exp.Insert, exp.Update, exp.Delete, vexp.VerticaCopy, exp.Merge),
        )

    def _validate_profile_root(
        self,
        expression: exp.Expr,
        *,
        statement: str,
        allowed: set[str],
        allow_default_name: bool,
    ) -> bool:
        valid = True
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "PROFILE":
            self.unsupported(f"{type(expression).__name__} requires kind PROFILE")
            valid = False
        if self._has_user_extras(expression, allowed):
            self.unsupported(f"{statement} does not support additional statement clauses")
            valid = False
        return (
            self._validate_profile_identifier(
                expression.args.get("this"), f"{statement} name", allow_default=allow_default_name
            )
            and valid
        )

    def _validate_profile_identifier(
        self, expression: object, label: str, *, allow_default: bool
    ) -> bool:
        if (
            allow_default
            and isinstance(expression, exp.Identifier)
            and isinstance(expression.this, str)
            and expression.this.upper() == "DEFAULT"
            and expression.args.get("quoted", False) is False
        ):
            valid = self._validate_connection_policy_identifier(expression, label)
            if self._has_user_extras(expression, {"this", "quoted"}):
                self.unsupported(f"{label} contains unsupported identifier fields")
                valid = False
            return valid
        valid = self._validate_user_identifier(expression, label)
        if (
            isinstance(expression, exp.Identifier)
            and isinstance(expression.this, str)
            and expression.name.upper() == "DEFAULT"
            and (not allow_default or expression.args.get("quoted", False) is not False)
        ):
            self.unsupported(f"{label} cannot use the DEFAULT profile")
            valid = False
        return valid

    def _validate_profile_limit(self, expression: vexp.ProfileLimit, *, alter: bool) -> bool:
        if self._has_user_extras(expression, {"expressions"}):
            self.unsupported("ProfileLimit contains unsupported fields")
            return False
        raw_parameters = expression.args.get("expressions")
        if not isinstance(raw_parameters, list):
            self.unsupported("ProfileLimit expressions must be a list")
            return False
        if not raw_parameters:
            self.unsupported("PROFILE LIMIT requires at least one parameter")
            return False
        valid = True
        seen: set[str] = set()
        values: dict[str, exp.Expr | None] = {}
        for parameter in raw_parameters:
            if not isinstance(parameter, vexp.ProfileParameter):
                self.unsupported("PROFILE LIMIT requires structured parameters")
                valid = False
                continue
            name = parameter.name.upper()
            if name in seen:
                self.unsupported(f"Duplicate PROFILE parameter {name}")
                valid = False
            seen.add(name)
            values[name] = parameter.args.get("expression")
            valid = self._validate_profile_parameter(parameter, alter=alter) and valid

        maximum = values.get("PASSWORD_MAX_LENGTH")
        if isinstance(maximum, exp.Literal) and not maximum.is_string and maximum.this.isdigit():
            for name in self.PROFILE_CHARACTER_MINIMUM_PARAMETERS:
                value = values.get(name)
                if (
                    isinstance(value, exp.Literal)
                    and not value.is_string
                    and value.this.isdigit()
                    and self._profile_digits_less(maximum.this, value.this)
                ):
                    self.unsupported(f"PROFILE {name} cannot exceed explicit PASSWORD_MAX_LENGTH")
                    valid = False
        return valid

    def _validate_profile_parameter(
        self, expression: vexp.ProfileParameter, *, alter: bool
    ) -> bool:
        if self._has_user_extras(expression, {"this", "expression"}):
            self.unsupported("ProfileParameter contains unsupported fields")
            return False
        marker = expression.args.get("this")
        if not isinstance(marker, exp.Var) or self._has_user_extras(marker, {"this"}):
            self.unsupported("PROFILE parameter requires a typed keyword marker")
            return False
        raw_name = marker.args.get("this")
        if not isinstance(raw_name, str) or not raw_name.isascii():
            self.unsupported("PROFILE parameter marker must be unquoted ASCII text")
            return False
        name = raw_name.upper()
        if name not in self.PROFILE_PARAMETERS:
            self.unsupported(f"Unsupported PROFILE parameter {name}")
            return False
        value = expression.args.get("expression")
        if isinstance(value, exp.Var):
            if self._has_user_extras(value, {"this"}) or not isinstance(value.this, str):
                self.unsupported(f"PROFILE {name} requires a valid sentinel")
                return False
            sentinel = value.this.upper() if value.this.isascii() else ""
            if sentinel == "UNLIMITED":
                return True
            if sentinel == "DEFAULT" and alter:
                return True
            self.unsupported(f"PROFILE {name} does not accept sentinel {sentinel!r}")
            return False
        if not isinstance(value, exp.Literal) or value.is_string or not value.this.isdigit():
            self.unsupported(f"PROFILE {name} requires an unsigned integer or UNLIMITED")
            return False
        if name in self.PROFILE_POSITIVE_PARAMETERS and self._profile_digits_less(value.this, "1"):
            self.unsupported(f"PROFILE {name} must be at least 1")
            return False
        if name == "PASSWORD_MAX_LENGTH":
            if self._profile_digits_less(value.this, "8"):
                self.unsupported("PROFILE PASSWORD_MAX_LENGTH must be at least 8")
                return False
            if self._profile_digits_less("512", value.this):
                self.unsupported("PROFILE PASSWORD_MAX_LENGTH must be at most 512")
                return False
        return True

    @staticmethod
    def _profile_digits_less(left: str, right: str) -> bool:
        left_normalized = left.lstrip("0") or "0"
        right_normalized = right.lstrip("0") or "0"
        return (len(left_normalized), left_normalized) < (
            len(right_normalized),
            right_normalized,
        )

    def alteruser_sql(self, expression: vexp.AlterUser) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "USER":
            self.unsupported("AlterUser requires kind USER")
        if self._has_user_extras(expression, {"this", "kind", "actions"}):
            self.unsupported("ALTER USER does not support additional ALTER clauses")

        user = expression.args.get("this")
        user_valid = self._validate_user_identifier(user, "ALTER USER name")
        raw_actions = expression.args.get("actions")
        if not isinstance(raw_actions, list):
            self.unsupported("ALTER USER actions must be a list")
            actions: list[exp.Expr] = []
        else:
            actions = raw_actions
        if len(actions) != 1:
            self.unsupported("ALTER USER requires exactly one action")
            action: exp.Expr | None = actions[0] if actions else None
        else:
            action = actions[0]

        if isinstance(action, exp.AlterRename):
            rename_valid = True
            if self._has_user_extras(action, {"this"}):
                self.unsupported("ALTER USER RENAME requires one unqualified name")
                rename_valid = False
            rename_valid = (
                self._validate_user_identifier(action.args.get("this"), "ALTER USER RENAME TO")
                and rename_valid
            )
            action_sql = self.sql(action) if rename_valid else ""
        elif isinstance(action, vexp.UserAction):
            action_sql = self.sql(action)
        else:
            self.unsupported("ALTER USER requires a structured action")
            action_sql = ""

        user_sql = self.sql(user) if user_valid else ""
        return f"ALTER USER {user_sql} {action_sql}".rstrip()

    def dropusers_sql(self, expression: vexp.DropUsers) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "USER":
            self.unsupported("DropUsers requires kind USER")
        if self._has_user_extras(expression, {"this", "expressions", "kind", "exists", "cascade"}):
            self.unsupported("DROP USER does not support additional DROP clauses")

        raw_users = expression.args.get("expressions")
        if raw_users is None:
            secondary_users: list[exp.Expr] = []
        elif not isinstance(raw_users, list):
            self.unsupported("DROP USER secondary targets must be a list")
            secondary_users = []
        else:
            secondary_users = raw_users
        users = [expression.args.get("this"), *secondary_users]
        rendered_users = []
        for user in users:
            if self._validate_user_identifier(user, "DROP USER name"):
                rendered_users.append(self.sql(user))
        if not rendered_users:
            self.unsupported("DROP USER requires at least one user name")

        exists_value = expression.args.get("exists")
        cascade_value = expression.args.get("cascade")
        if exists_value is not None and not isinstance(exists_value, bool):
            self.unsupported("DropUsers exists must be boolean")
        if cascade_value is not None and not isinstance(cascade_value, bool):
            self.unsupported("DropUsers cascade must be boolean")
        exists = " IF EXISTS" if isinstance(exists_value, bool) and exists_value else ""
        cascade = " CASCADE" if isinstance(cascade_value, bool) and cascade_value else ""
        return f"DROP USER{exists} {', '.join(rendered_users)}{cascade}".rstrip()

    def useraction_sql(self, expression: vexp.UserAction) -> str:
        action = self._user_action_name(expression)
        if action not in {"ACCOUNT LOCK", "ACCOUNT UNLOCK", "PASSWORD EXPIRE"}:
            self.unsupported("UserAction must be ACCOUNT LOCK, ACCOUNT UNLOCK, or PASSWORD EXPIRE")
            return ""
        return action

    def _user_action_name(self, expression: vexp.UserAction) -> str:
        if self._has_user_extras(expression, {"this"}):
            self.unsupported("UserAction contains unsupported fields")
        marker = expression.args.get("this")
        if not isinstance(marker, exp.Var) or self._has_user_extras(marker, {"this"}):
            self.unsupported("UserAction requires a typed keyword marker")
            return ""
        raw_marker = marker.args.get("this")
        if not isinstance(raw_marker, str) or not raw_marker.isascii():
            self.unsupported("UserAction marker text must be a string")
            return ""
        return raw_marker.upper()

    def _validate_user_identifier(self, expression: object, label: str) -> bool:
        valid = self._validate_connection_policy_identifier(expression, label)
        if not isinstance(expression, exp.Identifier) or not isinstance(expression.this, str):
            return False
        if self._has_user_extras(expression, {"this", "quoted"}):
            self.unsupported(f"{label} contains unsupported identifier fields")
            valid = False
        try:
            size = len(expression.this.encode("utf-8"))
        except UnicodeEncodeError:
            self.unsupported(f"{label} must be valid UTF-8")
            valid = False
        else:
            if size > 128:
                self.unsupported(f"{label} cannot exceed 128 UTF-8 bytes")
                valid = False
        if valid and expression.args.get("quoted", False) is False:
            from sqlglot_vertica.parser import VerticaParser

            tokens = self.dialect.tokenize(expression.this)
            if (
                len(tokens) != 1
                or tokens[0].text != expression.this
                or tokens[0].token_type not in VerticaParser.ID_VAR_TOKENS
                or tokens[0].token_type
                in {TokenType.DEFAULT, TokenType.FALSE, TokenType.NULL, TokenType.TRUE}
            ):
                self.unsupported(f"{label} requires quoting for this keyword")
                valid = False
        return valid

    @staticmethod
    def _has_user_extras(expression: exp.Expr, allowed: set[str]) -> bool:
        return any(
            key not in allowed
            and (key not in expression.arg_types or (value is not None and value is not False))
            for key, value in expression.args.items()
        )

    def createresourcepool_sql(self, expression: vexp.CreateResourcePool) -> str:
        self._validate_resource_pool_target(expression)
        if any(
            expression.args.get(key)
            for key in (
                "begin",
                "clone",
                "clustered",
                "concurrently",
                "exists",
                "expression",
                "indexes",
                "no_schema_binding",
                "refresh",
                "replace",
                "unique",
                "with_",
            )
        ):
            self.unsupported(
                "Vertica CREATE RESOURCE POOL does not support CREATE modifiers or clauses"
            )

        properties = expression.args.get("properties")
        if properties is None:
            parameters: list[vexp.ResourcePoolParameter] = []
        elif isinstance(properties, exp.Properties) and all(
            isinstance(parameter, vexp.ResourcePoolParameter)
            for parameter in properties.expressions
        ):
            parameters = t.cast(list[vexp.ResourcePoolParameter], properties.expressions)
        else:
            self.unsupported(
                "Vertica CREATE RESOURCE POOL properties must be resource-pool parameters"
            )
            parameters = []

        self._validate_resource_pool_parameters(expression, parameters, alter=False)
        prefix = f"CREATE RESOURCE POOL {self.sql(expression, 'this')}"
        subcluster = self.sql(expression, "subcluster")
        if subcluster:
            prefix += f" {subcluster}"
        return self.sep().join([prefix, *(self.sql(parameter) for parameter in parameters)])

    def alterresourcepool_sql(self, expression: vexp.AlterResourcePool) -> str:
        self._validate_resource_pool_target(expression)
        parameters = expression.actions
        if not parameters or any(
            not isinstance(parameter, vexp.ResourcePoolParameter) for parameter in parameters
        ):
            self.unsupported(
                "Vertica ALTER RESOURCE POOL requires one or more resource-pool parameters"
            )
        typed_parameters = t.cast(list[vexp.ResourcePoolParameter], parameters)
        if any(
            expression.args.get(key)
            for key in (
                "cascade",
                "check",
                "cluster",
                "exists",
                "iceberg",
                "not_valid",
                "only",
                "options",
            )
        ):
            self.unsupported(
                "Vertica ALTER RESOURCE POOL does not support additional ALTER modifiers"
            )

        self._validate_resource_pool_parameters(expression, typed_parameters, alter=True)
        prefix = f"ALTER RESOURCE POOL {self.sql(expression, 'this')}"
        subcluster = self.sql(expression, "subcluster")
        if subcluster:
            prefix += f" {subcluster}"
        return self.sep().join([prefix, *(self.sql(parameter) for parameter in typed_parameters)])

    def dropresourcepool_sql(self, expression: vexp.DropResourcePool) -> str:
        self._validate_resource_pool_target(expression)
        if expression.expressions:
            self.unsupported("Vertica DROP RESOURCE POOL accepts exactly one pool")
        if expression.args.get("exists"):
            self.unsupported("Vertica DROP RESOURCE POOL does not support IF EXISTS")
        if expression.args.get("cascade") or expression.args.get("restrict"):
            self.unsupported("Vertica DROP RESOURCE POOL does not support CASCADE or RESTRICT")
        if any(
            expression.args.get(key)
            for key in (
                "cluster",
                "concurrently",
                "constraints",
                "iceberg",
                "materialized",
                "purge",
                "sync",
                "temporary",
            )
        ):
            self.unsupported(
                "Vertica DROP RESOURCE POOL does not support additional DROP modifiers"
            )

        sql = f"DROP RESOURCE POOL {self.sql(expression, 'this')}"
        subcluster = self.sql(expression, "subcluster")
        return f"{sql} {subcluster}" if subcluster else sql

    def createloadbalancegroup_sql(self, expression: vexp.CreateLoadBalanceGroup) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "LOAD BALANCE GROUP":
            self.unsupported("CreateLoadBalanceGroup requires kind LOAD BALANCE GROUP")
        if self._has_statement_extras(expression, {"this", "kind", "spec"}):
            self.unsupported("CREATE LOAD BALANCE GROUP does not support additional CREATE clauses")

        name = expression.args.get("this")
        self._validate_connection_policy_identifier(name, "CREATE LOAD BALANCE GROUP name")
        spec = expression.args.get("spec")
        if not isinstance(spec, vexp.LoadBalanceGroupSpec):
            self.unsupported("CREATE LOAD BALANCE GROUP requires a structured group specification")
            spec_sql = ""
        else:
            spec_sql = self.sql(spec)
        return f"CREATE LOAD BALANCE GROUP {self.sql(name)} {spec_sql}".rstrip()

    def alterloadbalancegroup_sql(self, expression: vexp.AlterLoadBalanceGroup) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "LOAD BALANCE GROUP":
            self.unsupported("AlterLoadBalanceGroup requires kind LOAD BALANCE GROUP")
        if self._has_statement_extras(expression, {"this", "kind", "actions"}):
            self.unsupported("ALTER LOAD BALANCE GROUP does not support additional ALTER clauses")

        target = expression.args.get("this")
        self._validate_connection_policy_identifier(target, "ALTER LOAD BALANCE GROUP name")
        raw_actions = expression.args.get("actions")
        if not isinstance(raw_actions, list):
            self.unsupported("ALTER LOAD BALANCE GROUP actions must be a list")
            actions: list[exp.Expr] = []
        else:
            actions = raw_actions
        if len(actions) != 1:
            self.unsupported("ALTER LOAD BALANCE GROUP requires exactly one action")
            action: exp.Expr | None = actions[0] if actions else None
        else:
            action = actions[0]

        if isinstance(action, exp.AlterRename):
            if self._has_statement_extras(action, {"this"}):
                self.unsupported("ALTER LOAD BALANCE GROUP RENAME requires one unqualified name")
            self._validate_connection_policy_identifier(
                action.args.get("this"), "ALTER LOAD BALANCE GROUP RENAME"
            )
        elif not isinstance(action, vexp.LoadBalanceGroupAction):
            self.unsupported("ALTER LOAD BALANCE GROUP requires a structured action")

        action_sql = (
            self.sql(action)
            if isinstance(action, (exp.AlterRename, vexp.LoadBalanceGroupAction))
            else ""
        )
        return f"ALTER LOAD BALANCE GROUP {self.sql(target)} {action_sql}".rstrip()

    def droploadbalancegroup_sql(self, expression: vexp.DropLoadBalanceGroup) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "LOAD BALANCE GROUP":
            self.unsupported("DropLoadBalanceGroup requires kind LOAD BALANCE GROUP")
        if self._has_statement_extras(expression, {"this", "kind", "exists", "cascade"}):
            self.unsupported("DROP LOAD BALANCE GROUP does not support additional DROP clauses")

        target = expression.args.get("this")
        self._validate_connection_policy_identifier(target, "DROP LOAD BALANCE GROUP name")
        exists_value = expression.args.get("exists")
        cascade_value = expression.args.get("cascade")
        if exists_value is not None and not isinstance(exists_value, bool):
            self.unsupported("DropLoadBalanceGroup exists must be boolean")
        if cascade_value is not None and not isinstance(cascade_value, bool):
            self.unsupported("DropLoadBalanceGroup cascade must be boolean")
        exists = " IF EXISTS" if exists_value else ""
        cascade = " CASCADE" if cascade_value else ""
        return f"DROP LOAD BALANCE GROUP{exists} {self.sql(target)}{cascade}"

    def loadbalancegroupspec_sql(self, expression: vexp.LoadBalanceGroupSpec) -> str:
        if self._has_statement_extras(expression, {"this", "expressions", "filter", "policy"}):
            self.unsupported("LoadBalanceGroupSpec contains unsupported fields")
        member_kind = self._load_balance_group_member_kind(expression.args.get("this"))
        raw_members = expression.args.get("expressions")
        if raw_members is None:
            members: list[exp.Expr] = []
        elif not isinstance(raw_members, list):
            self.unsupported("LOAD BALANCE GROUP members must be a list")
            members = []
        else:
            members = raw_members
        if not members:
            self.unsupported("LOAD BALANCE GROUP requires one or more members")
        for member in members:
            self._validate_connection_policy_identifier(member, f"{member_kind} member")

        filter_value = expression.args.get("filter")
        if member_kind == "ADDRESS":
            if filter_value is not None:
                self.unsupported("ADDRESS load balance groups do not support FILTER")
            filter_sql = ""
        else:
            if not self._is_load_balance_group_string(filter_value):
                self.unsupported(f"{member_kind} load balance groups require a quoted FILTER")
                filter_sql = ""
            else:
                filter_sql = f" FILTER {self.sql(filter_value)}"

        policy = expression.args.get("policy")
        policy_sql = ""
        if policy is not None:
            self._validate_load_balance_group_policy(policy)
            policy_sql = f" POLICY {self.sql(policy)}"
        members_sql = ", ".join(self.sql(member) for member in members)
        return f"WITH {member_kind} {members_sql}{filter_sql}{policy_sql}".rstrip()

    def loadbalancegroupaction_sql(self, expression: vexp.LoadBalanceGroupAction) -> str:
        if self._has_statement_extras(
            expression, {"this", "member_kind", "expression", "expressions"}
        ):
            self.unsupported("LoadBalanceGroupAction contains unsupported fields")
        marker = expression.args.get("this")
        if not isinstance(marker, exp.Var):
            self.unsupported("LoadBalanceGroupAction requires a typed action marker")
            action = ""
        else:
            action = marker.name.upper()

        member_marker = expression.args.get("member_kind")
        scalar = expression.args.get("expression")
        raw_members = expression.args.get("expressions")
        if raw_members is None:
            members: list[exp.Expr] = []
        elif not isinstance(raw_members, list):
            self.unsupported("LoadBalanceGroupAction members must be a list")
            members = []
        else:
            members = raw_members
        if action in {"SET FILTER", "SET POLICY"}:
            if member_marker is not None or not self._is_load_balance_group_string(scalar):
                self.unsupported(f"{action} requires exactly one quoted string value")
            if members:
                self.unsupported(f"{action} does not accept a member list")
            if action == "SET POLICY":
                self._validate_load_balance_group_policy(scalar)
            return f"{action} TO {self.sql(scalar)}"

        if action in {"ADD", "DROP"}:
            if scalar is not None:
                self.unsupported(f"{action} does not accept a scalar value")
            member_kind = self._load_balance_group_member_kind(member_marker)
            if not members:
                self.unsupported(f"{action} {member_kind} requires one or more members")
            for member in members:
                self._validate_connection_policy_identifier(member, f"{action} {member_kind}")
            members_sql = ", ".join(self.sql(member) for member in members)
            return f"{action} {member_kind} {members_sql}".rstrip()

        self.unsupported(f"Unsupported ALTER LOAD BALANCE GROUP action: {action}")
        return action

    def createnetworkaddress_sql(self, expression: vexp.CreateNetworkAddress) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "NETWORK ADDRESS":
            self.unsupported("CreateNetworkAddress requires kind NETWORK ADDRESS")
        if self._has_statement_extras(expression, {"this", "kind", "spec"}):
            self.unsupported("CREATE NETWORK ADDRESS does not support additional CREATE clauses")

        name = expression.args.get("this")
        name_valid = self._validate_connection_policy_identifier(
            name, "CREATE NETWORK ADDRESS name"
        )
        spec = expression.args.get("spec")
        if not isinstance(spec, vexp.NetworkAddressSpec):
            self.unsupported("CREATE NETWORK ADDRESS requires a structured address specification")
            spec_sql = ""
        else:
            spec_sql = self.sql(spec)
        name_sql = self.sql(name) if name_valid else ""
        return f"CREATE NETWORK ADDRESS {name_sql} {spec_sql}".rstrip()

    def alternetworkaddress_sql(self, expression: vexp.AlterNetworkAddress) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "NETWORK ADDRESS":
            self.unsupported("AlterNetworkAddress requires kind NETWORK ADDRESS")
        if self._has_statement_extras(expression, {"this", "kind", "actions"}):
            self.unsupported("ALTER NETWORK ADDRESS does not support additional ALTER clauses")

        target = expression.args.get("this")
        target_valid = self._validate_connection_policy_identifier(
            target, "ALTER NETWORK ADDRESS name"
        )
        raw_actions = expression.args.get("actions")
        if not isinstance(raw_actions, list):
            self.unsupported("ALTER NETWORK ADDRESS actions must be a list")
            actions: list[exp.Expr] = []
        else:
            actions = raw_actions
        if len(actions) != 1:
            self.unsupported("ALTER NETWORK ADDRESS requires exactly one action")
            action: exp.Expr | None = actions[0] if actions else None
        else:
            action = actions[0]

        if isinstance(action, exp.AlterRename):
            rename_valid = True
            if self._has_statement_extras(action, {"this"}):
                self.unsupported("ALTER NETWORK ADDRESS RENAME requires one unqualified name")
                rename_valid = False
            rename_valid = (
                self._validate_connection_policy_identifier(
                    action.args.get("this"), "ALTER NETWORK ADDRESS RENAME"
                )
                and rename_valid
            )
            action_sql = self.sql(action) if rename_valid else ""
        elif isinstance(action, vexp.NetworkAddressAction):
            action_sql = self.sql(action)
        else:
            self.unsupported("ALTER NETWORK ADDRESS requires a structured action")
            action_sql = ""

        target_sql = self.sql(target) if target_valid else ""
        return f"ALTER NETWORK ADDRESS {target_sql} {action_sql}".rstrip()

    def dropnetworkaddress_sql(self, expression: vexp.DropNetworkAddress) -> str:
        kind = expression.args.get("kind")
        if not isinstance(kind, str) or kind != "NETWORK ADDRESS":
            self.unsupported("DropNetworkAddress requires kind NETWORK ADDRESS")
        if self._has_statement_extras(expression, {"this", "kind", "exists", "cascade"}):
            self.unsupported("DROP NETWORK ADDRESS does not support additional DROP clauses")

        target = expression.args.get("this")
        target_valid = self._validate_connection_policy_identifier(
            target, "DROP NETWORK ADDRESS name"
        )
        exists_value = expression.args.get("exists")
        cascade_value = expression.args.get("cascade")
        if exists_value is not None and not isinstance(exists_value, bool):
            self.unsupported("DropNetworkAddress exists must be boolean")
        if cascade_value is not None and not isinstance(cascade_value, bool):
            self.unsupported("DropNetworkAddress cascade must be boolean")
        exists = " IF EXISTS" if isinstance(exists_value, bool) and exists_value else ""
        cascade = " CASCADE" if isinstance(cascade_value, bool) and cascade_value else ""
        target_sql = self.sql(target) if target_valid else ""
        return f"DROP NETWORK ADDRESS{exists} {target_sql}{cascade}".rstrip()

    def networkaddressspec_sql(self, expression: vexp.NetworkAddressSpec) -> str:
        if self._has_statement_extras(expression, {"this", "node", "port", "state"}):
            self.unsupported("NetworkAddressSpec contains unsupported fields")

        address = expression.args.get("this")
        node = expression.args.get("node")
        node_valid = self._validate_connection_policy_identifier(node, "NETWORK ADDRESS node")
        address_valid = self._validate_network_address_string(
            address, "NETWORK ADDRESS requires a quoted address string"
        )

        port = expression.args.get("port")
        port_sql = ""
        if port is not None and self._validate_network_address_port(port):
            port_sql = f" PORT {self.sql(port)}"

        state = expression.args.get("state")
        state_sql = ""
        if state is not None:
            state_name = self._network_address_marker(state)
            if state_name not in {"ENABLED", "DISABLED"}:
                self.unsupported("NETWORK ADDRESS state must be ENABLED or DISABLED")
            else:
                state_sql = f" {state_name}"

        node_sql = self.sql(node) if node_valid else ""
        address_sql = self.sql(address) if address_valid else ""
        return f"ON {node_sql} WITH {address_sql}{port_sql}{state_sql}"

    def networkaddressaction_sql(self, expression: vexp.NetworkAddressAction) -> str:
        if self._has_statement_extras(expression, {"this", "expression", "port"}):
            self.unsupported("NetworkAddressAction contains unsupported fields")
        action = self._network_address_marker(expression.args.get("this"))
        address = expression.args.get("expression")
        port = expression.args.get("port")

        if action == "SET":
            address_valid = self._validate_network_address_string(
                address, "ALTER NETWORK ADDRESS SET requires a quoted address string"
            )
            port_sql = ""
            if port is not None and self._validate_network_address_port(port):
                port_sql = f" PORT {self.sql(port)}"
            address_sql = self.sql(address) if address_valid else ""
            return f"SET TO {address_sql}{port_sql}"

        if action in {"ENABLE", "DISABLE"}:
            if address is not None or port is not None:
                self.unsupported(f"ALTER NETWORK ADDRESS {action} does not accept values")
            return action

        self.unsupported("NetworkAddressAction must be SET, ENABLE, or DISABLE")
        return action

    def createroutingrule_sql(self, expression: vexp.CreateRoutingRule) -> str:
        if expression.kind != "ROUTING RULE":
            self.unsupported("CreateRoutingRule requires kind ROUTING RULE")
        if self._has_statement_extras(expression, {"this", "kind", "route"}):
            self.unsupported("CREATE ROUTING RULE does not support additional CREATE clauses")

        name = expression.args.get("this")
        if name is not None:
            self._validate_connection_policy_identifier(name, "CREATE ROUTING RULE name")
        route = expression.args.get("route")
        if not isinstance(route, vexp.RoutingRuleSpec):
            self.unsupported("CREATE ROUTING RULE requires a structured route specification")
            route_sql = self.sql(route)
        else:
            mode = self._routing_rule_mode(route)
            if mode == "ADDRESS" and not isinstance(name, exp.Identifier):
                self.unsupported("Classic CREATE ROUTING RULE requires a rule name")
            route_sql = self.sql(route)

        name_sql = f" {self.sql(name)}" if name is not None else ""
        return f"CREATE ROUTING RULE{name_sql} {route_sql}"

    def alterroutingrule_sql(self, expression: vexp.AlterRoutingRule) -> str:
        if expression.kind != "ROUTING RULE":
            self.unsupported("AlterRoutingRule requires kind ROUTING RULE")
        if self._has_statement_extras(expression, {"this", "kind", "actions"}):
            self.unsupported("ALTER ROUTING RULE does not support additional ALTER clauses")

        target = expression.args.get("this")
        if not isinstance(target, vexp.RoutingRuleTarget):
            self.unsupported("ALTER ROUTING RULE requires a structured target")
        actions = expression.actions
        if len(actions) != 1:
            self.unsupported("ALTER ROUTING RULE requires exactly one action")
            action: exp.Expr | None = actions[0] if actions else None
        else:
            action = actions[0]

        if isinstance(action, exp.AlterRename):
            rename_target = action.args.get("this")
            if self._has_statement_extras(action, {"this"}):
                self.unsupported("ALTER ROUTING RULE RENAME requires one unqualified name")
            self._validate_connection_policy_identifier(rename_target, "ALTER ROUTING RULE RENAME")
        elif not isinstance(action, vexp.RoutingRuleAction):
            self.unsupported("ALTER ROUTING RULE requires a structured action")

        action_sql = (
            self.sql(action)
            if isinstance(action, (exp.AlterRename, vexp.RoutingRuleAction))
            else ""
        )
        return f"ALTER ROUTING RULE {self.sql(target)} {action_sql}"

    def droproutingrule_sql(self, expression: vexp.DropRoutingRule) -> str:
        if expression.kind != "ROUTING RULE":
            self.unsupported("DropRoutingRule requires kind ROUTING RULE")
        if self._has_statement_extras(expression, {"this", "kind", "exists"}):
            self.unsupported("DROP ROUTING RULE does not support additional DROP clauses")

        target = expression.args.get("this")
        if not isinstance(target, vexp.RoutingRuleTarget):
            self.unsupported("DROP ROUTING RULE requires one structured target")
        exists_value = expression.args.get("exists")
        if exists_value is not None and not isinstance(exists_value, bool):
            self.unsupported("DropRoutingRule exists must be boolean")
        exists = " IF EXISTS" if exists_value else ""
        return f"DROP ROUTING RULE{exists} {self.sql(target)}"

    def routingrulespec_sql(self, expression: vexp.RoutingRuleSpec) -> str:
        if self._has_statement_extras(expression, {"mode", "this", "expressions", "priority"}):
            self.unsupported("RoutingRuleSpec contains unsupported fields")
        mode = self._routing_rule_mode(expression)
        source = expression.args.get("this")
        destinations = expression.expressions
        priority = expression.args.get("priority")

        if mode == "ADDRESS":
            if not isinstance(source, exp.Literal) or not source.is_string:
                self.unsupported("Classic routing rules require a quoted address range")
            if len(destinations) != 1:
                self.unsupported("Classic routing rules require exactly one unqualified group")
            if priority is not None:
                self.unsupported("Classic routing rules do not support PRIORITY")
            destination = destinations[0] if destinations else None
            self._validate_connection_policy_identifier(destination, "Classic routing-rule group")
            return f"ROUTE {self.sql(source)} TO {self.sql(destination)}"

        if mode == "WORKLOAD":
            self._validate_connection_policy_identifier(source, "Workload routing-rule workload")
            if not destinations:
                self.unsupported("Workload routing rules require one or more subclusters")
            for destination in destinations:
                self._validate_connection_policy_identifier(
                    destination, "Workload routing-rule subcluster"
                )
            priority_sql = ""
            if priority is not None:
                self._validate_routing_rule_priority(priority)
                priority_sql = f" PRIORITY {self.sql(priority)}"
            return (
                f"ROUTE WORKLOAD {self.sql(source)} TO SUBCLUSTER "
                f"{self.expressions(expression, flat=True)}{priority_sql}"
            )

        self.unsupported("RoutingRuleSpec mode must be ADDRESS or WORKLOAD")
        return f"ROUTE {self.sql(source)}"

    def routingruletarget_sql(self, expression: vexp.RoutingRuleTarget) -> str:
        if self._has_statement_extras(expression, {"this", "workload"}):
            self.unsupported("RoutingRuleTarget contains unsupported fields")
        target = expression.args.get("this")
        self._validate_connection_policy_identifier(target, "Routing-rule target")
        workload = expression.args.get("workload")
        if workload is not None and not isinstance(workload, bool):
            self.unsupported("RoutingRuleTarget workload must be boolean")
        prefix = "FOR WORKLOAD " if workload else ""
        return f"{prefix}{self.sql(target)}"

    def routingruleaction_sql(self, expression: vexp.RoutingRuleAction) -> str:
        if self._has_statement_extras(expression, {"this", "expression", "expressions"}):
            self.unsupported("RoutingRuleAction contains unsupported fields")
        marker = expression.args.get("this")
        if not isinstance(marker, exp.Var):
            self.unsupported("RoutingRuleAction requires a typed action marker")
            action = ""
        else:
            action = marker.name.upper()

        scalar = expression.args.get("expression")
        values = expression.expressions
        scalar_actions = {"SET GROUP", "SET PRIORITY", "SET ROUTE", "SET WORKLOAD"}
        list_actions = {"ADD SUBCLUSTER", "REMOVE SUBCLUSTER", "SET SUBCLUSTER"}
        if action in scalar_actions:
            if scalar is None or values:
                self.unsupported(f"{action} requires exactly one value")
            if action == "SET ROUTE":
                if not isinstance(scalar, exp.Literal) or not scalar.is_string:
                    self.unsupported("SET ROUTE requires a quoted address range")
            elif action == "SET PRIORITY":
                self._validate_routing_rule_priority(scalar)
            else:
                self._validate_connection_policy_identifier(scalar, action)
            return f"{action} TO {self.sql(scalar)}"

        if action in list_actions:
            if scalar is not None or not values:
                self.unsupported(f"{action} requires one or more unqualified subclusters")
            for value in values:
                self._validate_connection_policy_identifier(value, action)
            separator = " TO " if action == "SET SUBCLUSTER" else " "
            return f"{action}{separator}{self.expressions(expression, flat=True)}"

        self.unsupported(f"Unsupported ALTER ROUTING RULE action: {action}")
        return action

    def setsessionrouting_sql(self, expression: vexp.SetSessionRouting) -> str:
        if self._has_statement_extras(expression, {"expressions", "unset", "tag"}):
            self.unsupported("SetSessionRouting contains unsupported SET fields")
        for flag in ("unset", "tag"):
            flag_value = expression.args.get(flag)
            if flag_value is not None and not isinstance(flag_value, bool):
                self.unsupported(f"SET SESSION routing {flag} must be boolean")
            if flag_value:
                self.unsupported("SET SESSION routing does not support UNSET or TAG")
        if len(expression.expressions) != 1:
            self.unsupported("SET SESSION routing requires exactly one assignment")
        item = expression.expressions[0] if expression.expressions else None
        if not isinstance(item, exp.SetItem) or item.args.get("kind") != "SESSION":
            self.unsupported("SET SESSION routing requires one SESSION SetItem")
            assignment = None
        else:
            if self._has_statement_extras(item, {"this", "kind"}):
                self.unsupported("SET SESSION routing SetItem contains unsupported fields")
            assignment = item.args.get("this")
        if not isinstance(assignment, exp.EQ):
            self.unsupported("SET SESSION routing requires a structured assignment")
            left = None
            value = None
        else:
            if self._has_statement_extras(assignment, {"this", "expression"}):
                self.unsupported("SET SESSION routing assignment contains unsupported fields")
            left = assignment.args.get("this")
            value = assignment.args.get("expression")

        if (
            not isinstance(left, exp.Column)
            or not isinstance(left.args.get("this"), exp.Identifier)
            or len(left.parts) != 1
        ):
            self.unsupported("SET SESSION routing requires WORKLOAD or RESOURCE_POOL")
            name = ""
        else:
            name = left.name.upper()

        if isinstance(value, exp.Identifier):
            self._validate_connection_policy_identifier(value, f"SET SESSION {name} value")
            if not value.quoted and value.name.upper() in {"DEFAULT", "NONE"}:
                self.unsupported("SET SESSION routing sentinels require typed keyword nodes")
            value_sql = self.sql(value)
        elif isinstance(value, exp.Var) and value.name.upper() in {"DEFAULT", "NONE"}:
            value_sql = value.name.upper()
        else:
            self.unsupported("SET SESSION routing values must be names, DEFAULT, or NONE")
            value_sql = self.sql(value)

        if name == "WORKLOAD":
            return f"SET SESSION WORKLOAD TO {value_sql}"
        if name == "RESOURCE_POOL":
            if isinstance(value, exp.Var) and value.name.upper() == "NONE":
                self.unsupported("SET SESSION RESOURCE_POOL does not support NONE")
            return f"SET SESSION RESOURCE_POOL = {value_sql}"
        self.unsupported("SET SESSION routing requires WORKLOAD or RESOURCE_POOL")
        return f"SET SESSION {name} = {value_sql}"

    def showworkload_sql(self, expression: vexp.ShowWorkload) -> str:
        if self._has_statement_extras(expression, {"this", "available"}):
            self.unsupported("SHOW WORKLOAD does not support additional SHOW clauses")
        target = expression.args.get("this")
        if not isinstance(target, exp.Var) or target.name.upper() != "WORKLOAD":
            self.unsupported("ShowWorkload requires the WORKLOAD target")
        available = expression.args.get("available")
        if available is not None and not isinstance(available, bool):
            self.unsupported("ShowWorkload available must be boolean")
        return "SHOW AVAILABLE WORKLOADS" if available else "SHOW WORKLOAD"

    def _load_balance_group_member_kind(self, marker: object) -> str:
        if not isinstance(marker, exp.Var):
            self.unsupported("LOAD BALANCE GROUP member kind requires a typed marker")
            return ""
        member_kind = marker.name.upper()
        if member_kind not in self.LOAD_BALANCE_GROUP_MEMBER_KINDS:
            self.unsupported(
                "LOAD BALANCE GROUP member kind must be ADDRESS, FAULT GROUP, or SUBCLUSTER"
            )
        return member_kind

    def _validate_load_balance_group_policy(self, policy: object) -> None:
        if not self._is_load_balance_group_string(policy):
            self.unsupported("LOAD BALANCE GROUP POLICY requires a quoted string literal")
            return
        assert isinstance(policy, exp.Literal)
        assert isinstance(policy.this, str)
        if policy.this.upper() not in self.LOAD_BALANCE_GROUP_POLICIES:
            self.unsupported("LOAD BALANCE GROUP POLICY must be ROUNDROBIN, RANDOM, or NONE")

    @staticmethod
    def _is_load_balance_group_string(expression: object) -> bool:
        return (
            isinstance(expression, exp.Literal)
            and expression.args.get("is_string") is True
            and isinstance(expression.this, str)
        )

    def _validate_network_address_string(self, expression: object, message: str) -> bool:
        valid = (
            isinstance(expression, exp.Literal)
            and expression.args.get("is_string") is True
            and isinstance(expression.this, str)
            and not self._has_statement_extras(expression, {"this", "is_string"})
        )
        if not valid:
            self.unsupported(message)
        return valid

    def _validate_network_address_port(self, value: object) -> bool:
        valid = (
            isinstance(value, exp.Literal)
            and value.args.get("is_string") is False
            and isinstance(value.this, str)
            and bool(value.this)
            and value.this.isascii()
            and value.this.isdigit()
            and not self._has_statement_extras(value, {"this", "is_string"})
        )
        if not valid:
            self.unsupported("NETWORK ADDRESS PORT requires a nonnegative integer")
        return valid

    def _network_address_marker(self, marker: object) -> str:
        if not isinstance(marker, exp.Var):
            self.unsupported("NETWORK ADDRESS marker requires a typed keyword")
            return ""
        raw_marker = marker.args.get("this")
        if not isinstance(raw_marker, str) or self._has_statement_extras(marker, {"this"}):
            self.unsupported("NETWORK ADDRESS marker requires a typed keyword")
            return ""
        return raw_marker.upper()

    @staticmethod
    def _routing_rule_mode(expression: vexp.RoutingRuleSpec) -> str:
        mode = expression.args.get("mode")
        return mode.name.upper() if isinstance(mode, exp.Var) else ""

    def _validate_routing_rule_priority(self, value: exp.Expr | None) -> None:
        if not isinstance(value, exp.Literal) or not value.is_int or int(value.this) < 0:
            self.unsupported("ROUTING RULE PRIORITY must be a nonnegative integer")

    def _validate_connection_policy_identifier(self, expression: object, label: str) -> bool:
        if not isinstance(expression, exp.Identifier) or not isinstance(expression.this, str):
            self.unsupported(f"{label} requires an unqualified identifier")
            return False

        valid = True
        quoted = expression.args.get("quoted", False)
        if not isinstance(quoted, bool):
            self.unsupported(f"{label} quoted flag must be boolean")
            valid = False
        if self._has_statement_extras(expression, {"this", "quoted"}):
            self.unsupported(f"{label} contains unsupported identifier fields")
            valid = False
        if not expression.this:
            self.unsupported(f"{label} requires a nonempty identifier")
            valid = False
        elif quoted is False and not self._is_safe_connection_policy_identifier(expression.this):
            self.unsupported(f"{label} requires a safely quoted identifier")
            valid = False
        return valid

    @staticmethod
    def _is_safe_connection_policy_identifier(name: str) -> bool:
        return (
            bool(name)
            and (name[0] == "_" or (name[0].isascii() and name[0].isalpha()))
            and all(
                character in {"_", "$"}
                or (character.isascii() and character.isdigit())
                or character.isalpha()
                for character in name[1:]
            )
        )

    @staticmethod
    def _has_statement_extras(expression: exp.Expr, allowed: set[str]) -> bool:
        for key, value in expression.args.items():
            if key in allowed or value is None or value is False:
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            return True
        return False

    def resourcepoolsubcluster_sql(self, expression: vexp.ResourcePoolSubcluster) -> str:
        name = expression.args.get("this")
        current = expression.args.get("current")
        if bool(name) == bool(current):
            self.unsupported(
                "A resource-pool selector requires exactly one named or current subcluster"
            )
        if name is not None and not isinstance(name, exp.Identifier):
            self.unsupported("A named resource-pool subcluster must be an unqualified identifier")
        return "FOR CURRENT SUBCLUSTER" if current else f"FOR SUBCLUSTER {self.sql(name)}"

    def resourcepoolparameter_sql(self, expression: vexp.ResourcePoolParameter) -> str:
        name = expression.name.upper()
        value = self.sql(expression, "value")
        if not name or not value:
            self.unsupported("A resource-pool parameter requires a name and value")
        return f"{name} {value}"

    def resourcepoolkeyword_sql(self, expression: vexp.ResourcePoolKeyword) -> str:
        name = expression.name.upper()
        if not name:
            self.unsupported("A resource-pool keyword requires a value")
        return f"'{name}'" if expression.args.get("quoted") else name

    def _validate_resource_pool_target(
        self,
        expression: vexp.CreateResourcePool | vexp.AlterResourcePool | vexp.DropResourcePool,
    ) -> None:
        if expression.kind != "RESOURCE POOL":
            self.unsupported("Resource-pool statement roots require kind RESOURCE POOL")
        if not isinstance(expression.args.get("this"), exp.Identifier):
            self.unsupported("Vertica RESOURCE POOL requires one unqualified pool name")
        subcluster = expression.args.get("subcluster")
        if subcluster is not None and not isinstance(subcluster, vexp.ResourcePoolSubcluster):
            self.unsupported("Vertica RESOURCE POOL requires a structured subcluster selector")

    def _validate_resource_pool_parameters(
        self,
        expression: vexp.CreateResourcePool | vexp.AlterResourcePool,
        parameters: list[vexp.ResourcePoolParameter],
        alter: bool,
    ) -> None:
        seen: set[str] = set()
        by_name: dict[str, vexp.ResourcePoolParameter] = {}
        pool = expression.args.get("this")
        pool_name = pool.name.upper() if isinstance(pool, exp.Identifier) else ""
        pool_quoted = pool.quoted if isinstance(pool, exp.Identifier) else False

        for parameter in parameters:
            name = parameter.name.upper()
            if name not in self.RESOURCE_POOL_PARAMETERS:
                self.unsupported(f"Unsupported Vertica RESOURCE POOL parameter: {name}")
            if name in seen:
                self.unsupported(f"Duplicate Vertica RESOURCE POOL parameter: {name}")
            seen.add(name)
            by_name[name] = parameter
            self._validate_resource_pool_parameter_value(
                name=name,
                value=parameter.args.get("value"),
                alter=alter,
                pool_name=pool_name,
                pool_quoted=pool_quoted,
            )

        affinity_set = "CPUAFFINITYSET" in seen
        affinity_mode = "CPUAFFINITYMODE" in seen
        if affinity_set != affinity_mode:
            self.unsupported("Vertica CPUAFFINITYSET and CPUAFFINITYMODE must be set together")
        if affinity_set and affinity_mode:
            mode = by_name["CPUAFFINITYMODE"].args.get("value")
            affinity = by_name["CPUAFFINITYSET"].args.get("value")
            if self._resource_pool_keyword_value(mode) == (
                "ANY",
                False,
            ) and self._resource_pool_keyword_value(affinity) not in {
                ("DEFAULT", False),
                ("NONE", False),
            }:
                self.unsupported("Vertica CPUAFFINITYMODE ANY requires CPUAFFINITYSET NONE")

    def _validate_resource_pool_parameter_value(
        self,
        name: str,
        value: exp.Expr | None,
        alter: bool,
        pool_name: str,
        pool_quoted: bool,
    ) -> None:
        keyword = self._resource_pool_keyword_value(value)
        if keyword == ("DEFAULT", False):
            if not alter:
                self.unsupported("Vertica RESOURCE POOL DEFAULT values are ALTER-only")
            return

        if name == "CASCADE TO":
            if not isinstance(value, exp.Identifier):
                self.unsupported("Vertica RESOURCE POOL CASCADE TO requires a pool name")
            return
        if name == "CPUAFFINITYMODE":
            self._validate_resource_pool_enum(name, keyword, {"ANY", "EXCLUSIVE", "SHARED"})
            return
        if name == "CPUAFFINITYSET":
            if keyword == ("NONE", False):
                return
            if not self._is_resource_pool_string(value) or not re.fullmatch(
                r"(?:\d+(?:,\d+)*|\d+-\d+|\d+%)", t.cast(exp.Literal, value).this
            ):
                self.unsupported(
                    "Vertica CPUAFFINITYSET requires a quoted CPU list, range, or percentage"
                )
            return
        if name == "EXECUTIONPARALLELISM":
            if keyword != ("AUTO", False):
                self._validate_resource_pool_integer(name, value, minimum=0)
            return
        if name == "MAXCONCURRENCY":
            if keyword != ("NONE", False):
                self._validate_resource_pool_integer(name, value, minimum=0)
            return
        if name in {"MAXMEMORYSIZE", "MAXQUERYMEMORYSIZE"}:
            if keyword != ("NONE", False):
                self._validate_resource_pool_memory(name, value)
            return
        if name == "MEMORYSIZE":
            self._validate_resource_pool_memory(name, value)
            return
        if name == "PLANNEDCONCURRENCY":
            if keyword != ("AUTO", False):
                self._validate_resource_pool_integer(name, value, minimum=1)
            return
        if name == "PRIORITY":
            if keyword != ("HOLD", False):
                priority_limit = (
                    110
                    if alter
                    and not pool_quoted
                    and pool_name in self.RESOURCE_POOL_EXTENDED_PRIORITY_NAMES
                    else 100
                )
                self._validate_resource_pool_integer(
                    name, value, minimum=-priority_limit, maximum=priority_limit
                )
            return
        if name == "QUEUETIMEOUT":
            if keyword == ("NONE", True) or self._is_resource_pool_string(value):
                return
            self._validate_resource_pool_integer(name, value, minimum=0)
            return
        if name == "RUNTIMECAP":
            if keyword != ("NONE", False) and not self._is_resource_pool_string(value):
                self.unsupported("Vertica RUNTIMECAP requires a quoted interval or NONE")
            return
        if name == "RUNTIMEPRIORITY":
            self._validate_resource_pool_enum(name, keyword, {"HIGH", "LOW", "MEDIUM"})
            return
        if name == "RUNTIMEPRIORITYTHRESHOLD":
            self._validate_resource_pool_integer(name, value, minimum=0)
            return
        if name == "SINGLEINITIATOR" and not isinstance(value, exp.Boolean):
            self.unsupported("Vertica SINGLEINITIATOR requires TRUE or FALSE")

    def _validate_resource_pool_enum(
        self, name: str, keyword: tuple[str, bool] | None, values: set[str]
    ) -> None:
        if keyword not in {(value, False) for value in values}:
            self.unsupported(f"Vertica {name} requires one of {', '.join(sorted(values))}")

    def _validate_resource_pool_memory(self, name: str, value: exp.Expr | None) -> None:
        if not self._is_resource_pool_string(value) or not re.fullmatch(
            r"\d+(?:%|[KMGT])", t.cast(exp.Literal, value).this, flags=re.IGNORECASE
        ):
            self.unsupported(f"Vertica {name} requires a quoted integer percentage or K/M/G/T size")

    def _validate_resource_pool_integer(
        self,
        name: str,
        value: exp.Expr | None,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> None:
        number = self._resource_pool_integer_value(value)
        if number is None:
            self.unsupported(f"Vertica {name} requires an integer")
            return
        if minimum is not None and number < minimum:
            self.unsupported(f"Vertica {name} must be at least {minimum}")
        if maximum is not None and number > maximum:
            self.unsupported(f"Vertica {name} must be at most {maximum}")

    @staticmethod
    def _resource_pool_integer_value(value: exp.Expr | None) -> int | None:
        if isinstance(value, exp.Neg):
            negative = True
            literal = value.this
        else:
            negative = False
            literal = value
        if not isinstance(literal, exp.Literal) or not literal.is_int:
            return None
        number = int(literal.this)
        return -number if negative else number

    @staticmethod
    def _resource_pool_keyword_value(value: exp.Expr | None) -> tuple[str, bool] | None:
        if not isinstance(value, vexp.ResourcePoolKeyword):
            return None
        return value.name.upper(), bool(value.args.get("quoted"))

    @staticmethod
    def _is_resource_pool_string(value: exp.Expr | None) -> bool:
        return isinstance(value, exp.Literal) and value.is_string

    def sequenceproperties_sql(self, expression: exp.SequenceProperties) -> str:
        return self._vertica_sequence_properties_sql(expression, restart=False)

    def _vertica_sequence_properties_sql(
        self, expression: exp.SequenceProperties, restart: bool
    ) -> str:
        options: dict[str, exp.Expr] = {}
        unknown_options: list[exp.Expr] = []
        supported_options = {"NO MINVALUE", "NO MAXVALUE", "NO CACHE", "CYCLE", "NO CYCLE"}
        for option in expression.args.get("options") or []:
            if isinstance(option, exp.Expr) and option.name.upper() in supported_options:
                options[option.name.upper()] = option
            elif isinstance(option, exp.Expr):
                unknown_options.append(option)

        clauses: list[str] = []
        increment = expression.args.get("increment")
        if increment is not None:
            clauses.append(f"INCREMENT BY {self.sql(increment)}")

        minvalue = expression.args.get("minvalue")
        if minvalue is not None:
            clauses.append(f"MINVALUE {self.sql(minvalue)}")
        elif "NO MINVALUE" in options:
            clauses.append("NO MINVALUE")

        maxvalue = expression.args.get("maxvalue")
        if maxvalue is not None:
            clauses.append(f"MAXVALUE {self.sql(maxvalue)}")
        elif "NO MAXVALUE" in options:
            clauses.append("NO MAXVALUE")

        start = expression.args.get("start")
        if start is not None:
            keyword = "RESTART WITH" if restart else "START WITH"
            clauses.append(f"{keyword} {self.sql(start)}")

        cache = expression.args.get("cache")
        if cache is not None:
            if cache is True:
                self.unsupported("Vertica SEQUENCE CACHE requires an integer")
                clauses.append("CACHE")
            else:
                clauses.append(f"CACHE {self.sql(cache)}")
        elif "NO CACHE" in options:
            clauses.append("NO CACHE")

        if "CYCLE" in options:
            clauses.append("CYCLE")
        elif "NO CYCLE" in options:
            clauses.append("NO CYCLE")

        if expression.args.get("owned") is not None:
            self.unsupported("Vertica sequences do not support OWNED BY")
        if unknown_options:
            self.unsupported(
                "Vertica does not support these sequence options: "
                f"{self.expressions(exp.Tuple(expressions=unknown_options), flat=True)}"
            )

        return " ".join(clauses)

    def grant_sql(self, expression: exp.Grant) -> str:
        target = expression.args.get("securable")
        if isinstance(target, vexp.VerticaPrivilegeTarget):
            self._validate_security_generation(expression, target, grant=True)
        return super().grant_sql(expression)

    def revoke_sql(self, expression: exp.Revoke) -> str:
        target = expression.args.get("securable")
        if isinstance(target, vexp.VerticaPrivilegeTarget):
            self._validate_security_generation(expression, target, grant=False)
        return super().revoke_sql(expression)

    def _validate_security_generation(
        self,
        expression: exp.Grant | exp.Revoke,
        target: vexp.VerticaPrivilegeTarget,
        grant: bool,
    ) -> None:
        kind = target.args.get("kind")
        privileges = expression.args.get("privileges") or []
        if isinstance(kind, str):
            workload_kind = kind.strip().upper()
        elif isinstance(kind, exp.Expr):
            workload_kind = kind.name.strip().upper()
            self.unsupported("Vertica privilege target kind must be a string")
        else:
            workload_kind = ""
            if kind is not None:
                self.unsupported("Vertica privilege target kind must be a string")
        if workload_kind in {"ROUTING RULE", "WORKLOAD"}:
            if kind != "WORKLOAD":
                self.unsupported("Vertica workload privilege targets require canonical WORKLOAD")
            self._validate_workload_security_generation(expression, target, grant)

        if (
            grant
            and kind == "RESOURCE POOL"
            and any(
                isinstance(privilege, exp.GrantPrivilege)
                and privilege.name.upper().startswith("ALL")
                for privilege in privileges
            )
        ):
            self.unsupported("Vertica RESOURCE POOL GRANT requires USAGE")

        if any(isinstance(privilege, vexp.ExtendedGrantPrivilege) for privilege in privileges) and (
            kind
            in {
                "DATABASE",
                "DATA LOADER",
                "LOCATION",
                "PROCEDURE",
                "RESOURCE POOL",
                "WORKLOAD",
            }
        ):
            self.unsupported(f"Vertica {kind} privileges do not support EXTEND")

    def _validate_workload_security_generation(
        self,
        expression: exp.Grant | exp.Revoke,
        target: vexp.VerticaPrivilegeTarget,
        grant: bool,
    ) -> None:
        allowed_root_args = {
            "privileges",
            "kind",
            "securable",
            "principals",
            "grant_option",
        }
        if not grant:
            allowed_root_args.add("cascade")
        if self._has_statement_extras(expression, allowed_root_args):
            self.unsupported("Vertica WORKLOAD privileges contain unsupported statement fields")
        if expression.args.get("kind") is not None:
            self.unsupported("Vertica WORKLOAD privileges do not accept an outer object kind")
        grant_option = expression.args.get("grant_option")
        if grant_option is not None and grant_option is not False:
            self.unsupported("Vertica WORKLOAD privileges do not support grant options")
        if not grant and expression.args.get("cascade") is not None:
            self.unsupported("Vertica WORKLOAD REVOKE does not support CASCADE")

        privileges = expression.args.get("privileges") or []
        if len(privileges) != 1 or not isinstance(privileges[0], exp.GrantPrivilege):
            self.unsupported("Vertica WORKLOAD privileges require exactly one USAGE privilege")
        else:
            privilege = privileges[0]
            marker = privilege.args.get("this")
            if (
                self._has_statement_extras(privilege, {"this"})
                or not isinstance(marker, exp.Var)
                or marker.name.upper() != "USAGE"
            ):
                self.unsupported("Vertica WORKLOAD privileges require argument-free USAGE")

        if self._has_statement_extras(target, {"kind", "expressions"}):
            self.unsupported("Vertica WORKLOAD targets do not support qualifiers")
        targets = target.expressions
        if len(targets) != 1 or not isinstance(targets[0], exp.Table):
            self.unsupported("Vertica WORKLOAD privileges require exactly one workload target")
        else:
            workload = targets[0]
            if self._has_statement_extras(workload, {"this"}):
                self.unsupported("Vertica WORKLOAD targets must be unqualified and unaliased")
            self._validate_connection_policy_identifier(
                workload.args.get("this"), "WORKLOAD target"
            )

        principals = expression.args.get("principals") or []
        if len(principals) != 1 or not isinstance(principals[0], exp.GrantPrincipal):
            self.unsupported("Vertica WORKLOAD privileges require exactly one principal")
        else:
            principal = principals[0]
            if self._has_statement_extras(principal, {"this"}):
                self.unsupported("Vertica WORKLOAD principals cannot use qualifiers")
            self._validate_connection_policy_identifier(
                principal.args.get("this"), "WORKLOAD principal"
            )

    def extendedgrantprivilege_sql(self, expression: vexp.ExtendedGrantPrivilege) -> str:
        if not expression.args.get("extend") or expression.name.upper() != "ALL":
            self.unsupported("Vertica ExtendedGrantPrivilege requires ALL ... EXTEND")
        privileges = " PRIVILEGES" if expression.args.get("privileges") else ""
        return f"ALL{privileges} EXTEND"

    def verticaprivilegetarget_sql(self, expression: vexp.VerticaPrivilegeTarget) -> str:
        kind_value = expression.args.get("kind")
        if kind_value is not None and not isinstance(kind_value, str):
            self.unsupported("Vertica privilege target kind must be a string")
            kind = ""
        else:
            kind = kind_value or ""
        targets = self.expressions(expression, flat=True)
        target_count = len(expression.expressions)
        all_in_schema = expression.args.get("all_in_schema")
        subcluster = self.sql(expression, "subcluster")
        current_subcluster = expression.args.get("current_subcluster")
        node = self.sql(expression, "node")

        if not targets:
            self.unsupported("Vertica privilege targets require at least one object")
        if subcluster and current_subcluster:
            self.unsupported("A resource-pool target cannot use two subcluster qualifiers")

        if all_in_schema:
            plural = {"FUNCTION": "FUNCTIONS", "SEQUENCE": "SEQUENCES", "TABLE": "TABLES"}.get(kind)
            if not plural:
                self.unsupported(
                    "Vertica ALL ... IN SCHEMA requires functions, sequences, or tables"
                )
                plural = f"{kind}S"
            if subcluster or current_subcluster or node:
                self.unsupported("ALL ... IN SCHEMA cannot use target qualifiers")
            return f"ALL {plural} IN SCHEMA {targets}"

        routine_kinds = {
            "AGGREGATE FUNCTION",
            "ANALYTIC FUNCTION",
            "FILTER",
            "FUNCTION",
            "PARSER",
            "PROCEDURE",
            "SOURCE",
            "TRANSFORM FUNCTION",
        }
        if kind in routine_kinds:
            if not all(
                isinstance(target, vexp.RoutineSignature) for target in expression.expressions
            ):
                self.unsupported("Routine privilege targets require typed signatures")
            return f"{kind} {targets}"

        if kind == "LOCATION":
            if target_count != 1:
                self.unsupported("LOCATION privileges require exactly one path")
            return f"LOCATION {targets}{f' ON {node}' if node else ''}"

        if node:
            self.unsupported("Only LOCATION privilege targets support ON node")

        if kind == "WORKLOAD":
            if target_count != 1:
                self.unsupported("WORKLOAD privileges require exactly one workload")
            return f"WORKLOAD {targets}"

        if kind == "RESOURCE POOL":
            qualifier = (
                " FOR CURRENT SUBCLUSTER"
                if current_subcluster
                else f" FOR SUBCLUSTER {subcluster}"
                if subcluster
                else ""
            )
            return f"RESOURCE POOL {targets}{qualifier}"

        if subcluster or current_subcluster:
            self.unsupported("Only RESOURCE POOL privilege targets support FOR SUBCLUSTER")
        return f"{kind + ' ' if kind else ''}{targets}"

    def routinesignature_sql(self, expression: vexp.RoutineSignature) -> str:
        return f"{self.sql(expression, 'this')}({self.expressions(expression, flat=True)})"

    def createuserdefinedextension_sql(self, expression: vexp.CreateUserDefinedExtension) -> str:
        kind = expression.kind or ""
        if kind not in self.USER_DEFINED_EXTENSION_LANGUAGES or kind == "LIBRARY":
            self.unsupported(f"Unsupported Vertica user-defined extension kind: {kind}")

        if expression.args.get("replace") and expression.args.get("exists"):
            self.unsupported("OR REPLACE and IF NOT EXISTS are mutually exclusive")
        if any(
            expression.args.get(key)
            for key in (
                "begin",
                "clone",
                "clustered",
                "concurrently",
                "indexes",
                "no_schema_binding",
                "properties",
                "refresh",
                "unique",
                "with_",
            )
        ):
            self.unsupported("Factory-backed Vertica UDxs do not support additional CREATE clauses")

        target = self._catalog_name_sql(expression.args.get("this"), f"CREATE {kind}")
        spec = expression.args.get("expression")
        if not isinstance(spec, vexp.UDxFactorySpec):
            self.unsupported(f"CREATE {kind} requires a structured UDx factory specification")
            spec_sql = self.sql(spec)
        else:
            spec_sql = self._udx_factory_spec_sql(spec, kind)

        replace = " OR REPLACE" if expression.args.get("replace") else ""
        exists = " IF NOT EXISTS" if expression.args.get("exists") else ""
        return self.sep().join(
            [
                f"CREATE{replace} {kind}{exists} {target}",
                f"AS {spec_sql}",
            ]
        )

    def udxfactoryspec_sql(self, expression: vexp.UDxFactorySpec) -> str:
        return self._udx_factory_spec_sql(expression, kind=None)

    def _udx_factory_spec_sql(self, expression: vexp.UDxFactorySpec, kind: str | None) -> str:
        if any(
            value
            for key, value in expression.args.items()
            if key not in {"language", "factory", "library", "fenced"}
        ):
            self.unsupported("Vertica UDx factory specifications do not support extra clauses")

        language = expression.args.get("language")
        canonical_language = self._canonical_udx_language(language, kind)
        effective_language = canonical_language.upper() if canonical_language else "C++"

        factory = expression.args.get("factory")
        if not isinstance(factory, exp.Literal) or not factory.is_string:
            self.unsupported("Vertica UDx factory NAME must be a string")

        library = expression.args.get("library")
        library_sql = self._catalog_name_sql(library, "Vertica UDx LIBRARY")

        fenced = expression.args.get("fenced")
        if fenced is not None and not isinstance(fenced, bool):
            self.unsupported("Vertica UDx fenced mode must be FENCED, NOT FENCED, or omitted")
        if kind == "AGGREGATE FUNCTION" and fenced is True:
            self.unsupported("Vertica aggregate functions cannot run FENCED")
        if effective_language != "C++" and fenced is False:
            self.unsupported(f"Vertica {effective_language} UDxs cannot run NOT FENCED")

        clauses = []
        if language is not None:
            language_sql = f"'{canonical_language}'" if canonical_language else self.sql(language)
            clauses.append(f"LANGUAGE {language_sql}")
        clauses.extend([f"NAME {self.sql(factory)}", f"LIBRARY {library_sql}"])
        if fenced is True:
            clauses.append("FENCED")
        elif fenced is False:
            clauses.append("NOT FENCED")
        return self.sep().join(clauses)

    def _canonical_udx_language(self, language: object, kind: str | None) -> str | None:
        if language is None:
            return None
        if not isinstance(language, exp.Literal) or not language.is_string:
            self.unsupported("Vertica UDx LANGUAGE must be a string")
            return None

        normalized = language.this.upper()
        canonical = self.USER_DEFINED_EXTENSION_LANGUAGE_NAMES.get(normalized)
        allowed = self.USER_DEFINED_EXTENSION_LANGUAGES.get(kind or "")
        if allowed is None:
            allowed = set().union(*self.USER_DEFINED_EXTENSION_LANGUAGES.values())
        if canonical is None or normalized not in allowed:
            label = kind or "UDx"
            self.unsupported(f"Unsupported Vertica {label} language: {language.this}")
            return None
        return canonical

    def dropuserdefinedextension_sql(self, expression: vexp.DropUserDefinedExtension) -> str:
        kind = expression.kind or ""
        if kind not in self.USER_DEFINED_EXTENSION_LANGUAGES or kind == "LIBRARY":
            self.unsupported(f"Unsupported Vertica user-defined extension kind: {kind}")

        signature = expression.args.get("this")
        self._validate_udx_routine_signature(signature, kind)
        if expression.args.get("exists") and kind in self.USER_DEFINED_LOAD_FUNCTION_KINDS:
            self.unsupported(f"DROP {kind} does not support IF EXISTS")
        if (
            isinstance(signature, vexp.RoutineSignature)
            and signature.expressions
            and kind in self.USER_DEFINED_LOAD_FUNCTION_KINDS
        ):
            self.unsupported(f"DROP {kind} requires an empty argument signature")
        if expression.args.get("cascade") or expression.args.get("restrict"):
            self.unsupported(f"DROP {kind} does not support CASCADE or RESTRICT")
        if expression.expressions or any(
            expression.args.get(key)
            for key in (
                "cluster",
                "concurrently",
                "constraints",
                "iceberg",
                "materialized",
                "purge",
                "sync",
                "temporary",
            )
        ):
            self.unsupported(f"DROP {kind} accepts one signature and no additional DROP clauses")

        exists = " IF EXISTS" if expression.args.get("exists") else ""
        return f"DROP {kind}{exists} {self.sql(signature)}"

    def _validate_udx_routine_signature(self, signature: object, kind: str) -> None:
        if not isinstance(signature, vexp.RoutineSignature):
            self.unsupported(f"DROP {kind} requires a structured routine signature")
            return

        if any(
            value for key, value in signature.args.items() if key not in {"this", "expressions"}
        ):
            self.unsupported(f"DROP {kind} signatures do not support extra clauses")

        self._catalog_name_sql(signature.args.get("this"), f"DROP {kind}")
        for argument in signature.expressions:
            if isinstance(argument, exp.DataType):
                continue
            if not isinstance(argument, exp.ColumnDef):
                self.unsupported(f"DROP {kind} arguments require a type or named type")
                continue
            if not isinstance(argument.args.get("this"), exp.Identifier) or not isinstance(
                argument.args.get("kind"), exp.DataType
            ):
                self.unsupported(f"DROP {kind} named arguments require a name and type")
            if any(
                argument.args.get(key) for key in argument.arg_types if key not in {"this", "kind"}
            ):
                self.unsupported(f"DROP {kind} arguments do not support column clauses")

    def createlibrary_sql(self, expression: vexp.CreateLibrary) -> str:
        if expression.kind != "LIBRARY":
            self.unsupported("Vertica CreateLibrary roots require kind LIBRARY")
        if expression.args.get("exists"):
            self.unsupported("CREATE LIBRARY does not support IF NOT EXISTS")
        if any(
            expression.args.get(key)
            for key in (
                "begin",
                "clone",
                "clustered",
                "concurrently",
                "expression",
                "indexes",
                "no_schema_binding",
                "properties",
                "refresh",
                "unique",
                "with_",
            )
        ):
            self.unsupported("Vertica CREATE LIBRARY does not support additional CREATE clauses")

        target = self._catalog_name_sql(expression.args.get("this"), "CREATE LIBRARY")
        path = expression.args.get("path")
        if not isinstance(path, exp.Literal) or not path.is_string:
            self.unsupported("CREATE LIBRARY path must be a string")
        depends = expression.args.get("depends")
        if depends is not None and (not isinstance(depends, exp.Literal) or not depends.is_string):
            self.unsupported("CREATE LIBRARY DEPENDS must be a string")
        language = expression.args.get("language")
        canonical_language = self._canonical_udx_language(language, "LIBRARY")

        replace = " OR REPLACE" if expression.args.get("replace") else ""
        clauses = [f"CREATE{replace} LIBRARY {target}", f"AS {self.sql(path)}"]
        if depends is not None:
            clauses.append(f"DEPENDS {self.sql(depends)}")
        if language is not None:
            language_sql = f"'{canonical_language}'" if canonical_language else self.sql(language)
            clauses.append(f"LANGUAGE {language_sql}")
        return self.sep().join(clauses)

    def droplibrary_sql(self, expression: vexp.DropLibrary) -> str:
        if expression.kind != "LIBRARY":
            self.unsupported("Vertica DropLibrary roots require kind LIBRARY")
        target = self._catalog_name_sql(expression.args.get("this"), "DROP LIBRARY")
        if expression.args.get("restrict"):
            self.unsupported("DROP LIBRARY does not support RESTRICT")
        if expression.expressions or any(
            expression.args.get(key)
            for key in (
                "cluster",
                "concurrently",
                "constraints",
                "iceberg",
                "materialized",
                "purge",
                "sync",
                "temporary",
            )
        ):
            self.unsupported("DROP LIBRARY accepts one target and no additional DROP clauses")

        exists = " IF EXISTS" if expression.args.get("exists") else ""
        cascade = " CASCADE" if expression.args.get("cascade") else ""
        return f"DROP LIBRARY{exists} {target}{cascade}"

    def _catalog_name_sql(self, value: object, label: str) -> str:
        if not isinstance(value, exp.Table):
            self.unsupported(f"{label} requires a qualified catalog name")
            return self.sql(value) if isinstance(value, exp.Expr) else ""

        if not isinstance(value.args.get("this"), exp.Identifier) or any(
            part is not None and not isinstance(part, exp.Identifier)
            for part in (value.args.get("db"), value.args.get("catalog"))
        ):
            self.unsupported(f"{label} requires at most a database, schema, and object name")
        if any(
            value.args.get(key) for key in value.arg_types if key not in {"this", "db", "catalog"}
        ):
            self.unsupported(f"{label} does not support table aliases or query modifiers")
        return self.sql(value)

    def rolegrant_sql(self, expression: vexp.RoleGrant) -> str:
        roles = self.expressions(expression, key="roles", flat=True)
        principals = self.expressions(expression, key="principals", flat=True)
        if not roles or not principals:
            self.unsupported("Vertica role GRANT requires roles and grantees")
        if expression.args.get("grant_option"):
            self.unsupported("Vertica role GRANT uses ADMIN OPTION, not GRANT OPTION")
        admin = " WITH ADMIN OPTION" if expression.args.get("admin_option") else ""
        return f"GRANT {roles} TO {principals}{admin}"

    def rolerevoke_sql(self, expression: vexp.RoleRevoke) -> str:
        roles = self.expressions(expression, key="roles", flat=True)
        principals = self.expressions(expression, key="principals", flat=True)
        if not roles or not principals:
            self.unsupported("Vertica role REVOKE requires roles and grantees")
        if expression.args.get("grant_option"):
            self.unsupported("Vertica role REVOKE uses ADMIN OPTION, not GRANT OPTION")
        admin = "ADMIN OPTION FOR " if expression.args.get("admin_option") else ""
        cascade = " CASCADE" if expression.args.get("cascade") else ""
        return f"REVOKE {admin}{roles} FROM {principals}{cascade}"

    def authenticationgrant_sql(self, expression: vexp.AuthenticationGrant) -> str:
        authentication = self.sql(expression, "this")
        principals = self.expressions(expression, key="principals", flat=True)
        if not authentication or not principals:
            self.unsupported("Vertica AUTHENTICATION GRANT requires a method and grantees")
        if expression.args.get("grant_option") or expression.args.get("admin_option"):
            self.unsupported("Vertica AUTHENTICATION GRANT does not support options")
        return f"GRANT AUTHENTICATION {authentication} TO {principals}"

    def authenticationrevoke_sql(self, expression: vexp.AuthenticationRevoke) -> str:
        authentication = self.sql(expression, "this")
        principals = self.expressions(expression, key="principals", flat=True)
        if not authentication or not principals:
            self.unsupported("Vertica AUTHENTICATION REVOKE requires a method and grantees")
        if expression.args.get("grant_option") or expression.args.get("cascade"):
            self.unsupported("Vertica AUTHENTICATION REVOKE does not support options")
        return f"REVOKE AUTHENTICATION {authentication} FROM {principals}"

    def ksafeproperty_sql(self, expression: vexp.KsafeProperty) -> str:
        safety = self.sql(expression, "this")
        return f"KSAFE {safety}" if safety else "KSAFE"

    def atepochproperty_sql(self, expression: vexp.AtEpochProperty) -> str:
        return f"AT {self.sql(expression, 'kind')} {self.sql(expression, 'this')}"

    def tablepartitionproperty_sql(self, expression: vexp.TablePartitionProperty) -> str:
        sql = f"PARTITION BY {self.sql(expression, 'this')}"
        group = self.sql(expression, "group")
        if group:
            sql += f" GROUP BY {group}"
        active_partition_count = self.sql(expression, "active_partition_count")
        if active_partition_count:
            sql += f" ACTIVEPARTITIONCOUNT {active_partition_count}"
        return sql

    def inheritedprivilegesproperty_sql(self, expression: vexp.InheritedPrivilegesProperty) -> str:
        action = "INCLUDE" if expression.args["include"] else "EXCLUDE"
        schema = " SCHEMA" if expression.args.get("schema") else ""
        return f"{action}{schema} PRIVILEGES"

    def createexternaltable_sql(self, expression: vexp.CreateExternalTable) -> str:
        target = self.sql(expression, "this")
        definition = expression.args.get("expression")
        if not target or type(definition) is not vexp.ExternalCopyDefinition:
            self.unsupported(
                "Vertica CREATE EXTERNAL TABLE requires a target and external COPY definition"
            )
        if (
            isinstance(definition, vexp.ExternalCopyDefinition)
            and not isinstance(expression.args.get("this"), exp.Schema)
            and not isinstance(definition.args.get("source"), vexp.CopyUDL)
        ):
            self.unsupported("Regular external tables require columns unless they use a UDL source")

        properties = expression.args.get("properties")
        if isinstance(properties, exp.Properties) and any(
            not isinstance(prop, vexp.InheritedPrivilegesProperty)
            for prop in properties.expressions
        ):
            self.unsupported(
                "Regular Vertica external tables only support INCLUDE or EXCLUDE PRIVILEGES"
            )

        exists = " IF NOT EXISTS" if expression.args.get("exists") else ""
        clauses = [f"CREATE EXTERNAL TABLE{exists} {target}"]
        properties_sql = self.sql(properties)
        if properties_sql:
            clauses.append(properties_sql)
        clauses.append(f"AS {self.sql(definition)}")
        return self.sep().join(clauses)

    def createflexibleexternaltable_sql(self, expression: vexp.CreateFlexibleExternalTable) -> str:
        schema = expression.args.get("this")
        definition = expression.args.get("expression")
        if not isinstance(schema, exp.Schema):
            self.unsupported(
                "Vertica CREATE FLEXIBLE EXTERNAL TABLE requires column-list parentheses"
            )
            target = self.sql(schema)
        else:
            table = self.sql(schema, "this")
            columns = self.expressions(schema, flat=True)
            target = f"{table} ({columns})"
        if not isinstance(definition, vexp.FlexibleCopyDefinition):
            self.unsupported(
                "Vertica CREATE FLEXIBLE EXTERNAL TABLE requires a flexible COPY definition"
            )

        properties = expression.args.get("properties")
        if isinstance(properties, exp.Properties) and any(
            not isinstance(prop, vexp.InheritedPrivilegesProperty)
            for prop in properties.expressions
        ):
            self.unsupported("Flexible external tables only support INCLUDE or EXCLUDE PRIVILEGES")

        exists = " IF NOT EXISTS" if expression.args.get("exists") else ""
        clauses = [f"CREATE FLEXIBLE EXTERNAL TABLE{exists} {target}"]
        properties_sql = self.sql(properties)
        if properties_sql:
            clauses.append(properties_sql)
        clauses.append(f"AS {self.sql(definition)}")
        return self.sep().join(clauses)

    def createicebergexternaltable_sql(self, expression: vexp.CreateIcebergExternalTable) -> str:
        target = self.sql(expression, "this")
        spec = expression.args.get("expression")
        if not target or isinstance(expression.args.get("this"), exp.Schema):
            self.unsupported("Iceberg external tables require a name without ordinary columns")
        if not isinstance(spec, vexp.IcebergExternalTableSpec):
            self.unsupported("Iceberg external tables require an Iceberg specification")
        if expression.args.get("exists"):
            self.unsupported("Iceberg external tables do not support IF NOT EXISTS")
        if expression.args.get("replace") or expression.args.get("properties"):
            self.unsupported("Iceberg external tables do not support CREATE properties")
        return self.sep().join([f"CREATE EXTERNAL TABLE {target}", self.sql(spec)])

    def icebergexternaltablespec_sql(self, expression: vexp.IcebergExternalTableSpec) -> str:
        location = expression.args.get("location")
        if not isinstance(location, exp.Literal) or not location.is_string:
            self.unsupported("Iceberg LOCATION must be a string")

        catalog_values = {
            "GLUE_DB": expression.args.get("glue_db"),
            "GLUE_TABLE": expression.args.get("glue_table"),
            "HMS_DB": expression.args.get("hms_db"),
            "HMS_TABLE": expression.args.get("hms_table"),
            "REST_AUTH": expression.args.get("rest_auth"),
        }
        for name, value in catalog_values.items():
            if value is not None and (not isinstance(value, exp.Literal) or not value.is_string):
                self.unsupported(f"Iceberg {name} must be a string")

        has_glue = catalog_values["GLUE_DB"] is not None or catalog_values["GLUE_TABLE"] is not None
        has_hms = catalog_values["HMS_DB"] is not None or catalog_values["HMS_TABLE"] is not None
        has_rest = catalog_values["REST_AUTH"] is not None
        if has_glue and not all(
            catalog_values[name] is not None for name in ("GLUE_DB", "GLUE_TABLE")
        ):
            self.unsupported("Iceberg GLUE_DB and GLUE_TABLE must be specified together")
        if has_hms and not all(
            catalog_values[name] is not None for name in ("HMS_DB", "HMS_TABLE")
        ):
            self.unsupported("Iceberg HMS_DB and HMS_TABLE must be specified together")
        if sum((has_glue, has_hms, has_rest)) > 1:
            self.unsupported("Iceberg Glue, HMS, and REST catalog modes are mutually exclusive")

        column_types = expression.args.get("column_types") or []
        if any(not isinstance(column_type, vexp.IcebergColumnType) for column_type in column_types):
            self.unsupported("Iceberg COLUMN TYPES requires structured type overrides")
        names = [
            column_type.name.lower()
            for column_type in column_types
            if isinstance(column_type, vexp.IcebergColumnType)
        ]
        if len(names) != len(set(names)):
            self.unsupported("Iceberg COLUMN TYPES cannot repeat columns")

        clauses = [f"STORED BY ICEBERG LOCATION {self.sql(location)}"]
        clauses.extend(
            f"{name} {self.sql(value)}"
            for name, value in catalog_values.items()
            if value is not None
        )
        if column_types:
            clauses.append(
                f"COLUMN TYPES ({self.expressions(expression, key='column_types', flat=True)})"
            )
        return self.sep().join(clauses)

    def icebergcolumntype_sql(self, expression: vexp.IcebergColumnType) -> str:
        name = self.sql(expression, "this")
        kind = expression.args.get("kind")
        if not name or not isinstance(kind, exp.DataType):
            self.unsupported("Iceberg COLUMN TYPES entries require a name and data type")
        elif not self._is_valid_iceberg_override_type(kind):
            self.unsupported(
                "Iceberg COLUMN TYPES only supports sized VARCHAR/VARBINARY, bounded ARRAY, "
                "or eligible ROW fields"
            )
        return f"{name} {self.sql(kind)}"

    def _is_valid_iceberg_override_type(self, kind: exp.DataType) -> bool:
        if kind.this in self.ICEBERG_SIZED_TYPES:
            return len(kind.expressions) == 1 and self._is_positive_integer_type_size(
                kind.expressions[0]
            )
        if kind.this == exp.DType.ARRAY:
            values = kind.args.get("values") or []
            return (
                len(values) == 1
                and self._is_positive_integer_type_size(values[0])
                and len(kind.expressions) == 1
                and isinstance(kind.expressions[0], exp.DataType)
                and self._is_valid_iceberg_array_element_type(kind.expressions[0])
            )
        if kind.this == exp.DType.STRUCT:
            fields = kind.expressions
            return bool(fields) and all(
                isinstance(field, exp.ColumnDef)
                and not field.args.get("constraints")
                and isinstance(field.args.get("kind"), exp.DataType)
                and self._is_valid_iceberg_override_type(field.args["kind"])
                for field in fields
            )
        return False

    def _is_valid_iceberg_array_element_type(self, kind: exp.DataType) -> bool:
        if kind.this in {exp.DType.LONGTEXT, exp.DType.LONGBLOB}:
            return False
        if kind.this == exp.DType.STRUCT:
            return bool(kind.expressions) and all(
                isinstance(field, exp.ColumnDef)
                and not field.args.get("constraints")
                and isinstance(field.args.get("kind"), exp.DataType)
                and self._is_valid_iceberg_array_element_type(field.args["kind"])
                for field in kind.expressions
            )
        if kind.this == exp.DType.ARRAY:
            return (
                len(kind.expressions) == 1
                and isinstance(kind.expressions[0], exp.DataType)
                and self._is_valid_iceberg_array_element_type(kind.expressions[0])
            )
        return True

    @staticmethod
    def _is_positive_integer_type_size(expression: exp.Expr) -> bool:
        if isinstance(expression, exp.DataTypeParam):
            expression = expression.this
        if not isinstance(expression, exp.Literal) or expression.is_string:
            return False
        value = expression.to_py()
        return type(value) is int and value > 0

    def externalprocedureparameter_sql(self, expression: vexp.ExternalProcedureParameter) -> str:
        kind = expression.args.get("kind")
        kind_sql = self.sql(kind)
        if not isinstance(kind, exp.DataType) or kind.expressions or kind.args.get("values"):
            self.unsupported("External PROCEDURE arguments require unparameterized scalar types")
        if kind_sql.upper() not in self.EXTERNAL_PROCEDURE_TYPES:
            self.unsupported(f"Unsupported external PROCEDURE argument type: {kind_sql}")

        name = self.sql(expression, "this")
        return f"{name} {kind_sql}" if name else kind_sql

    def externalproceduresignature_sql(self, expression: vexp.ExternalProcedureSignature) -> str:
        name = self.sql(expression, "this")
        if not name:
            self.unsupported("External PROCEDURE signatures require a name")
        return f"{name}({self.expressions(expression, flat=True)})"

    def createexternalprocedure_sql(self, expression: vexp.CreateExternalProcedure) -> str:
        signature = expression.args.get("this")
        executable = expression.args.get("executable")
        os_user = expression.args.get("os_user")
        if not isinstance(signature, vexp.ExternalProcedureSignature):
            self.unsupported("External PROCEDURE creation requires a typed signature")
        if not isinstance(executable, exp.Literal) or not executable.is_string:
            self.unsupported("External PROCEDURE executable must be a string")
        if not isinstance(os_user, exp.Literal) or not os_user.is_string:
            self.unsupported("External PROCEDURE USER must be a string")

        exists = " IF NOT EXISTS" if expression.args.get("exists") else ""
        clauses = [
            f"CREATE PROCEDURE{exists} {self.sql(signature)}",
            f"AS {self.sql(executable)}",
            "LANGUAGE 'EXTERNAL'",
            f"USER {self.sql(os_user)}",
        ]
        return self.sep().join(clauses)

    def dropexternalprocedure_sql(self, expression: vexp.DropExternalProcedure) -> str:
        signature = expression.args.get("this")
        if not isinstance(signature, vexp.ExternalProcedureSignature):
            self.unsupported("External DROP PROCEDURE requires a typed signature")
        if expression.args.get("cascade") or expression.args.get("restrict"):
            self.unsupported("External DROP PROCEDURE does not support CASCADE or RESTRICT")

        exists = " IF EXISTS" if expression.args.get("exists") else ""
        return f"DROP PROCEDURE{exists} {self.sql(signature)}"

    def verticacopy_sql(self, expression: vexp.VerticaCopy) -> str:
        hint = self.sql(expression, "hint")
        target = self.sql(expression, "this")
        if not target:
            self.unsupported("Vertica COPY requires a target table")
        return self._copy_definition_sql(expression, f"COPY{hint} {target}")

    def externalcopydefinition_sql(self, expression: vexp.ExternalCopyDefinition) -> str:
        self._validate_external_copy_generation(expression)
        return self._copy_definition_sql(expression, "COPY")

    def flexiblecopydefinition_sql(self, expression: vexp.FlexibleCopyDefinition) -> str:
        self._validate_external_copy_generation(expression)
        self._validate_flexible_copy_generation(expression)
        return self._copy_definition_sql(expression, "COPY")

    def _validate_external_copy_generation(self, expression: vexp.ExternalCopyDefinition) -> None:
        if expression.args.get("no_commit"):
            self.unsupported("External table COPY definitions do not support NO COMMIT")

        source = expression.args.get("source")
        if isinstance(source, vexp.CopyStdin) or (
            isinstance(source, vexp.CopyFiles) and source.args.get("local")
        ):
            self.unsupported("External table COPY definitions do not support LOCAL or STDIN")

        params = expression.args.get("params") or []
        names = [parameter.name for parameter in params if isinstance(parameter, exp.Expr)]
        unsupported = set(names).difference(self.EXTERNAL_COPY_PARAMETERS)
        if unsupported:
            self.unsupported(
                f"External table COPY definition does not support: {', '.join(sorted(unsupported))}"
            )
        if len(names) != len(set(names)):
            self.unsupported("External table COPY parameters cannot be repeated")

    def _validate_flexible_copy_generation(self, expression: vexp.FlexibleCopyDefinition) -> None:
        if expression.args.get("column_options"):
            self.unsupported("Flexible external tables do not support COLUMN OPTION")

        columns = expression.expressions
        if columns and not any(
            isinstance(column, vexp.CopyColumn)
            and column.name.lower() == "__raw__"
            and not column.args.get("expression")
            and not any(
                parameter.name == "FILLER"
                for parameter in column.args.get("params") or []
                if isinstance(parameter, exp.Expr)
            )
            for column in columns
        ):
            self.unsupported("Flexible COPY column lists require a plain __raw__ column")

        params = expression.args.get("params") or []
        names = [parameter.name for parameter in params if isinstance(parameter, exp.Expr)]
        unsupported = set(names).difference(self.FLEXIBLE_COPY_PARAMETERS)
        if unsupported:
            self.unsupported(
                f"Flexible external table COPY does not support: {', '.join(sorted(unsupported))}"
            )

        source = expression.args.get("source")
        if isinstance(source, vexp.CopyFromVertica):
            self.unsupported("Flexible external tables do not support FROM VERTICA")
        elif isinstance(source, vexp.CopyFiles):
            if source.args.get("partition_by"):
                self.unsupported("Flexible external tables do not support PARTITION COLUMNS")
            if any(
                isinstance(copy_file.args.get("on"), vexp.CopyNodeSelection)
                and copy_file.args["on"].args.get("kind") == "EACH"
                for copy_file in source.expressions
            ):
                self.unsupported("Flexible external tables do not support ON EACH NODE")
            if expression.args.get("format"):
                self.unsupported(
                    "Flexible external table files require a compatible PARSER, "
                    "not a built-in COPY format"
                )
            parser_parameters = [
                parameter
                for parameter in params
                if isinstance(parameter, exp.CopyParameter) and parameter.name == "PARSER"
            ]
            if len(parser_parameters) != 1 or not isinstance(
                parser_parameters[0].args.get("expression") if parser_parameters else None,
                vexp.CopyLoadFunction,
            ):
                self.unsupported("Flexible external table files require one compatible PARSER")
        elif isinstance(source, vexp.CopyUDL) and not isinstance(
            source.args.get("parser"), vexp.CopyLoadFunction
        ):
            self.unsupported("Flexible external table UDL pipelines require a PARSER")

    def _copy_definition_sql(
        self,
        expression: vexp.VerticaCopy | vexp.ExternalCopyDefinition,
        header: str,
    ) -> str:
        source = self.sql(expression, "source")
        if not source:
            self.unsupported("Vertica COPY requires a source")

        columns = self.expressions(expression, flat=True)
        columns = f" ({columns})" if columns else ""
        column_options = self.expressions(expression, key="column_options", flat=True)
        column_options = f" COLUMN OPTION ({column_options})" if column_options else ""

        clauses = [f"{header}{columns}{column_options}"]
        clauses.append(f"FROM {source}")

        source_format = self.sql(expression, "format")
        if source_format:
            clauses.append(source_format)

        params = self.expressions(expression, key="params", flat=True, sep=" ")
        if params:
            clauses.append(params)
        if expression.args.get("no_commit"):
            clauses.append("NO COMMIT")
        return self.sep().join(clauses)

    def copycolumn_sql(self, expression: vexp.CopyColumn) -> str:
        sql = self.sql(expression, "this")
        transformation = self.sql(expression, "expression")
        if transformation:
            sql += f" AS {transformation}"
        params = self.expressions(expression, key="params", flat=True, sep=" ")
        return f"{sql} {params}" if params else sql

    def copystdin_sql(self, expression: vexp.CopyStdin) -> str:
        local = "LOCAL " if expression.args.get("local") else ""
        compression = self.sql(expression, "compression")
        compression = f" {compression}" if compression else ""
        return f"{local}STDIN{compression}"

    def copyfiles_sql(self, expression: vexp.CopyFiles) -> str:
        local = "LOCAL " if expression.args.get("local") else ""
        files = self.expressions(expression, flat=True)
        partition_by = self.expressions(expression, key="partition_by", flat=True)
        partition_by = f" PARTITION COLUMNS {partition_by}" if partition_by else ""
        return f"{local}{files}{partition_by}"

    def copyfile_sql(self, expression: vexp.CopyFile) -> str:
        sql = self.sql(expression, "this")
        node = self.sql(expression, "on")
        if node:
            sql += f" ON {node}"
        compression = self.sql(expression, "compression")
        if compression:
            sql += f" {compression}"
        return sql

    def copynodeselection_sql(self, expression: vexp.CopyNodeSelection) -> str:
        kind = expression.args["kind"]
        if kind == "ANY":
            return "ANY NODE"
        if kind == "EACH":
            return "EACH NODE"
        if kind == "SET":
            return f"({self.expressions(expression, flat=True)})"
        return self.sql(expression, "this")

    def copyfromvertica_sql(self, expression: vexp.CopyFromVertica) -> str:
        columns = self.expressions(expression, flat=True)
        columns = f"({columns})" if columns else ""
        return f"VERTICA {self.sql(expression, 'this')}{columns}"

    def copyudl_sql(self, expression: vexp.CopyUDL) -> str:
        clauses = [f"SOURCE {self.sql(expression, 'this')}"]
        clauses.extend(
            f"FILTER {self.sql(filter_expression)}"
            for filter_expression in expression.args.get("filters") or []
        )
        parser = self.sql(expression, "parser")
        if parser:
            clauses.append(f"PARSER {parser}")
        return " ".join(clauses)

    def copyloadfunction_sql(self, expression: vexp.CopyLoadFunction) -> str:
        return f"{self.sql(expression, 'this')}({self.expressions(expression, flat=True)})"

    def copyformat_sql(self, expression: vexp.CopyFormat) -> str:
        name = self.sql(expression, "this")
        parameters = self.expressions(expression, flat=True)
        if not parameters:
            return name
        if expression.name.upper() == "FIXEDWIDTH":
            return f"{name} COLSIZES ({parameters})"
        if expression.name.upper() in {"ORC", "PARQUET"}:
            format_name = expression.name.upper()
            if not all(isinstance(parameter, exp.EQ) for parameter in expression.expressions):
                self.unsupported(f"Vertica {format_name} parameters require name=value")
                return f"{name}({parameters})"
            parameter_names = [parameter.this.name.upper() for parameter in expression.expressions]
            if len(parameter_names) != len(set(parameter_names)):
                self.unsupported(f"Vertica {format_name} parameters cannot be repeated")
            unsupported = set(parameter_names).difference(self.COPY_FORMAT_PARAMETERS[format_name])
            if unsupported:
                self.unsupported(
                    f"Unsupported Vertica {format_name} parameter: {', '.join(sorted(unsupported))}"
                )
            return f"{name}({parameters})"

        self.unsupported(f"Vertica COPY format {name} does not support parameters")
        return name

    def copyoutputtarget_sql(self, expression: vexp.CopyOutputTarget) -> str:
        node = self.sql(expression, "node")
        node = f" ON {node}" if node else ""
        return f"{self.sql(expression, 'this')}{node}"

    def copyparameter_sql(self, expression: exp.CopyParameter) -> str:
        name = self.sql(expression, "this")
        values = self.expressions(expression, flat=True)
        if values:
            return f"{name} {values}"
        value = self.sql(expression, "expression")
        return f"{name} {value}" if value else name

    def projectioncolumn_sql(self, expression: vexp.ProjectionColumn) -> str:
        this = self.sql(expression, "this")
        encoding = self.sql(expression, "encoding")
        access_rank = self.sql(expression, "access_rank")
        encoding = f" ENCODING {encoding}" if encoding else ""
        access_rank = f" ACCESSRANK {access_rank}" if access_rank else ""
        return f"{this}{encoding}{access_rank}"

    def datatype_sql(self, expression: exp.DataType) -> str:
        """Generate Vertica's bracketed collection and parenthesized row types."""

        if expression.this == exp.DType.INTERVAL:
            precision = self.expressions(expression, key="values", flat=True)
            precision = f"({precision})" if precision else ""
            qualifier = self.expressions(expression, flat=True)
            qualifier = f" {qualifier}" if qualifier else ""
            return f"INTERVAL{precision}{qualifier}"

        if expression.this in (exp.DType.ARRAY, exp.DType.SET):
            name = "ARRAY" if expression.this == exp.DType.ARRAY else "SET"
            element_type = self.expressions(expression, flat=True)
            bounds = self.expressions(expression, key="values", flat=True)
            if expression.args.get("kind"):
                bounds = f"({bounds})" if bounds else ""
                return f"{name}[{element_type}]{bounds}"
            bounds = f", {bounds}" if bounds else ""
            return f"{name}[{element_type}{bounds}]"

        if expression.this == exp.DType.STRUCT:
            return f"ROW({self.expressions(expression, flat=True)})"

        return super().datatype_sql(expression)

    def interval_sql(self, expression: exp.Interval) -> str:
        precision = self.sql(expression, "precision")
        precision = f"({precision})" if precision else ""
        this = self.sql(expression, "this")
        if this and not isinstance(expression.this, self.UNWRAPPED_INTERVAL_VALUES):
            this = f"({this})"
        unit = self.sql(expression, "unit")
        unit = f" {unit}" if unit else ""
        return f"INTERVAL{precision} {this}{unit}"

    def vertica_date_delta_sql(
        self, expression: exp.DateAdd | exp.DateDiff | exp.TsOrDsAdd | exp.TsOrDsDiff, name: str
    ) -> str:
        unit = expression.args.get("unit")
        if unit and not isinstance(unit, (exp.Var, exp.Literal, exp.Placeholder, exp.Paren)):
            unit = exp.Paren(this=unit)
        return self.func(
            name,
            unit,
            expression.expression,
            expression.this,
        )

    def currenttimestamp_sql(self, expression: exp.CurrentTimestamp) -> str:
        precision = self.sql(expression, "this")
        return f"CURRENT_TIMESTAMP({precision})" if precision else "CURRENT_TIMESTAMP"

    def timeslice_sql(self, expression: exp.TimeSlice) -> str:
        unit = expression.args.get("unit")
        if isinstance(unit, exp.Var):
            unit = exp.Literal.string(unit.name)
        return self.func(
            "TIME_SLICE",
            expression.this,
            expression.expression,
            unit,
            expression.args.get("kind"),
        )

    def ignorenulls_sql(self, expression: exp.IgnoreNulls) -> str:
        return Generator.ignorenulls_sql(self, expression)

    def respectnulls_sql(self, expression: exp.RespectNulls) -> str:
        return Generator.respectnulls_sql(self, expression)

    def interpolate_sql(self, expression: vexp.Interpolate) -> str:
        direction = self.sql(expression, "direction").upper()
        return (
            f"{self.sql(expression, 'this')} INTERPOLATE {direction} VALUE "
            f"{self.sql(expression, 'expression')}"
        )

    def partitionedlimit_sql(self, expression: vexp.PartitionedLimit) -> str:
        count = self.sql(expression, "expression")
        partition_by = self.expressions(expression, key="partition_by", flat=True)
        partition_by = f"PARTITION BY {partition_by} " if partition_by else ""
        order = self.sql(expression, "order").lstrip()
        return f"{self.seg('LIMIT')} {count} OVER ({partition_by}{order})"

    def matchdefinition_sql(self, expression: vexp.MatchDefinition) -> str:
        return f"{self.sql(expression, 'this')} AS {self.sql(expression, 'expression')}"

    def vertica_match_sql(self, expression: vexp.Match) -> str:
        partition_by = self.expressions(expression, key="partition_by", flat=True)
        partition_by = f"PARTITION BY {partition_by}" if partition_by else ""
        order = self.sql(expression, "order").lstrip()
        definitions = self.expressions(expression, key="definitions", flat=True)
        definitions = f"DEFINE {definitions}" if definitions else ""
        pattern_name = self.sql(expression, "pattern_name")
        pattern = self.sql(expression, "pattern")
        rows_match = self.sql(expression, "rows_match")

        clauses = [clause for clause in (partition_by, order, definitions) if clause]
        clauses.append(f"PATTERN {pattern_name} AS ({pattern})")
        if rows_match:
            clauses.append(f"ROWS MATCH {rows_match}")
        return f"{self.seg('MATCH')} ({' '.join(clauses)})"

    def projectionsegmentation_sql(self, expression: vexp.ProjectionSegmentation) -> str:
        if expression.args["segmented"]:
            sql = f"SEGMENTED BY {self.sql(expression, 'this')}"
        else:
            sql = "UNSEGMENTED"

        if expression.args.get("all_nodes"):
            sql += " ALL NODES"
        elif expression.args.get("nodes"):
            sql += f" NODES {self.expressions(expression, key='nodes', flat=True)}"

        offset = self.sql(expression, "offset")
        if offset:
            sql += f" OFFSET {offset}"
        return sql

    def createprojection_sql(self, expression: vexp.CreateProjection) -> str:
        replace = " OR REPLACE" if expression.args.get("replace") else ""
        exists = " IF NOT EXISTS" if expression.args.get("exists") else ""
        name = self.sql(expression, "this")

        columns = self.expressions(expression, key="columns")
        columns = f"{self.sep()}{self.wrap(columns)}" if columns else ""

        query = self.sql(expression, "expression")
        order = self.sql(expression, "order").lstrip()
        segmentation = self.sql(expression, "segmentation")
        ksafe = self.sql(expression, "ksafe")

        clauses = [f"CREATE{replace} PROJECTION{exists} {name}{columns}", f"AS{self.seg(query)}"]
        if order:
            clauses.append(order)
        if segmentation:
            clauses.append(segmentation)
        if ksafe:
            clauses.append(f"KSAFE {ksafe}")

        return self.sep().join(clauses)

    def timeseries_sql(self, expression: vexp.Timeseries) -> str:
        slice_name = self.sql(expression, "this")
        slice_interval = self.sql(expression, "expression")
        partition_by = self.expressions(expression, key="partition_by", flat=True)
        partition_by = f"PARTITION BY {partition_by} " if partition_by else ""
        order = self.sql(expression, "order").lstrip()
        return (
            f"{self.seg('TIMESERIES')} {slice_name} AS {slice_interval} "
            f"OVER ({partition_by}{order})"
        )

    def options_modifier(self, expression: exp.Expr) -> str:
        """Hide internal WITH materialization barriers from Vertica SQL."""

        options = [
            option
            for option in expression.args.get("options") or []
            if not isinstance(option, vexp.MaterializedWithMarker)
        ]
        options_sql = self.expressions(sqls=options)
        return f" {options_sql}" if options_sql else ""

    def query_modifiers(self, expression: exp.Expr, *sqls: str) -> str:
        """Emit TIMESERIES in Vertica's position after WHERE and before GROUP BY."""

        limit = expression.args.get("limit")
        if self.LIMIT_FETCH == "LIMIT" and isinstance(limit, exp.Fetch):
            count = limit.args.get("count")
            limit = exp.Limit(
                expression=exp.maybe_copy(count) if count is not None else exp.Literal.number(1)
            )
        elif self.LIMIT_FETCH == "FETCH" and isinstance(limit, exp.Limit):
            limit = exp.Fetch(direction="FIRST", count=exp.maybe_copy(limit.expression))

        return csv(
            *sqls,
            *[self.sql(join) for join in expression.args.get("joins") or []],
            *[self.sql(lateral) for lateral in expression.args.get("laterals") or []],
            self.sql(expression, "prewhere"),
            self.sql(expression, "where"),
            self.sql(expression, "timeseries"),
            self.sql(expression, "connect"),
            self.sql(expression, "group"),
            self.sql(expression, "having"),
            self.sql(expression, "match"),
            *[gen(self, expression) for gen in self.AFTER_HAVING_MODIFIER_TRANSFORMS.values()],
            self.sql(expression, "order"),
            *self.offset_limit_modifiers(expression, isinstance(limit, exp.Fetch), limit),
            *self.after_limit_modifiers(expression),
            self.options_modifier(expression),
            self.sql(expression, "for_"),
            sep="",
        )
