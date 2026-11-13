# RecruiterPulse

RecruiterPulse imports recruiter call logs, calculates per-recruiter daily metrics, and creates a draft MIS report for review.

## Run locally

1. From `backend`, run `pip install -r requirements.txt`, then `uvicorn app.main:app --reload`. Backend startup automatically ensures the default Apex workspace and its starter data exist; `python seed_db.py` can also be run manually.
2. From `frontend`, run `npm install` and `npm run dev`.
3. Open `http://localhost:3000`. The local frontend expects the seeded workspace ID `ws-apex-101`.

## Import a recruiter workbook

On **Spreadsheets & Mapping**, upload `.xlsx`, `.xls`, or `.csv`. Excel workbooks are scanned across tabs; tabs with recognizable call-status columns are processed. Recruiter names come from a detected recruiter column, the selected recruiter, or the worksheet name. The report defaults to the current date in the workspace timezone; callers can supply `target_date_str` to process a different day. Recruiters appear in the report only when they have at least one counted call for that date. Connected, not-connected, total calls, and roles are calculated from those dated rows, and subsequent master-sheet uploads remove recruiters who have no calls for that date.

The report includes call counts, connection rate, active roles, and unmapped status values. Duplicate candidate/status rows are removed only when a candidate identifier is available. Candidate names and contact details are not included in report data. Interview counts are zero for file uploads because calendar events are not part of the uploaded workbook.

## Enable live Google Sheets sync

Live sync reads only explicitly registered recruiter call-log tabs. It does not guess the first tab. Naukri, Internshala, and summary tabs are not recruiter call logs and should not be registered as recruiters.

1. In Google Cloud, create a service account, enable the Google Sheets API for its project, and create/download a JSON key. Store the key outside this repository (for example, under `%USERPROFILE%\.recruiterpulse\`); never commit it or share it in chat.
2. Copy `backend\.env.example` to `backend\.env`. Set `GOOGLE_SERVICE_ACCOUNT_EMAIL` to the service account's actual `client_email`, and set `GOOGLE_SERVICE_ACCOUNT_KEY_PATH` to the JSON key's absolute path. Keep `GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES=15` for 15-minute refreshes. The backend `.env` is ignored by git.
3. Share each private spreadsheet with that exact service-account email as **Viewer**. Do not enable public link access for candidate data.
4. Install backend requirements and restart the backend. The configured service-account email is shown in **Spreadsheets & Data Sources**.
5. In **Spreadsheets & Data Sources**, select the recruiter call-log tab in Google Sheets, copy its URL with the `gid` in it, enter the recruiter name, and choose **Enable 15-minute live sync**. Repeat for each recruiter tab. The first sync runs immediately; later syncs run every 15 minutes while the backend is running. Use a separate source only when it is a separate recruiter call log.

If a sheet returns HTTP 401 or 403, verify that the backend is using the key for the same service-account email you shared with the spreadsheet, that the Sheets API is enabled, and that the URL's `gid` points to the intended tab. Do not share the JSON key to troubleshoot.

## Current integration boundaries

- Live Google Sheets sync is recurring; the one-time **Analyze Google Sheet** action remains available for an ad-hoc import. Google Calendar events are not fetched by the current sync workflow, so interview numbers should not be treated as live until calendar ingestion is configured.
- The current frontend targets the seeded workspace and seeded MIS approver; sign-in and workspace selection are not implemented.
