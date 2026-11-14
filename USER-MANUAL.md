# RecruiterPulse User Manual

RecruiterPulse reads recruiter call-log tabs, calculates daily call totals, and creates a report for review. This guide covers the local app setup and the recurring Google Sheets workflow.

## 1. Start RecruiterPulse

Start the backend and frontend in separate PowerShell terminals from the project folder.

**Backend terminal**

```powershell
Set-Location backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If the virtual environment does not exist yet, create it and install requirements first:

```powershell
Set-Location backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use `app.main:app` as shown; starting a different entry point can serve an older app or database.

**Frontend terminal**

```powershell
Set-Location frontend
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:3000`. Keep both terminals running. The backend provisions the default workspace on startup; if the page was already open, refresh it.

## 2. Connect private Google Sheets (one-time setup)

The backend uses a Google service account to read private spreadsheets. It needs **Viewer** access only.

1. In Google Cloud Console, create a service account and enable the **Google Sheets API** for its project.
2. Create and download a JSON key. Store it somewhere private outside the project, for example `C:\Users\<your-user>\.recruiterpulse\service-account.json`. Never put the JSON key in chat, source code, or a shared folder.
3. In `backend\.env`, set the service account email, the JSON file's full path, and the refresh interval:

   ```env
   GOOGLE_SERVICE_ACCOUNT_EMAIL=the-service-account@your-project.iam.gserviceaccount.com
   GOOGLE_SERVICE_ACCOUNT_KEY_PATH=C:\Users\<your-user>\.recruiterpulse\service-account.json
   GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES=5
   ```

   Replace the example email and path with your actual values. Use the interval already set in your `.env`; `5` means sync every five minutes. The key path is the location of the downloaded JSON file, not its contents.
4. In Google Sheets, share every workbook you need to sync with that exact service-account email as **Viewer**.
5. In Google Cloud Console, enable the **Google Calendar API** in the same project if you plan to sync recruiter interviews.
6. In Google Calendar, share each recruiter's calendar with the same service-account email as **See all event details** (read-only). Find each calendar ID in Google Calendar **Settings & sharing → Integrate calendar → Calendar ID**.
7. Restart the backend after changing `.env` or Google Cloud API settings.

The app's **Spreadsheets & Data Sources** page shows the email to share with. It also has a copy button.

## 3. Register one tab or a whole workbook for live sync

You can register an individual recruiter tab or let RecruiterPulse scan a whole workbook. You do not need to upload the sheet again after registration.

### Register one recruiter tab

1. In Google Sheets, open the individual recruiter's call-log tab (for example, Tanmay).
2. Copy the browser URL while that tab is selected. It must include its `gid`, such as `.../edit?gid=1195049191`.
3. In RecruiterPulse, open **Spreadsheets & Data Sources** and paste the URL in the Google Sheets URL field.
4. In **Recruiter owning this tab**, enter the matching recruiter name.
5. Select **Enable automatic live sync**. The first sync runs immediately; subsequent refreshes use `GOOGLE_SHEETS_SYNC_INTERVAL_MINUTES` from the backend `.env`.

### Register every supported recruiter tab in a workbook

1. Share the workbook with the configured service-account email as **Viewer**.
2. Paste a URL to the workbook into the Google Sheets URL field. The URL may point to any tab.
3. Select **Register all recruiter tabs**. RecruiterPulse discovers the workbook's tabs and registers ones with recognizable activity-date and call-status columns. The initial sync runs after registration.
4. Review the skipped-tab reasons shown on the page. Summary/non-call tabs are skipped. Tabs with multiple recruiter names are skipped because each live source must have one recruiter owner; split those logs into one tab per recruiter or register the appropriate individual tabs.

Whole-workbook discovery requires the configured Google service-account key and Viewer access to the workbook. Naukri and Internshala are job sources, not recruiter names. Tabs that identify the same recruiter more than once, or conflict with that recruiter's already-registered different source, are skipped rather than silently replacing or double-counting it. To switch sources, disconnect the old one first.

The **Registered live recruiter sheets** list shows each recruiter/tab and its last sync time or any sync error. Use **Disconnect** to remove a Google Sheet from RecruiterPulse. This stops its live sync and removes its column mappings, but does not delete the Google tab or historical reports. You can register that tab again later.

## 4. Connect recruiter calendars

1. On **Spreadsheets & Data Sources**, find **Recruiter interview calendars**.
2. For each recruiter whose interview count should be reported, paste that recruiter's Calendar ID and choose **Save Calendar**. A calendar ID is often an email address, but use the value shown under **Integrate calendar** in Google Calendar.
3. Ensure the calendar is shared with the service-account email as **See all event details**. Do not share passwords or grant edit access.
4. In **Hourly MIS Review & Approval**, choose **Sync Live Sheets** to refresh calls and fetch interviews. Scheduled report syncs fetch them automatically.

RecruiterPulse counts non-cancelled events from midnight to midnight **tomorrow**, in the workspace timezone. For a Sunday report, tomorrow is Monday. Calendar counts appear on the corresponding recruiter row and in the team total. If a calendar is missing or inaccessible, the MIS report displays a warning; correct the calendar ID or sharing permission and sync again. Recruiters without a counted call row remain omitted from that day's report.

## 5. Daily recruiter workflow

1. Recruiters continue updating their existing Google Sheets call logs. Keep the date, call status, and (where used) role columns populated consistently.
2. Leave the backend running. It refreshes registered sheets automatically at the configured interval.
3. Open **Hourly MIS Review & Approval**. The report view refreshes periodically while open. To fetch immediately, choose **Sync Live Sheets**.
4. Check the reporting date, recruiter list, roles, connected calls, not-connected calls, and total calls before approving.
5. If any row looks wrong, choose **Edit report**. Update roles (comma-separated), connected calls, not-connected calls, and tomorrow's interviews. Totals and connection rates recalculate automatically. Save the edits or cancel them.
6. Choose **Approve** to publish the report to the management dashboard. Choose **Reject** and enter a reason if it needs correction.
7. **Copy for WhatsApp** copies the displayed report summary.

Saved edits are recorded in the audit log and are preserved from automatic refreshes for that report slot. A later hourly report slot is generated from the live sheets again. Once approved or rejected, a report can no longer be edited.

Recruiters with no counted calls for the reporting date are left out of the report. Blank call statuses do not count as calls. A row is counted when it has a valid reporting date and a classifiable call status; `Not Connected` counts as not connected, not connected. Totals equal connected plus not-connected calls. Roles are drawn from counted call rows. When a candidate identifier is available, duplicate candidate/status rows may be removed.

The reporting date uses the workspace timezone (currently Asia/Kolkata). Check that the sheet's dates represent the day the calls were made.

## 6. One-time imports

On **Spreadsheets & Data Sources**, **Analyze Google Sheet** imports the selected tab once and processes it immediately; it does not register recurring sync. Excel, XLS, and CSV uploads are also one-time imports. Use these for ad-hoc files, not as a substitute for registering live recruiter tabs.

## 7. Troubleshooting

- **“Default workspace is not provisioned”**: make sure the backend is running from the `backend` folder with `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`, then refresh the page.
- **Google HTTP 401/403 or “caller does not have permission”**: confirm the Google Sheets API is enabled, the key path points to a valid JSON key, the email in `.env` matches the key's service-account email, and the spreadsheet is shared with that email as Viewer. Restart the backend after editing `.env`.
- **Could not find the selected tab**: select the intended tab in the browser first and copy a URL containing its `gid`.
- **Recruiter name does not match the selected tab**: the app checks a detected `Recruiter` column before registering, to avoid attributing calls to the wrong person. Enter a recruiter name listed in that tab, or select the intended recruiter tab and copy its URL again.
- **Required date/status columns not detected**: check that the selected tab has a header row and recognizable date and call-status column names.
- **Sync failed**: open **Spreadsheets & Data Sources** and read the error shown beside the source. Fix the sheet access, URL, or column issue, then use **Sync Live Sheets** to retry. A failed sheet sync should not be treated as a successful zero-call report.
- **Calendar count is zero or has a warning**: verify that the Calendar API is enabled, the entered Calendar ID is exact, and the calendar is shared with the configured service-account email as **See all event details**. Then run **Sync Live Sheets** again.
- **Counts differ from the sheet**: compare only the target day's rows; check blank statuses, date formats, duplicate candidate/status rows, and whether every intended recruiter tab is registered. Inspect the totals before approving.
- **Browser shows old data**: confirm both backend and frontend terminals are still running, wait for the next refresh interval, or use **Sync Live Sheets**.

Do not send service-account JSON keys or candidate names, phone numbers, or emails when asking for help. Calendar interview counts require the Google Calendar API to be enabled, calendar IDs configured, and the calendars shared with the service account.
