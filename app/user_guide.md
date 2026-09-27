#### Start here

WeLook helps sales teams selling external attack-surface monitoring choose domains to research. An **observation** is a historical record of an internet-facing service. A **candidate domain** groups related observations; it is not a verified company.

1. Start with the **Review queue** and select a domain.
2. Read why it appears, its next research step, and the source evidence. AI notes appear only where a note has been published.
3. **Add to shortlist**, record what you checked, and save the research update. To mark **Ready for sales review**, add a company name and the HTTPS page supporting that identity.
4. Download the **research brief CSV** from the sidebar. Shortlists and notes last only for this browser session.

#### What the filters do

Filters work together. **Reset filters** returns to the default queue and keeps your shortlist. The table shows at most 100 matches from the hosted subset.

| Filter | Meaning |
| --- | --- |
| **Find a domain** | Search part of a candidate domain name. Other filters still apply. |
| **View** | **Review queue** combines Investigate first and Review next. **All candidates** includes every priority tier in the hosted subset. **Investigate first**, **Review next**, and **Needs research** show that tier only. **AI notes** shows domains with a published note; it does not mean higher priority. |
| **Technical signal** | **Any signal** adds no restriction. **Direct verified label** requires a scanner-verified label and both domain matches on the same observation. **Any scanner-verified label** also includes weaker domain links. **Admin/login page** means the page title mentions an administration or login interface. **Vulnerability metadata** means the scanner listed at least one vulnerability label, verified or unverified. |
| **Direct domain matches only** | Keep domains where both the website host and certificate name match on an observation, excluding known provider-only domains. This does not verify the business operating the service. |
| **Evidence match** | **Both fields match** means website host and certificate match; **One field matches** means only one does; **No direct match** means neither does. **Known provider domain** means the domain is on the provider list. **Any match** adds no restriction. A provider classification takes precedence. |
| **Product in selected evidence** | Search a scanner-reported product name, such as cPanel. It searches only the up-to-three observations retained per domain, so a missing result does not prove the product is absent. |

#### Priority and research score

- **Investigate first:** both domain fields match and the same observation carries a scanner-verified label.
- **Review next:** both fields match and the same observation carries an unverified scanner label, with no directly matched verified label.
- **Needs research:** weaker evidence, such as a one-field match with scanner labels or an admin/login title.
- **Low evidence:** remaining candidates, available through All candidates. Low evidence does not mean secure.

Priority sorts first. Within a tier, a higher **research score** puts stronger observations earlier. The score adds 20 for each matching domain field, 30 for a scanner-verified label (otherwise 5 for unverified metadata), 10 for an admin/login title, and 5 for a recorded product field. A domain uses its highest observation score, not the sum of its services. Current scores range from 0 to 85. This is not a risk percentage or likelihood to buy.

#### Reading the evidence

A **scanner label** is a potential finding reported in the dataset. A **CVE** ID identifies a catalogued vulnerability; seeing one does not prove it applies here. “Verified” preserves the scanner's flag, not a new verification by WeLook. A login page alone is not a vulnerability.

This historical snapshot cannot establish current exposure, legal ownership, buying intent, or named contacts. A server's country is not the company's territory. AI notes are advisory and never change the priority. Confirm the business, current service operator, and technical finding before outreach.
