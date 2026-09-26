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

    def test_research_handoff_csv_has_citations_and_safe_notes(self):
        rows = list(csv.DictReader(StringIO(shortlist_csv(ROOT / "app" / "data" / "welook_serving.duckdb",
            ["3ds.com"], {"3ds.com": {"status": "Verify operator",
                                      "note": '=HYPERLINK("https://example.test")'}}))))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["research_status"], "Verify operator")
        self.assertTrue(rows[0]["selected_evidence_ids"].startswith("source-record-"))
        self.assertEqual(rows[0]["ai_decision"], "supported")
        self.assertTrue(rows[0]["research_note"].startswith("'="))

    def test_product_filter_only_returns_domains_with_selected_evidence(self):
        app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=30).run()
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
