-- Unsupported expression type LocalProperty
create local temp table t_local on commit preserve rows as select 1 as c;

-- Unsupported expression type PartitionedLimit
select 1 as x limit 1 over (partition by x order by x);

-- Unsupported expression type StatementTimestamp
select getdate();

-- Unsupposrted expression type UtcStatementTimestamp
select getutcdate();

-- Unsupported expression type VerticaOrdered
select row_number() over (order by 1 asc nulls last) as rn;

-- Unsupported expression type VerticaRegexpLike
select regexp_like('abc', 'a');

-- Unsupported expression type VerticaToChar
select to_char(year(current_date) - 2);
