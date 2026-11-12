import re
import os
import io
import json
from typing import Optional, Tuple, Dict, Any
import pandas as pd
import httpx
from app.core.config import settings

# Google Client Library imports
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GoogleSheetsWorker:
    """
    Worker for fetching spreadsheet data from live Google Sheets.
    Supports both Google Service Account API and direct Sheets web export.
    """

    SHEET_ID_REGEX = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
    GID_REGEX = re.compile(r"[#&]gid=([0-9]+)")

    @classmethod
    def extract_sheet_id(cls, url_or_id: str) -> Tuple[str, Optional[str]]:
        """
        Extracts spreadsheet ID and optional gid (tab identifier) from a Google Sheets URL or raw ID.
        """
        clean_input = url_or_id.strip()
        match = cls.SHEET_ID_REGEX.search(clean_input)
        sheet_id = match.group(1) if match else clean_input

        gid_match = cls.GID_REGEX.search(clean_input)
        gid = gid_match.group(1) if gid_match else None

        return sheet_id, gid

    @classmethod
    def fetch_via_service_account(
        cls,
        spreadsheet_id: str,
        tab_name: Optional[str] = None,
        key_path: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetches live spreadsheet data using Google Service Account credentials.
        """
        if not GOOGLE_API_AVAILABLE:
            raise RuntimeError("Google API client libraries are not installed.")

        key_file = key_path or settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH
        if not key_file or not os.path.exists(key_file):
            raise FileNotFoundError(f"Service account key file not found: {key_file}")

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = service_account.Credentials.from_service_account_file(key_file, scopes=scopes)
        service = build("sheets", "v4", credentials=creds)

        range_to_fetch = f"'{tab_name}'!A1:ZZ" if tab_name else "A1:ZZ"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_to_fetch
        ).execute()

        values = result.get("values", [])
        if not values or len(values) < 2:
            return pd.DataFrame()

        headers = values[0]
        data_rows = values[1:]
        # Pad shorter rows
        padded_rows = [row + [""] * (len(headers) - len(row)) for row in data_rows]
        return pd.DataFrame(padded_rows, columns=headers)

    @classmethod
    async def fetch_via_web_export(
        cls,
        spreadsheet_id: str,
        gid: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fast HTTPS ingestion: Reads shared/viewer Google Sheet directly as CSV.
        Requires Viewer access granted to service account or link-sharing.
        """
        export_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
        if gid:
            export_url += f"&gid={gid}"

        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(export_url)
            if resp.status_code != 200:
                raise ValueError(
                    f"Unable to access Google Sheet (HTTP {resp.status_code}). "
                    f"Ensure sheet is shared with '{settings.GOOGLE_SERVICE_ACCOUNT_EMAIL}' with Viewer access."
                )

            csv_text = resp.text
            return pd.read_csv(io.StringIO(csv_text))

    @classmethod
    async def fetch_sheet_dataframe(
        cls,
        url_or_id: str,
        tab_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Main entrypoint: Attempts Service Account API first, falls back to Web Export endpoint.
        """
        sheet_id, gid = cls.extract_sheet_id(url_or_id)

        # 1. Try official Service Account API if credentials configured
        if settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH and os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_KEY_PATH):
            try:
                return cls.fetch_via_service_account(sheet_id, tab_name=tab_name)
            except Exception as e:
                pass  # Fall through to web export

        # 2. Ingest via direct export endpoint
        return await cls.fetch_via_web_export(sheet_id, gid=gid)

