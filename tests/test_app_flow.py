"""Check the hosted snapshot supports the salesperson's core research flow."""

import unittest

from streamlit.testing.v1 import AppTest

from scripts.ingest_full import ROOT


class AppFlowTest(unittest.TestCase):
    def test_ai_note_can_be_found_and_shortlisted(self):
        app = AppTest.from_file(str(ROOT / "app" / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertIn("Explore candidates", [heading.value for heading in app.subheader])

        view = next(control for control in app.selectbox if control.label == "View")
        view.set_value("AI notes").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 35)
        self.assertTrue(any("AI research note" in item.value for item in app.info))

        next(button for button in app.button if button.label == "Add to shortlist").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["shortlist"]), 1)


if __name__ == "__main__":
    unittest.main()
