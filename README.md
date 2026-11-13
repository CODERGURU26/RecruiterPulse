# RecruiterPulse

RecruiterPulse imports recruiter call logs, calculates per-recruiter daily metrics, and creates a draft MIS report for review.

## Run locally

1. From `backend`, run `pip install -r requirements.txt`, then `uvicorn app.main:app --reload`. Backend startup automatically ensures the default Apex workspace and its starter data exist; `python seed_db.py` can also be run manually.
2. From `frontend`, run `npm install` and `npm run dev`.
3. Open `http://localhost:3000`. The local frontend expects the seeded workspace ID `ws-apex-101`.

## Import a recruiter workbook

On **Spreadsheets & Mapping**, upload `.xlsx`, `.xls`, or `.csv`. Excel workbooks are scanned across tabs; tabs with recognizable call-status columns are processed. Recruiter names come from a detected recruiter column, the selected recruiter, or the worksheet name. The report defaults to the current date in the workspace timezone; callers can supply `target_date_str` to process a different day. Recruiters appear in the report only when they have at least one counted call for that date. Connected, not-connected, total calls, and roles are calculated from those dated rows, and subsequent master-sheet uploads remove recruiters who have no calls for that date.

The report includes call counts, connection rate, active roles, and unmapped status values. Duplicate candidate/status rows are removed only when a candidate identifier is available. Candidate names and contact details are not included in report data. Interview counts are zero for file uploads because calendar events are not part of the uploaded workbook.

## Current integration boundaries

- Google Sheets URL import reads the tab selected by `gid` (or the first tab) once; it does not register recurring sync. Private sheets need a valid service-account key configured on the backend, otherwise the sheet must be publicly exportable.
- Calendar events are not fetched by the current sync workflow. Do not treat interview numbers as live until calendar ingestion is configured.
- The current frontend targets the seeded workspace and seeded MIS approver; sign-in and workspace selection are not implemented.
