#### Start here

WeLook helps sales teams selling external attack-surface monitoring choose domains to research. An **observation** is a historical record of an internet-facing service. A **candidate domain** groups related observations; it is not a verified company.

1. Start with the **Review queue** and select a domain.
2. Read why it appears, its next research step, and the source evidence. AI summaries appear only where one has been published.
3. **Add to shortlist**, record what you checked, and save the research update. To mark **Ready for sales review**, add a company name and the HTTPS page supporting that identity.
4. Download the **research brief CSV** from the sidebar. Shortlists and notes last only for this browser session.

#### What the filters do

Filters work together. **Reset filters** returns to the default queue and keeps your shortlist. The table shows at most 100 matches from the hosted subset.

| Filter | Meaning |
| --- | --- |
| **Find a domain** | Search part of a candidate domain name. Other filters still apply. |
| **Queue** | **Review queue** combines Investigate first and Review next. **All candidates** includes every priority tier in the hosted subset. **Investigate first**, **Review next**, and **Needs research** show one tier. **AI suggestions** shows domains with a published AI summary; it does not mean higher priority. |
| **Why it surfaced** | Filter by a scanner signal or an observed admin/login page. **Strong scanner-verified signal** also requires a strong domain link. Scanner findings still need checking. |
| **Observed product** | Search a scanner-reported product name, such as cPanel. It searches only the selected observations shown in the app, so a missing result does not prove the product is absent. |

The **Domain link** column explains how the candidate domain relates to the service. **Strong** means both the website host and certificate match. **Partial** means one matches. **Weak** means neither directly matches. **Infrastructure provider** means the domain is on the known-provider list. None of these labels verifies a legal company or current service operator.

#### Priority and evidence score

- **Investigate first:** both domain fields match and the same observation carries a scanner-verified label.
- **Review next:** both fields match and the same observation carries an unverified scanner label, with no directly matched verified label.
- **Needs research:** weaker evidence, such as a one-field match with scanner labels or an admin/login title.
- **Low evidence:** remaining candidates, available through All candidates. Low evidence does not mean secure.

Priority sorts first. Within a tier, a higher **evidence score** puts stronger observations earlier. The score adds 20 for each matching domain field, 30 for a scanner-verified label (otherwise 5 for unverified metadata), 10 for an admin/login title, and 5 for a recorded product field. A domain uses its highest observation score, not the sum of its services. The formula can produce 0–85; this full run observed 0–75. This is not a risk percentage or likelihood to buy.

#### Reading the evidence

A **scanner label** is a potential finding reported in the dataset. A **CVE** ID identifies a catalogued vulnerability; seeing one does not prove it applies here. “Verified” preserves the scanner's flag, not a new verification by WeLook. A login page alone is not a vulnerability.

An **AI research summary** combines the selected evidence into a short explanation and suggested check. The prompt version, model, source IDs, and review status remain in the engineering traces instead of the sales screen. AI summaries are advisory and never change the priority.

This historical snapshot cannot establish current exposure, legal ownership, buying intent, or named contacts. A server's country is not the company's territory. Confirm the business, current service operator, and technical finding before outreach.
