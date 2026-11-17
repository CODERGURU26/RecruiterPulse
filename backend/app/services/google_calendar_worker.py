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

        def unique_match(value: str, recruiter_field: str) -> Optional[str]:
            normalized = value.casefold().strip()
            if not normalized:
                return None
            matches = {
                recruiter["id"]
                for recruiter in recruiters
                if (recruiter.get(recruiter_field) or "").casefold().strip() == normalized
            }
            return next(iter(matches)) if len(matches) == 1 else None

        # Prefer event identity over the calendar that happened to return the event.
        for field in ("creator", "organizer"):
            email = (event.get(field, {}).get("email") or "").casefold().strip()
            matched = unique_match(email, "email")
            if matched:
                return matched
            matched = unique_match(email, "calendar_identifier")
            if matched:
                return matched

        organizer_names = [
            (event.get(field, {}).get("displayName") or "").casefold().strip()
            for field in ("creator", "organizer")
        ]
        for display_name in organizer_names:
            if not display_name:
                continue
            exact_matches = [
                recruiter["id"]
                for recruiter in recruiters
                if (recruiter.get("full_name") or "").casefold().strip() == display_name
            ]
            if len(exact_matches) == 1:
                return exact_matches[0]

            first_name_matches = [
                recruiter["id"]
                for recruiter in recruiters
                if (recruiter.get("full_name") or "").casefold().split()
                and (recruiter.get("full_name") or "").casefold().split()[0]
                == display_name.split()[0]
            ]
            if len(first_name_matches) == 1:
                return first_name_matches[0]

        # Tier 2: Attendee Email Match
        attendees = event.get("attendees", [])
        attendee_matches = set()
        for att in attendees:
            att_email = (att.get("email") or "").casefold().strip()
            response_status = att.get("responseStatus", "")
            if response_status == "declined":
                continue  # Skip declined

            matched = unique_match(att_email, "email")
            if matched:
                attendee_matches.add(matched)
            matched = unique_match(att_email, "calendar_identifier")
            if matched:
                attendee_matches.add(matched)
        if len(attendee_matches) == 1:
            return next(iter(attendee_matches))

        # Tier 3: Summary or Description Tag Match (e.g. "[Recruiter: Priya]", "Owner: Priya Sharma")
        summary = (event.get("summary") or "").casefold()
        description = (event.get("description") or "").casefold()
        combined_text = f"{summary} {description}"
        tagged_matches = set()
        for rec in recruiters:
            rec_name = rec.get("full_name", "").casefold().strip()
            if not rec_name:
                continue

            if (
                rec_name in combined_text
                or f"recruiter: {rec_name}" in combined_text
                or f"owner: {rec_name}" in combined_text
            ):
                tagged_matches.add(rec["id"])
            first_name = rec_name.split()[0]
            if len(first_name) >= 3 and f"[{first_name}]" in combined_text:
                tagged_matches.add(rec["id"])
        if len(tagged_matches) == 1:
            return next(iter(tagged_matches))

        # Calendar ownership is only a fallback after event metadata and tags.
        source_calendar_recruiter_id = event.get("_recruiterpulse_calendar_recruiter_id")
        if source_calendar_recruiter_id and any(
            rec["id"] == source_calendar_recruiter_id for rec in recruiters
        ):
            return source_calendar_recruiter_id
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

        events_by_id: Dict[str, Dict[str, Any]] = {}
        shared_calendar_event_ids: Set[str] = set()
        for event in events:
            event_id = event.get("id")
            if not event_id or event.get("status") == "cancelled":
                continue
            existing = events_by_id.get(event_id)
            if existing is None:
                events_by_id[event_id] = event
                continue

            original_source = existing.get("_recruiterpulse_calendar_recruiter_id")
            duplicate_source = event.get("_recruiterpulse_calendar_recruiter_id")
            if original_source != duplicate_source:
                shared_calendar_event_ids.add(event_id)

        for event_id in shared_calendar_event_ids:
            events_by_id[event_id].pop("_recruiterpulse_calendar_recruiter_id", None)

        for ev in events_by_id.values():
            event_id = ev.get("id")
            if not event_id or event_id in seen_event_ids:
                continue  # Avoid double counting rescheduled events

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
