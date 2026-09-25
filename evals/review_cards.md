# Eval review cards

Review the proposed class for each real-data case. This is about whether the candidate domain is associated with the observed service, **not** whether a vulnerability is confirmed, the company owns the IP, or it intends to buy.

- `supported`: host/certificate evidence supports a service-to-domain association.
- `needs_review`: there is a clue, but shared infrastructure, a conflict, or a missing ownership link needs research.
- `insufficient_evidence`: the observation does not meaningfully link the service to the candidate.

The cases are split into development and held-out sets. Please review the proposed labels and tell me which IDs you would change; do not edit the held-out prompts after seeing the labels.

## S01 · ahk.nl

**Proposed:** `supported` · **Split:** development

- HTTP host: `cnvas.ahk.nl`; certificate: `cnvas.ahk.nl`
- Page title: Welkom bij CnVAs
- Infrastructure organisation: DigitalOcean, LLC; product: nginx
- Dataset vulnerability labels: 4 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-5591478`
- Why proposed: HTTP host and certificate both name a subdomain of the candidate.

## S02 · sdmujer.gov.co

**Proposed:** `supported` · **Split:** development

- HTTP host: `capacitacionesdesanew.sdmujer.gov.co`; certificate: `*.sdmujer.gov.co`
- Page title: Página Principal | LMSSDMUJER
- Infrastructure organisation: Oracle Corporation; product: Apache httpd
- Dataset vulnerability labels: 164 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-10052589`
- Why proposed: Candidate subdomain appears in HTTP host and wildcard certificate.

## S03 · techlinkit.com.au

**Proposed:** `supported` · **Split:** development

- HTTP host: `techlinkit.com.au`; certificate: `techlinkit.com.au`
- Page title: TechLink IT Solutions | SEQ IT Specialists | Linking Business and IT together
- Infrastructure organisation: Cloudflare, Inc.; product: missing
- Dataset vulnerability labels: 2 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-5104791`
- Why proposed: Exact candidate domain in HTTP host and certificate, with matching page title.

## S04 · qasource.com

**Proposed:** `supported` · **Split:** development

- HTTP host: `whm.qasource.com`; certificate: `webmail.qasource.com`
- Page title: WHM Login
- Infrastructure organisation: InMotion Hosting, Inc.; product: WHM
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-2172695`
- Why proposed: Web management host and certificate share the candidate domain.

## S05 · ito-e.co.jp

**Proposed:** `supported` · **Split:** development

- HTTP host: `www.ito-e.co.jp`; certificate: `ito-e.co.jp`
- Page title: 302 Found
- Infrastructure organisation: Open Computer Network; product: Apache httpd
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-6434172`
- Why proposed: Website host and certificate agree on the candidate domain.

## S06 · thebrooklynbrothers.com

**Proposed:** `supported` · **Split:** held_out

- HTTP host: `sociallistening.thebrooklynbrothers.com`; certificate: `sociallistening.thebrooklynbrothers.com`
- Page title: 404 Not Found
- Infrastructure organisation: DigitalOcean, LLC; product: Apache httpd
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-7425921`
- Why proposed: Specific subdomain and certificate agree despite uninformative 404 title.

## S07 · southwales.ac.uk

**Proposed:** `supported` · **Split:** held_out

- HTTP host: `health.research.southwales.ac.uk`; certificate: `southwales.ac.uk`
- Page title: Attention Required! | Cloudflare
- Infrastructure organisation: Cloudflare, Inc.; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-3437625`
- Why proposed: Subdomain and certificate agree; CDN ownership is separate from domain association.

## S08 · gutedizioni.it

**Proposed:** `supported` · **Split:** held_out

- HTTP host: `erp.gutedizioni.it`; certificate: `gutedizioni.it`
- Page title: gutedizioni.it | 521: Web server is down
- Infrastructure organisation: Cloudflare, Inc.; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-3404597`
- Why proposed: Subdomain and certificate agree even though page reports an origin error.

## R01 · mybigcommerce.com

**Proposed:** `needs_review` · **Split:** development

- HTTP host: `store-vpyn8kombe.mybigcommerce.com`; certificate: `*.mybigcommerce.com`
- Page title: Garrett Popcorn Shops® | Chicago&#x27;s True Original Gourmet Popcorn
- Infrastructure organisation: Bigcommerce Inc.; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-617470`
- Why proposed: Shared commerce platform domain and certificate do not identify the merchant account.

## R02 · memberclicks.net

**Proposed:** `needs_review` · **Split:** development

- HTTP host: `rahma.memberclicks.net`; certificate: `memberclicks.net`
- Page title: Home
- Infrastructure organisation: Cloudflare, Inc.; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-4214944`
- Why proposed: Shared association-platform domain does not identify the tenant organisation.

## R03 · sony.com.mx

**Proposed:** `needs_review` · **Split:** development

- HTTP host: `missing`; certificate: `store.sony.com.mx`
- Page title: missing
- Infrastructure organisation: Incapsula Inc; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-1290466`
- Why proposed: Certificate references the candidate but HTTP host and operator remain unclear.

## R04 · perforce.com

**Proposed:** `needs_review` · **Split:** development

- HTTP host: `perforce.datagrail.io`; certificate: `preferences.perforce.com`
- Page title: missing
- Infrastructure organisation: Amazon.com, Inc.; product: nginx
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-6384489`
- Why proposed: Certificate names candidate but HTTP host points to another service domain.

## R05 · cloudezapp.io

**Proposed:** `needs_review` · **Split:** development

- HTTP host: `ip-96-126-120-201.cloudezapp.io`; certificate: `missing`
- Page title: ip-96-126-120-201.cloudezapp.io
- Infrastructure organisation: Linode; product: nginx
- Dataset vulnerability labels: 3 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-1553696`
- Why proposed: Candidate HTTP host exists but certificate is absent; vulnerability labels do not settle ownership.

## R06 · toyota-ess.com

**Proposed:** `needs_review` · **Split:** held_out

- HTTP host: `23.48.64.99`; certificate: `*.toyota-ess.com`
- Page title: Invalid URL
- Infrastructure organisation: Akamai Technologies, Inc.; product: AkamaiGHost
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-1395673`
- Why proposed: Candidate wildcard certificate sits behind Akamai with an IP host and invalid URL page.

## R07 · pair.com

**Proposed:** `needs_review` · **Split:** held_out

- HTTP host: `missing`; certificate: `*.pair.com`
- Page title: missing
- Infrastructure organisation: pair Networks; product: Postfix smtpd
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `True`; known provider domain `False`
- Source evidence ID: `source-line-7253401`
- Why proposed: Mail certificate names a hosting platform, not a specific tenant business.

## R08 · switchcraft.com

**Proposed:** `needs_review` · **Split:** held_out

- HTTP host: `107.154.123.136`; certificate: `imperva.com`
- Page title: missing
- Infrastructure organisation: Incapsula Inc; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-7127446`
- Why proposed: Candidate domain appears in DNS list but provider certificate and IP host conflict.

## R09 · cloudfront.net

**Proposed:** `needs_review` · **Split:** held_out

- HTTP host: `d3owwq2i9dkgid.cloudfront.net`; certificate: `missing`
- Page title: 301 Moved Permanently
- Infrastructure organisation: Amazon.com, Inc.; product: CloudFront httpd
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `True`; certificate match `False`; known provider domain `True`
- Source evidence ID: `source-line-141514`
- Why proposed: Platform domain and service host could hide a customer; buyer identity requires research.

## I01 · cosmic.global

**Proposed:** `insufficient_evidence` · **Split:** development

- HTTP host: `216.39.241.85`; certificate: `missing`
- Page title: kube-state-metrics
- Infrastructure organisation: Gameserverkings; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-7207933`
- Why proposed: Only an IP host and generic metrics title; no direct candidate-domain link.

## I02 · jago-ag.de

**Proposed:** `insufficient_evidence` · **Split:** development

- HTTP host: `168.119.165.93`; certificate: `missing`
- Page title: missing
- Infrastructure organisation: Hetzner Online GmbH; product: Ncat http proxy
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-4656801`
- Why proposed: IP host and generic proxy product do not identify candidate operator.

## I03 · batelco.jo

**Proposed:** `insufficient_evidence` · **Split:** development

- HTTP host: `missing`; certificate: `missing`
- Page title: missing
- Infrastructure organisation: Batelco Jordan; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-9170562`
- Why proposed: Candidate is in DNS list but host, certificate and title are absent.

## I04 · above.com

**Proposed:** `insufficient_evidence` · **Split:** development

- HTTP host: `careercenter.protectionfirstsecurity.com`; certificate: `missing`
- Page title: protectionfirstsecurity.com
- Infrastructure organisation: Trellian Pty. Limited; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-1168313`
- Why proposed: HTTP host and certificate concern another business, not candidate domain.

## I05 · bluefin.com

**Proposed:** `insufficient_evidence` · **Split:** development

- HTTP host: `192.230.79.136`; certificate: `imperva.com`
- Page title: missing
- Infrastructure organisation: Incapsula Inc; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-9917172`
- Why proposed: Provider certificate and IP host do not support candidate-domain association.

## I06 · dnsmadeeasy.com

**Proposed:** `insufficient_evidence` · **Split:** held_out

- HTTP host: `96.45.83.146`; certificate: `missing`
- Page title: missing
- Infrastructure organisation: Tiggee LLC; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-9526310`
- Why proposed: DNS-provider domain with IP host and no customer-specific evidence.

## I07 · gigainternet.pl

**Proposed:** `insufficient_evidence` · **Split:** held_out

- HTTP host: `missing`; certificate: `missing`
- Page title: missing
- Infrastructure organisation: FIRMA HANDLOWA GIGA ARKADIUSZ KOCMA; product: missing
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-7172166`
- Why proposed: No service host or certificate naming candidate.

## I08 · foxplay.com

**Proposed:** `insufficient_evidence` · **Split:** held_out

- HTTP host: `23.210.131.73`; certificate: `ficfiles.com`
- Page title: Invalid URL
- Infrastructure organisation: Akamai Technologies, Inc.; product: AkamaiGHost
- Dataset vulnerability labels: 0 (association count, not a verified finding)
- Rule flags: HTTP match `False`; certificate match `False`; known provider domain `False`
- Source evidence ID: `source-line-2026477`
- Why proposed: HTTP host is IP and certificate names unrelated domain.
