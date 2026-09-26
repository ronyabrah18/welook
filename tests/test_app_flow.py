"""Check the hosted snapshot supports the salesperson's core research flow."""

import unittest
import json

import duckdb

from streamlit.testing.v1 import AppTest

from scripts.ingest_full import ROOT


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


if __name__ == "__main__":
    unittest.main()
