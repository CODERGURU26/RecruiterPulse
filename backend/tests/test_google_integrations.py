import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from app.services.google_sheets_worker import GoogleSheetsWorker
from app.services.google_calendar_worker import GoogleCalendarWorker


class TestGoogleIntegrations(unittest.TestCase):
    """Exhaustive tests for Google Sheets URL extraction and Google Calendar interview attribution."""

    def test_google_sheets_url_extraction(self):
        """Tests parsing of various Google Sheets URL formats and gids."""
        url1 = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
        sid1, gid1 = GoogleSheetsWorker.extract_sheet_id(url1)
        self.assertEqual(sid1, "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
        self.assertEqual(gid1, "0")

        url2 = "https://docs.google.com/spreadsheets/d/2abcXYZ_12345-6789/edit?gid=987654321#gid=987654321"
        sid2, gid2 = GoogleSheetsWorker.extract_sheet_id(url2)
        self.assertEqual(sid2, "2abcXYZ_12345-6789")
        self.assertEqual(gid2, "987654321")

        _, query_gid = GoogleSheetsWorker.extract_sheet_id(
            "https://docs.google.com/spreadsheets/d/query-only/edit?gid=1195049191"
        )
        self.assertEqual(query_gid, "1195049191")

        # Bare sheet ID
        sid3, gid3 = GoogleSheetsWorker.extract_sheet_id("bare_sheet_id_only_123")
        self.assertEqual(sid3, "bare_sheet_id_only_123")
        self.assertIsNone(gid3)

    def test_google_sheets_rows_wider_than_header_are_preserved(self):
        dataframe = GoogleSheetsWorker._values_to_dataframe([
            ["Date", "Calling Status"],
            ["13/11/2026", "Connected", "extra cell"]
        ])

        self.assertEqual(
            dataframe.columns.tolist(),
            ["Date", "Calling Status", "Unnamed: 3"]
        )
        self.assertEqual(
            dataframe.iloc[0].tolist(),
            ["13/11/2026", "Connected", "extra cell"]
        )

    def test_google_sheets_duplicate_headers_are_made_unique(self):
        dataframe = GoogleSheetsWorker._values_to_dataframe([
            ["Date", "Calling Status", "Calling Status"],
            ["13/11/2026", "Connected", "Not Connected"]
        ])

        self.assertEqual(
            dataframe.columns.tolist(),
            ["Date", "Calling Status", "Calling Status (2)"]
        )
        self.assertEqual(dataframe["Calling Status (2)"].iloc[0], "Not Connected")

    def test_google_calendar_tomorrow_window(self):
        """Tests calculation of tomorrow's 00:00 to 23:59:59 window in IST."""
        ref_date = date(2026, 11, 12)
        t_min, t_max, tomorrow = GoogleCalendarWorker.get_tomorrow_window(ref_date, "Asia/Kolkata")

        self.assertEqual(tomorrow, date(2026, 11, 13))
        self.assertEqual(t_min.hour, 0)
        self.assertEqual(t_min.minute, 0)
        self.assertEqual(t_max.hour, 23)
        self.assertEqual(t_max.minute, 59)
        self.assertEqual(str(t_min.tzinfo), "Asia/Kolkata")

    def test_google_calendar_attribution_hierarchy(self):
        """Tests PRD v1.1 4-Tier Attribution Hierarchy and deduplication."""
        recruiters = [
            {"id": "rec-1", "full_name": "Priya Sharma", "email": "priya@agency.in", "calendar_identifier": "priya@agency.in"},
            {"id": "rec-2", "full_name": "Rahul Verma", "email": "rahul@agency.in", "calendar_identifier": "rahul@agency.in"},
            {"id": "rec-3", "full_name": "Amit Patel", "email": "amit@agency.in", "calendar_identifier": "amit@agency.in"}
        ]

        target_tomorrow = date(2026, 11, 13)

        mock_events = [
            # Event 1 (Tier 1: Creator email match -> Priya)
            {
                "id": "ev-1",
                "status": "confirmed",
                "summary": "Technical Discussion L1",
                "creator": {"email": "priya@agency.in"},
                "attendees": [{"email": "candidate1@gmail.com", "responseStatus": "accepted"}]
            },
            # Event 2 (Tier 2: Attendee list match -> Rahul)
            {
                "id": "ev-2",
                "status": "confirmed",
                "summary": "Interview: Frontend Developer",
                "creator": {"email": "client-hr@techcorp.com"},
                "attendees": [
                    {"email": "candidate2@gmail.com", "responseStatus": "accepted"},
                    {"email": "rahul@agency.in", "responseStatus": "accepted"}
                ]
            },
            # Event 3 (Tier 3: Description/Title tag match -> Amit)
            {
                "id": "ev-3",
                "status": "confirmed",
                "summary": "DevOps Round 1 [Recruiter: Amit Patel]",
                "creator": {"email": "interviewer@client.com"},
                "description": "Candidate interview. Coordinated by Amit Patel.",
                "attendees": [{"email": "candidate3@gmail.com"}]
            },
            # Event 4 (Tier 4: Unassigned - no recruiter tags)
            {
                "id": "ev-4",
                "status": "confirmed",
                "summary": "Direct Interview: System Architect",
                "creator": {"email": "ceo@startup.io"},
                "attendees": [{"email": "candidate4@gmail.com"}]
            },
            # Event 5 (Cancelled event -> Must be excluded)
            {
                "id": "ev-5",
                "status": "cancelled",
                "summary": "Cancelled Interview",
                "creator": {"email": "priya@agency.in"}
            },
            # Event 6 (Declined event -> Must be excluded)
            {
                "id": "ev-6",
                "status": "confirmed",
                "summary": "Declined Interview",
                "creator": {"email": "client@corp.com"},
                "attendees": [{"email": "priya@agency.in", "responseStatus": "declined"}]
            },
            # Event 7 (Duplicate of ev-1 due to reschedule -> Deduplicated by persistent ID)
            {
                "id": "ev-1",
                "status": "confirmed",
                "summary": "Technical Discussion L1 (Rescheduled)",
                "creator": {"email": "priya@agency.in"}
            }
        ]

        result = GoogleCalendarWorker.process_calendar_events(
            events=mock_events,
            recruiters=recruiters,
            target_date=target_tomorrow
        )

        # Priya: 1 (ev-1)
        # Rahul: 1 (ev-2)
        # Amit: 1 (ev-3)
        # Unassigned: 1 (ev-4)
        # Cancelled/Declined/Duplicate: excluded
        self.assertEqual(result.recruiter_interviews["rec-1"], 1)
        self.assertEqual(result.recruiter_interviews["rec-2"], 1)
        self.assertEqual(result.recruiter_interviews["rec-3"], 1)
        self.assertEqual(result.unassigned_count, 1)
        self.assertEqual(result.total_interviews, 4)
        self.assertEqual(len(result.processed_event_ids), 4)


if __name__ == "__main__":
    unittest.main()
