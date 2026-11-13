import unittest
import pandas as pd
from app.models.enums import StandardField
from app.services.column_detector import ColumnDetector


class TestColumnDetector(unittest.TestCase):
    """Exhaustive unit tests for automatic column detection & heuristic mapping."""

    def test_clean_header(self):
        """Tests header sanitization with punctuation and irregular casing."""
        self.assertEqual(ColumnDetector.clean_header("Calling_Date (IST)"), "calling date (ist)")
        self.assertEqual(ColumnDetector.clean_header("  Call.Outcome!  "), "call outcome!")
        self.assertEqual(ColumnDetector.clean_header("Candidate---Name"), "candidate name")
        self.assertEqual(ColumnDetector.clean_header("JOB-ROLE"), "job role")

    def test_standard_headers_detection(self):
        """Tests standard well-formed headers with high confidence."""
        df = pd.DataFrame({
            "Calling Date": ["12/11/2026", "12/11/2026"],
            "Call Outcome": ["Connected", "RNR"],
            "Candidate Name": ["Arjun Rao", "Sunita Nair"],
            "Role": ["Java Backend", "DevOps"]
        })
        results = ColumnDetector.analyze_dataframe(df)

        self.assertEqual(results[StandardField.ACTIVITY_DATE]["source_column"], "Calling Date")
        self.assertTrue(results[StandardField.ACTIVITY_DATE]["auto_confirmed"])
        self.assertGreaterEqual(results[StandardField.ACTIVITY_DATE]["confidence"], 0.85)

        self.assertEqual(results[StandardField.CALL_STATUS]["source_column"], "Call Outcome")
        self.assertTrue(results[StandardField.CALL_STATUS]["auto_confirmed"])

        self.assertEqual(results[StandardField.CANDIDATE_REF]["source_column"], "Candidate Name")
        self.assertTrue(results[StandardField.CANDIDATE_REF]["auto_confirmed"])

        self.assertEqual(results[StandardField.JOB_ROLE]["source_column"], "Role")
        self.assertTrue(results[StandardField.JOB_ROLE]["auto_confirmed"])

    def test_noisy_and_alternative_headers(self):
        """Tests alternative Indian agency header aliases."""
        df = pd.DataFrame({
            "call_dt": ["2026-11-12", "2026-11-12"],
            "connection_status": ["busy", "switched off"],
            "mobile_number": ["9876543210", "9123456789"],
            "designation": ["Python Engineer", "React Lead"]
        })
        results = ColumnDetector.analyze_dataframe(df)

        self.assertEqual(results[StandardField.ACTIVITY_DATE]["source_column"], "call_dt")
        self.assertEqual(results[StandardField.CALL_STATUS]["source_column"], "connection_status")
        self.assertEqual(results[StandardField.CANDIDATE_REF]["source_column"], "mobile_number")
        self.assertEqual(results[StandardField.JOB_ROLE]["source_column"], "designation")

    def test_value_assisted_date_detection(self):
        """Tests that date-like sample values elevate confidence even with generic header like 'Day'."""
        df = pd.DataFrame({
            "Day": ["12-Nov-2026", "13-Nov-2026", "14-Nov-2026"],
            "Remarks": ["Spoke with candidate", "RNR", "Busy"]
        })
        results = ColumnDetector.analyze_dataframe(df)
        self.assertEqual(results[StandardField.ACTIVITY_DATE]["source_column"], "Day")
        self.assertGreaterEqual(results[StandardField.ACTIVITY_DATE]["confidence"], 0.85)

    def test_job_source_column_is_not_detected_as_recruiter(self):
        df = pd.DataFrame({
            "Date": ["13/11/2026"],
            "Source": ["Internshala"],
            "Calling Status": ["Connected"],
            "Candidate Name": ["Example Candidate"],
            "Recruiter comments, if any": ["Follow up tomorrow"],
        })

        results = ColumnDetector.analyze_dataframe(df)

        self.assertIsNone(results[StandardField.RECRUITER_NAME]["source_column"])

    def test_recruiter_name_column_is_not_misclassified_as_candidate_name(self):
        df = pd.DataFrame({
            "Date": ["13/11/2026", "13/11/2026"],
            "Call Status": ["Connected", "Not Connected"],
            "Recruiter Name": ["Tanmay", "Divya"],
        })

        results = ColumnDetector.analyze_dataframe(df)

        self.assertEqual(results[StandardField.RECRUITER_NAME]["source_column"], "Recruiter Name")
        self.assertIsNone(results[StandardField.CANDIDATE_REF]["source_column"])

    def test_edge_case_empty_and_null_columns(self):
        """Tests handling of blank columns, NaN values, and unmapped fields."""
        df = pd.DataFrame({
            "Unrelated Column A": [None, None, None],
            "Unrelated Column B": ["xyz", "abc", "123"],
            "Unrelated Column C": [100, 200, 300]
        })
        results = ColumnDetector.analyze_dataframe(df)
        
        # When no relevant columns exist, confidence must be low and not auto-confirmed
        for field in StandardField:
            res = results[field]
            self.assertFalse(res["auto_confirmed"])


if __name__ == "__main__":
    unittest.main()
