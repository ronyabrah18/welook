# Account-association label review

These 25 labels are draft judgements over the supplied evidence, not verified legal ownership. Review the `expected` label and rationale before using them as a hand-labelled evaluation set. The JSONL file contains the exact evidence bundle for each case.

| ID | Split | Candidate domain | Expected | Why |
| --- | --- | --- | --- | --- |
| S01 | development | ahk.nl | supported | HTTP host and certificate both name a subdomain of the candidate. |
| S02 | development | sdmujer.gov.co | supported | Candidate subdomain appears in HTTP host and wildcard certificate. |
| S03 | development | techlinkit.com.au | supported | Exact candidate domain in HTTP host and certificate, with matching page title. |
| S04 | development | qasource.com | supported | Web management host and certificate share the candidate domain. |
| S05 | development | ito-e.co.jp | supported | Website host and certificate agree on the candidate domain. |
| S06 | held_out | thebrooklynbrothers.com | supported | Specific subdomain and certificate agree despite uninformative 404 title. |
| S07 | held_out | southwales.ac.uk | supported | Subdomain and certificate agree; CDN ownership is separate from domain association. |
| S08 | held_out | gutedizioni.it | supported | Subdomain and certificate agree even though page reports an origin error. |
| R01 | development | mybigcommerce.com | needs_review | Shared commerce platform domain and certificate do not identify the merchant account. |
| R02 | development | memberclicks.net | needs_review | Shared association-platform domain does not identify the tenant organisation. |
| R03 | development | sony.com.mx | needs_review | Certificate references the candidate but HTTP host and operator remain unclear. |
| R04 | development | perforce.com | needs_review | Certificate names candidate but HTTP host points to another service domain. |
| R05 | development | cloudezapp.io | needs_review | Candidate HTTP host exists but certificate is absent; vulnerability labels do not settle ownership. |
| R06 | held_out | toyota-ess.com | needs_review | Candidate wildcard certificate sits behind Akamai with an IP host and invalid URL page. |
| R07 | held_out | pair.com | needs_review | Mail certificate names a hosting platform, not a specific tenant business. |
| R08 | held_out | switchcraft.com | needs_review | Candidate domain appears in DNS list but provider certificate and IP host conflict. |
| R09 | held_out | cloudfront.net | needs_review | Platform domain and service host could hide a customer; buyer identity requires research. |
| I01 | development | cosmic.global | insufficient_evidence | Only an IP host and generic metrics title; no direct candidate-domain link. |
| I02 | development | jago-ag.de | insufficient_evidence | IP host and generic proxy product do not identify candidate operator. |
| I03 | development | batelco.jo | insufficient_evidence | Candidate is in DNS list but host, certificate and title are absent. |
| I04 | development | above.com | insufficient_evidence | HTTP host and certificate concern another business, not candidate domain. |
| I05 | development | bluefin.com | insufficient_evidence | Provider certificate and IP host do not support candidate-domain association. |
| I06 | held_out | dnsmadeeasy.com | insufficient_evidence | DNS-provider domain with IP host and no customer-specific evidence. |
| I07 | held_out | gigainternet.pl | insufficient_evidence | No service host or certificate naming candidate. |
| I08 | held_out | foxplay.com | insufficient_evidence | HTTP host is IP and certificate names unrelated domain. |
