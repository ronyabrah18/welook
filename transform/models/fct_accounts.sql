{{ config(materialized='table') }}

with grouped as (
    select candidate_domain,
           count(distinct observation_id) as observation_count,
           count(distinct case when attribution_status = 'supported' then observation_id end) as supported_observation_count,
           count(distinct case when vulnerability_count > 0 then observation_id end) as vulnerability_association_count,
           count(distinct case when verified_vulnerability_count > 0 then observation_id end) as verified_vulnerability_association_count,
           count(distinct case when admin_or_login_title then observation_id end) as admin_or_login_observation_count,
           min(observed_at) as first_observed_at,
           max(observed_at) as last_observed_at,
           max(evidence_score) as investigation_score,
           max(case when attribution_status = 'supported' then 3
                    when attribution_status = 'partial' then 2
                    when attribution_status = 'unresolved' then 1 else 0 end) as attribution_rank,
           bool_and(listed_provider_domain) as provider_domain,
           arg_max(nullif(http_title, ''), evidence_score) as example_http_title,
           arg_max(nullif(product, ''), evidence_score) as example_product
    from {{ ref('int_account_evidence') }}
    group by candidate_domain
)
select candidate_domain, observation_count, supported_observation_count,
       vulnerability_association_count, verified_vulnerability_association_count,
       admin_or_login_observation_count,
       first_observed_at, last_observed_at, investigation_score, provider_domain,
       example_http_title, example_product,
       case attribution_rank when 3 then 'supported' when 2 then 'partial'
            when 1 then 'unresolved' else 'provider_only' end as attribution_status,
       case when attribution_rank = 3 and
                 (verified_vulnerability_association_count > 0 or admin_or_login_observation_count > 0)
                 then 'investigate_first'
            when attribution_rank >= 2 and
                 (vulnerability_association_count > 0 or admin_or_login_observation_count > 0)
                 then 'research'
            else 'low_evidence' end as priority_tier,
       case when attribution_rank = 0 then 'Check whether this is only provider infrastructure'
            when attribution_rank < 3 then 'Verify which business operates the observed service'
            when verified_vulnerability_association_count > 0 then 'Review scanner-verified vulnerability evidence before outreach'
            when vulnerability_association_count > 0 then 'Validate the unverified vulnerability association'
            when admin_or_login_observation_count > 0 then 'Confirm the exposed interface and find the security owner'
            else 'Research security ownership and current priorities' end as next_action
from grouped
