-- One row per distinct source-record content hash. Preserve observation time:
-- repeated observations at different times are not interchangeable duplicates.
with ranked as (
    select *, row_number() over (
        partition by observation_id order by source_line
    ) as duplicate_rank
    from {{ source('raw', 'observations') }}
)
select * exclude (duplicate_rank)
from ranked
where duplicate_rank = 1
