"""Check the hosted snapshot supports the salesperson's core research flow."""

import unittest
import json
import csv
from io import StringIO

import duckdb

from streamlit.testing.v1 import AppTest

from scripts.ingest_full import ROOT
from app.handoff import shortlist_csv


class AppFlowTest(unittest.TestCase):
    def test_every_review_next_account_shows_its_qualifying_signal(self):
        with duckdb.connect(str(ROOT / "app" / "data" / "welook_serving.duckdb"), read_only=True) as con:
            total, visible, with_ids = con.execute("""
                SELECT count(*), count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM evidence e
                    WHERE e.candidate_domain = a.candidate_domain
                      AND e.http_domain_match AND e.cert_domain_match
                      AND e.vulnerability_count > 0
                )), count(*) FILTER (WHERE EXISTS (
                    SELECT 1 FROM evidence e
                    WHERE e.candidate_domain = a.candidate_domain
                      AND e.http_domain_match AND e.cert_domain_match
                      AND e.vulnerability_count > 0 AND len(e.scanner_label_ids) > 0
                ))
                FROM accounts a WHERE a.priority_tier = 'review_next'
            """).fetchone()
        self.assertGreater(total, 0)
        self.assertEqual(visible, total)
        self.assertEqual(with_ids, total)

    def test_every_investigate_first_domain_has_reviewed_note(self):
        with duckdb.connect(str(ROOT / "app" / "data" / "welook_serving.duckdb"), read_only=True) as con:
            priority, with_note = con.execute("""
                SELECT count(*), count(assessment.candidate_domain)
                FROM accounts account LEFT JOIN assessments assessment USING (candidate_domain)
                WHERE account.priority_tier = 'investigate_first'
            """).fetchone()
        self.assertEqual(priority, 7)
        self.assertEqual(with_note, priority)

    def test_ai_note_can_be_found_and_shortlisted(self):
        app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertIn("Explore candidates", [heading.value for heading in app.subheader])

        view = next(control for control in app.selectbox if control.label == "View")
        self.assertEqual(view.value, "Review queue")
        self.assertTrue(set(app.dataframe[0].value["Priority"]) <= {"Investigate First", "Review Next"})
        view.set_value("AI notes").run()
        self.assertFalse(app.exception)
        report = json.loads((ROOT / "app" / "data" / "serving_report.json").read_text())
        self.assertEqual(len(app.dataframe[0].value), report["ai_assessed_accounts"])
        self.assertTrue(any("AI research note" in item.value for item in app.info))

        next(button for button in app.button if button.label == "Add to shortlist").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["shortlist"]), 1)

        next(control for control in app.selectbox if control.label == "Research status")\
            .set_value("Verify operator").run()
        next(control for control in app.text_area if control.label == "What you checked or need to check")\
            .set_value("Confirm the service operator before any outreach.").run()
        next(button for button in app.button if button.label == "Save research update").click().run()
        self.assertFalse(app.exception)
        saved = app.session_state["research"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(next(iter(saved.values()))["status"], "Verify operator")
        self.assertIn("service operator", next(iter(saved.values()))["note"])

        next(control for control in app.selectbox if control.label == "Research status")\
            .set_value("Ready for sales review").run()
        next(button for button in app.button if button.label == "Save research update").click().run()
        self.assertTrue(any("company name and source URL" in item.value for item in app.error))
        self.assertEqual(next(iter(app.session_state["research"].values()))["status"], "Verify operator")
        next(control for control in app.text_input if control.label == "Company name found (optional)")\
            .set_value("Example Company").run()
        next(control for control in app.text_input if control.label == "Source URL for company identity (optional)")\
            .set_value("https://example.com/about").run()
        next(button for button in app.button if button.label == "Save research update").click().run()
        saved = next(iter(app.session_state["research"].values()))
        self.assertEqual(saved["status"], "Ready for sales review")
        self.assertEqual(saved["company_name"], "Example Company")

    def test_research_handoff_csv_has_citations_and_safe_notes(self):
        rows = list(csv.DictReader(StringIO(shortlist_csv(ROOT / "app" / "data" / "welook_serving.duckdb",
            ["3ds.com"], {"3ds.com": {"status": "Verify operator",
                                      "company_name": '=HYPERLINK("https://example.test")',
                                      "source_url": "https://example.com/about",
                                      "note": '=HYPERLINK("https://example.test")'}}))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["research_status"], "Verify operator")
        self.assertTrue(rows[0]["selected_evidence_ids"].startswith("source-record-"))
        self.assertIn("CVE-", rows[0]["scanner_listed_ids"])
        self.assertEqual(rows[0]["ai_decision"], "supported")
        self.assertTrue(rows[0]["research_note"].startswith("'="))
        self.assertTrue(rows[0]["researched_company_name"].startswith("'="))
        self.assertEqual(rows[0]["identity_source_url"], "https://example.com/about")

    def test_product_filter_only_returns_domains_with_selected_evidence(self):
        app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=30).run()
        next(control for control in app.selectbox if control.label == "View")\
            .set_value("All candidates").run()
        next(control for control in app.text_input if control.label == "Product in selected evidence")\
            .set_value("cPanel").run()
        self.assertFalse(app.exception)
        domains = app.dataframe[0].value["Domain"].tolist()
        self.assertTrue(domains)
        with duckdb.connect(str(ROOT / "app" / "data" / "welook_serving.duckdb"), read_only=True) as con:
            matched = con.execute(
                "SELECT count(DISTINCT candidate_domain) FROM evidence "
                "WHERE product ILIKE ? AND candidate_domain IN (SELECT unnest(?::VARCHAR[]))",
                ["%cPanel%", domains],
            ).fetchone()[0]
        self.assertEqual(matched, len(domains))


if __name__ == "__main__":
    unittest.main()
