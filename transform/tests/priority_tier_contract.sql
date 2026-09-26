-- A login/admin title alone must not promote a candidate to the strongest tier.
select candidate_domain
from {{ ref('fct_accounts') }}
where (priority_tier = 'investigate_first'
       and (attribution_status <> 'supported' or directly_supported_verified_observation_count = 0))
   or (attribution_status = 'supported'
       and directly_supported_verified_observation_count = 0
       and admin_or_login_observation_count > 0
       and priority_tier <> 'research')
