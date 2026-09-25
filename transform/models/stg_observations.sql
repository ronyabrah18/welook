{{ config(materialized='table') }}

-- One row per distinct source-record content hash. Preserve observation time:
-- repeated observations at different times are not interchangeable duplicates.
with ranked as (
    select *, row_number() over (
        partition by observation_id order by source_line
    ) as duplicate_rank
    from {{ source('raw', 'observations') }}
)
select * exclude (duplicate_rank),
       case when vulnerabilities_json is null then 0 else
           (select count(*) from json_each(ranked.vulnerabilities_json) v
            where json_extract_string(v.value, '$.verified') = 'true') end
           as verified_vulnerability_count
from ranked
where duplicate_rank = 1
