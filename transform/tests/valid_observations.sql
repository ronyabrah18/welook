-- A dbt data test fails when this query returns rows.
select observation_id
from {{ ref('stg_observations') }}
where port is null or port < 0 or port > 65535
   or ip_address is null or source_line < 1
   or not json_valid(vulnerabilities_json)
