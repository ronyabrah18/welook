{{ config(materialized='table') }}

-- Candidate domain is an evidence label, not a resolved legal company.
with expanded as (
    select o.source_record_id, o.source_line, o.observation_id, o.observed_at, o.ip_address,
           o.port, o.infrastructure_org, o.infrastructure_country, o.product,
           o.http_host, o.http_title, o.certificate_cn, o.vulnerability_count,
           o.verified_vulnerability_count,
           lower(trim(d.domain)) as candidate_domain
    from {{ ref('stg_observations') }} o, unnest(o.domains) as d(domain)
), cleaned as (
    select *,
        lower(split_part(coalesce(http_host, ''), ':', 1)) as clean_http_host,
        regexp_replace(lower(coalesce(certificate_cn, '')), '^[*][.]', '') as clean_cert_cn,
        regexp_matches(lower(coalesce(http_title, '')), '(admin|management|dashboard|sign in|login)') as admin_or_login_title
    from expanded
    where regexp_matches(candidate_domain, '^[a-z0-9][a-z0-9.-]*[.][a-z]{2,}$')
), assessed as (
    select *,
        regexp_matches(candidate_domain,
            '(^|[.])(amazonaws[.]com|cloudfront[.]net|googleusercontent[.]com|incapdns[.]net|akamaitechnologies[.]com|contaboserver[.]net|awsglobalaccelerator[.]com|hwclouds-dns[.]com|linodeusercontent[.]com|ovh[.]net|scw[.]cloud|vultrusercontent[.]com|your-server[.]de|flyio[.]net|mybigcommerce[.]com|memberclicks[.]net|pair[.]com|shop-pro[.]jp|exblog[.]jp|1blu[.]de)$'
        ) as listed_provider_domain,
        (clean_http_host = candidate_domain or ends_with(clean_http_host, '.' || candidate_domain)) as http_domain_match,
        (clean_cert_cn = candidate_domain or ends_with(clean_cert_cn, '.' || candidate_domain)) as cert_domain_match
    from cleaned
)
select source_record_id, source_line, observation_id, observed_at, ip_address, port,
       infrastructure_org, infrastructure_country, product, http_host, http_title,
       certificate_cn, vulnerability_count, verified_vulnerability_count,
       candidate_domain, listed_provider_domain,
       http_domain_match, cert_domain_match, admin_or_login_title,
       case when listed_provider_domain then 'provider_only'
            when http_domain_match and cert_domain_match then 'supported'
            when http_domain_match or cert_domain_match then 'partial'
            else 'unresolved' end as attribution_status,
       least(100, 20 * (http_domain_match::integer + cert_domain_match::integer)
           + case when verified_vulnerability_count > 0 then 30
                  when vulnerability_count > 0 then 5 else 0 end
           + case when admin_or_login_title then 10 else 0 end
           + case when product is not null then 5 else 0 end) as evidence_score
from assessed
