-- One normalized candidate domain can occur only once per source observation.
select candidate_domain, source_record_id
from {{ ref('int_account_evidence') }}
group by 1, 2
having count(*) > 1
