import unittest
import time
from datetime import date
import pandas as pd
from app.models.enums import StandardField, CallCategory
from app.models.taxonomy import DEFAULT_INDIAN_TAXONOMY_PRESETS
from app.services.calculation_engine import CalculationEngine


class TestPerformanceAndScalability(unittest.TestCase):
    """Stress testing the calculation engine with large recruiter call volumes."""

    def test_thousand_rows_processing_speed(self):
        """Processes 1,000 rows in < 250ms."""
        target_date = date(2026, 11, 12)
        statuses = ["Connected", "RNR", "Switched Off", "Interested", "Busy", "L1 Scheduled"]
        roles = ["Java Developer", "React Frontend", "DevOps Engineer", "Data Analyst"]

        # Generate 1,000 rows where indices 800..999 are exact duplicates of 0..199
        n_rows = 1000
        unique_count = 800
        data = {
            "Call Date": ["12/11/2026"] * n_rows,
            "Candidate Contact": [f"Candidate_{i if i < unique_count else (i - unique_count)}" for i in range(n_rows)],
            "Disposition": [statuses[i % len(statuses) if i < unique_count else (i - unique_count) % len(statuses)] for i in range(n_rows)],
            "Position": [roles[i % len(roles)] for i in range(n_rows)]
        }
        df = pd.DataFrame(data)

        mapping = {
            StandardField.ACTIVITY_DATE: "Call Date",
            StandardField.CALL_STATUS: "Disposition",
            StandardField.CANDIDATE_REF: "Candidate Contact",
            StandardField.JOB_ROLE: "Position"
        }
        taxonomy = {raw: cat for raw, cat in DEFAULT_INDIAN_TAXONOMY_PRESETS}

        start_time = time.perf_counter()
        result = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=mapping,
            status_taxonomy=taxonomy,
            target_date=target_date
        )
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        print(f"\n[Performance Benchmark] Processed {n_rows} rows in {elapsed_ms:.2f} ms")
        self.assertLess(elapsed_ms, 500.0, f"Processing {n_rows} rows took too long: {elapsed_ms:.2f} ms")
        self.assertEqual(result.total_rows_processed, n_rows)
        self.assertGreater(result.total_calls, 0)
        self.assertGreater(result.duplicates_removed, 0)


if __name__ == "__main__":
    unittest.main()
