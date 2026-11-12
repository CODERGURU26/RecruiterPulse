import unittest
from datetime import date
import pandas as pd
from app.models.enums import StandardField, CallCategory
from app.models.taxonomy import DEFAULT_INDIAN_TAXONOMY_PRESETS
from app.services.calculation_engine import CalculationEngine


class TestCalculationEngine(unittest.TestCase):
    """Exhaustive tests for calling metrics calculation, deduplication, and zero-PII protection."""

    def setUp(self):
        self.column_mapping = {
            StandardField.ACTIVITY_DATE: "Date",
            StandardField.CALL_STATUS: "Status",
            StandardField.CANDIDATE_REF: "Candidate",
            StandardField.JOB_ROLE: "Role"
        }
        self.taxonomy = {raw: cat for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS}
        self.target_date = date(2026, 11, 12)

    def test_multi_format_date_parsing_and_filtering(self):
        """Tests that various Indian date string formats parse cleanly and past dates are excluded."""
        df = pd.DataFrame({
            "Date": [
                "12/11/2026",      # DD/MM/YYYY
                "2026-11-12",      # YYYY-MM-DD
                "12-11-2026",      # DD-MM-YYYY
                "11/11/2026",      # Yesterday (must be filtered out)
                "13/11/2026",      # Tomorrow (must be filtered out)
                "invalid-date"     # Garbage date (must be safely ignored)
            ],
            "Candidate": ["C1", "C2", "C3", "C4", "C5", "C6"],
            "Status": ["Connected", "RNR", "Interested", "Connected", "Busy", "RNR"],
            "Role": ["Java", "DevOps", "Java", "Python", "React", "Node"]
        })

        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=self.column_mapping,
            status_taxonomy=self.taxonomy,
            target_date=self.target_date
        )

        self.assertEqual(result.total_rows_processed, 6)
        # Only C1, C2, C3 are on 2026-11-12
        self.assertEqual(result.total_calls, 3)
        self.assertEqual(result.connected_calls, 2)  # Connected, Interested
        self.assertEqual(result.not_connected_calls, 1)  # RNR
        self.assertAlmostEqual(result.connected_rate, 66.67, places=2)

    def test_deduplication_safeguard(self):
        """Tests that duplicate calls to the same candidate with identical status are deduplicated."""
        df = pd.DataFrame({
            "Date": ["12/11/2026", "12/11/2026", "12/11/2026"],
            "Candidate": ["Pooja Hegde", "Pooja Hegde", "Vikram Rathore"],
            "Status": ["Connected", "Connected", "RNR"],
            "Role": ["Frontend", "Frontend", "Backend"]
        })

        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=self.column_mapping,
            status_taxonomy=self.taxonomy,
            target_date=self.target_date
        )

        # 1 duplicate removed, leaving 2 unique calls
        self.assertEqual(result.duplicates_removed, 1)
        self.assertEqual(result.total_calls, 2)
        self.assertEqual(result.connected_calls, 1)
        self.assertEqual(result.not_connected_calls, 1)
        self.assertEqual(result.connected_rate, 50.0)

    def test_division_by_zero_safety(self):
        """Tests that recruiters with 0 calls produce 0.0% connected rate with zero errors."""
        df = pd.DataFrame({
            "Date": ["10/11/2026"],  # Different date
            "Candidate": ["Ramesh"],
            "Status": ["Connected"],
            "Role": ["Tester"]
        })

        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=self.column_mapping,
            status_taxonomy=self.taxonomy,
            target_date=self.target_date
        )

        self.assertEqual(result.total_calls, 0)
        self.assertEqual(result.connected_calls, 0)
        self.assertEqual(result.not_connected_calls, 0)
        self.assertEqual(result.connected_rate, 0.0)
        self.assertEqual(result.job_roles, [])

    def test_unmapped_status_handling(self):
        """Tests that unknown call statuses are flagged for MIS review without crashing."""
        df = pd.DataFrame({
            "Date": ["12/11/2026", "12/11/2026"],
            "Candidate": ["User A", "User B"],
            "Status": ["Spoke with candidate", "Network dropped midway"],
            "Role": ["Java", "Java"]
        })

        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=self.column_mapping,
            status_taxonomy=self.taxonomy,
            target_date=self.target_date
        )

        # 'Network dropped midway' is unknown
        self.assertIn("Network dropped midway", result.unmapped_statuses)
        self.assertEqual(result.total_calls, 2)

    def test_zero_pii_guarantee(self):
        """Strict DPDP Act verification: Candidate identities and phone numbers never leak into outputs."""
        df = pd.DataFrame({
            "Date": ["12/11/2026"],
            "Candidate": ["Sensitive Candidate Full Name (+91-9876543210)"],
            "Status": ["Connected"],
            "Role": ["Secret Client Role"]
        })

        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=self.column_mapping,
            status_taxonomy=self.taxonomy,
            target_date=self.target_date
        )

        result_dict = result.to_dict()
        self.assertNotIn("Candidate", result_dict)
        self.assertNotIn("Sensitive Candidate", str(result_dict))
        self.assertNotIn("+91-9876543210", str(result_dict))

    def test_missing_required_column_raises_error(self):
        """Tests that missing required columns raise descriptive ValueError."""
        df = pd.DataFrame({"Unknown Column": [1, 2, 3]})
        with self.assertRaises(ValueError):
            CalculationEngine.calculate_recruiter_activity(
                df=df,
                column_mapping=self.column_mapping,
                status_taxonomy=self.taxonomy,
                target_date=self.target_date
            )


if __name__ == "__main__":
    unittest.main()

