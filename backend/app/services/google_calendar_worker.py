import os
import re
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from zoneinfo import ZoneInfo
from app.core.config import settings

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class CalendarInterviewResult:
    """Summary of tomorrow's interviews mapped to recruiters."""
    def __init__(
        self,
        target_date: date,
        recruiter_interviews: Dict[str, int],  # recruiter_id -> interview count
        unassigned_count: int,
        total_interviews: int,
        processed_event_ids: Set[str]
    ):
        self.target_date = target_date
        self.recruiter_interviews = recruiter_interviews
        self.unassigned_count = unassigned_count
        self.total_interviews = total_interviews
        self.processed_event_ids = processed_event_ids


class GoogleCalendarWorker:
    """
    Worker for fetching scheduled interviews from Google Calendar
    and executing the 4-tier recruiter attribution hierarchy.
    """

    @staticmethod
    def get_tomorrow_window(
        reference_date: Optional[date] = None,
        tz_name: str = "Asia/Kolkata"
    ) -> Tuple[datetime, datetime, date]:
        """
        Calculates tomorrow's full-day window as [midnight, next midnight) in the workspace timezone.
        """
        tz = ZoneInfo(tz_name)
        base_date = reference_date or datetime.now(tz).date()
        tomorrow_date = base_date + timedelta(days=1)

        time_min = datetime(tomorrow_date.year, tomorrow_date.month, tomorrow_date.day, 0, 0, 0, tzinfo=tz)
        next_date = tomorrow_date + timedelta(days=1)
        time_max = datetime(next_date.year, next_date.month, next_date.day, 0, 0, 0, tzinfo=tz)

        return time_min, time_max, tomorrow_date

    @classmethod
    def attribute_event_to_recruiter(
        cls,
        event: Dict[str, Any],
        recruiters: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Applies PRD v1.1 4-Tier Attribution Hierarchy to find the responsible recruiter:
        1. Creator / Organizer Email
        2. Attendee Email Match (not declined)
        3. Title / Description Tag Match
        4. None (Unassigned)
        """
        # Exclude cancelled events
        if event.get("status") == "cancelled":
            return None

        source_calendar_recruiter_id = event.get("_recruiterpulse_calendar_recruiter_id")
        if source_calendar_recruiter_id and any(
            rec["id"] == source_calendar_recruiter_id for rec in recruiters
        ):
            return source_calendar_recruiter_id

        # Tier 1: Creator / Organizer Email
        creator_email = (event.get("creator", {}).get("email") or "").lower().strip()
        organizer_email = (event.get("organizer", {}).get("email") or "").lower().strip()

        for rec in recruiters:
            rec_email = (rec.get("email") or "").lower().strip()
            cal_id = (rec.get("calendar_identifier") or "").lower().strip()
            if rec_email and (rec_email == creator_email or rec_email == organizer_email):
                return rec["id"]
            if cal_id and (cal_id == creator_email or cal_id == organizer_email):
                return rec["id"]

        # Tier 2: Attendee Email Match
        attendees = event.get("attendees", [])
        for att in attendees:
            att_email = (att.get("email") or "").lower().strip()
            response_status = att.get("responseStatus", "")
            if response_status == "declined":
                continue  # Skip declined

            for rec in recruiters:
                rec_email = (rec.get("email") or "").lower().strip()
                if rec_email and rec_email == att_email:
                    return rec["id"]

        # Tier 3: Summary or Description Tag Match (e.g. "[Recruiter: Priya]", "Owner: Priya Sharma")
        summary = (event.get("summary") or "").lower()
        description = (event.get("description") or "").lower()
        combined_text = f"{summary} {description}"

        for rec in recruiters:
            rec_name = rec.get("full_name", "").lower().strip()
            if not rec_name:
                continue

            # Check full name or explicit tag
            if rec_name in combined_text or f"recruiter: {rec_name}" in combined_text or f"owner: {rec_name}" in combined_text:
                return rec["id"]

            # First name match if unique enough
            first_name = rec_name.split()[0]
            if len(first_name) >= 3 and f"[{first_name}]" in combined_text:
                return rec["id"]

        # Tier 4: Fallback to Unassigned
        return None

    @classmethod
    def process_calendar_events(
        cls,
        events: List[Dict[str, Any]],
        recruiters: List[Dict[str, Any]],
        target_date: date
    ) -> CalendarInterviewResult:
        """
        Processes a list of Google Calendar event objects:
        - Excludes cancelled/declined events
        - Deduplicates rescheduled events by persistent event_id
        - Attributes to recruiters
        """
        recruiter_counts: Dict[str, int] = {rec["id"]: 0 for rec in recruiters}
        unassigned_count = 0
        seen_event_ids: Set[str] = set()

        for ev in events:
            event_id = ev.get("id")
            if not event_id or event_id in seen_event_ids:
                continue  # Avoid double counting rescheduled events

            if ev.get("status") == "cancelled":
                continue

            # Exclude if any matching recruiter declined the interview
            has_declined_recruiter = False
            for att in ev.get("attendees", []):
                if att.get("responseStatus") == "declined":
                    att_email = (att.get("email") or "").lower().strip()
                    if any(
                        att_email in {
                            (rec.get("email") or "").lower().strip(),
                            (rec.get("calendar_identifier") or "").lower().strip()
                        }
                        for rec in recruiters
                    ):
                        has_declined_recruiter = True
                        break
            if has_declined_recruiter:
                continue

            seen_event_ids.add(event_id)
            matched_recruiter_id = cls.attribute_event_to_recruiter(ev, recruiters)


            if matched_recruiter_id and matched_recruiter_id in recruiter_counts:
                recruiter_counts[matched_recruiter_id] += 1
            else:
                unassigned_count += 1

        total_interviews = sum(recruiter_counts.values()) + unassigned_count

        return CalendarInterviewResult(
            target_date=target_date,
            recruiter_interviews=recruiter_counts,
            unassigned_count=unassigned_count,
            total_interviews=total_interviews,
            processed_event_ids=seen_event_ids
        )

    @classmethod
    def fetch_live_calendar_events(
        cls,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime,
        key_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Calls Google Calendar API v3 to list events within the specified time window.
        """
        if not GOOGLE_API_AVAILABLE:
            raise RuntimeError("Google API client libraries are not installed.")

        key_file = key_path or settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH
        if not key_file or not os.path.exists(key_file):
            raise FileNotFoundError(f"Service account key file not found: {key_file}")

        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
        service = build("calendar", "v3", credentials=creds)

        events = []
        page_token = None
        while True:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=2500,
                pageToken=page_token
            ).execute()
            events.extend(events_result.get("items", []))
            page_token = events_result.get("nextPageToken")
            if not page_token:
                return events

    @classmethod
    async def fetch_live_calendar_events_async(
        cls,
        calendar_id: str,
        time_min: datetime,
        time_max: datetime
    ) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(
            cls.fetch_live_calendar_events,
            calendar_id,
            time_min,
            time_max
        )
