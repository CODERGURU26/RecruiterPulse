import unittest
from datetime import date
from app.services.whatsapp_formatter import WhatsAppFormatter


class TestWhatsAppFormatter(unittest.TestCase):
    """Unit tests for the WhatsApp clipboard formatting engine."""

    def test_standard_report_formatting(self):
        metrics = [
            {
                "recruiter_name": "Priya Sharma",
                "job_roles": ["Java", "DevOps"],
                "connected_calls": 28,
                "not_connected_calls": 14,
                "total_calls": 42,
                "connected_rate": 66.67,
                "next_day_interviews": 3
            },
            {
                "recruiter_name": "Rahul Verma",
                "job_roles": ["Frontend"],
                "connected_calls": 18,
                "not_connected_calls": 17,
                "total_calls": 35,
                "connected_rate": 51.43,
                "next_day_interviews": 1
            }
        ]
        summary = {
            "total_calls": 77,
            "connected_rate": 59.74,
            "next_day_interviews": 4
        }
        output = WhatsAppFormatter.format_report(
            workspace_name="Apex Staffing India",
            reporting_date=date(2026, 11, 12),
            hour_slot="15:00",
            metrics=metrics,
            summary_totals=summary,
            approver_name="Pooja Kulkarni"
        )

        self.assertIn("Apex Staffing India", output)
        self.assertIn("12-Nov-2026", output)
        self.assertIn("03:00 PM IST", output)
        self.assertIn("Priya Sharma", output)
        self.assertIn("Calls: 42 (28 Conn / 14 Not Conn) | 66.7%", output)
        self.assertIn("Rahul Verma", output)
        self.assertIn("Team Total:* 77 Calls | 59.7% Conn Rate | 🎯 4 Next-Day Interviews", output)
        self.assertIn("Approved by MIS (Pooja Kulkarni)", output)

    def test_pending_approval_notice(self):
        """Tests that unapproved report indicates pending status."""
        output = WhatsAppFormatter.format_report(
            workspace_name="Demo Agency",
            reporting_date=date(2026, 11, 12),
            hour_slot="12:00",
            metrics=[],
            summary_totals={"total_calls": 0, "connected_rate": 0.0, "next_day_interviews": 0},
            approver_name=None
        )
        self.assertIn("Pending MIS Approval", output)


if __name__ == "__main__":
    unittest.main()

