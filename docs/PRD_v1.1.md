# RecruiterPulse — Product Requirements Document (PRD)

**Version:** 1.1 (Production-Ready Technical Specification)  
**Status:** Approved for Implementation  
**Product Category:** B2B Micro-SaaS  
**Target Market:** India (Initial) $\to$ International (Expansion)  
**Tagline:** *Your recruitment spreadsheets. One automated MIS dashboard.*

---

## 1. Product Vision & Executive Summary

RecruiterPulse automates repetitive Management Information System (MIS) reporting for recruitment and staffing agencies by consolidating recruiter activity from existing Google Sheets, Excel files, and Google Calendar.

Rather than forcing agencies to migrate to a complex, disruptive Applicant Tracking System (ATS), RecruiterPulse operates non-invasively on top of their existing workflows. It reduces reporting overhead from **~2.5 hours per day** (8 cycles $\times$ 20 minutes) to **under 2 minutes per cycle** (a single review-and-approve action).

---

## 2. Target Persona & User Roles

### 2.1 Target Segment
* Small to mid-sized recruitment & staffing agencies (3–15 recruiters).
* Agencies running on Google Sheets / Excel without an enterprise ATS.
* Dedicated MIS executives or team leads burdened with hourly status reporting.

### 2.2 Role-Based Access Control (RBAC)

| Role | Permissions & Responsibilities |
|---|---|
| **Agency Owner** | Workspace settings, subscription/billing, invite/remove users, audit access. |
| **Manager / Team Lead** | View live management dashboard, view historical trends, download reports. |
| **MIS Executive** | Connect/manage data sources, configure column mappings, review/edit hourly draft reports, approve/reject reports for management publishing. |
| **Recruiter** | Operates as usual in their designated Google Sheets or local files. No system login strictly required. |

*Multi-tenancy:* Strict schema or workspace-level data isolation ensures zero cross-agency visibility.

---

## 3. Core Architecture & Data Privacy (DPDP Compliance)

### 3.1 Data Minimization Pipeline (India DPDP Act 2023)
RecruiterPulse is a **metrics aggregation engine**, not an ATS or resume repository. To ensure compliance with the Digital Personal Data Protection (DPDP) Act 2023 and eliminate data-leak liability:

1. **In-Memory Ingestion:** Recruiter spreadsheets are read in-memory.
2. **Instant PII Stripping:** Candidate names, phone numbers, email addresses, and resume notes are used solely to count/deduplicate rows and are **immediately discarded**.
3. **Persisted Data:** Only anonymized aggregate metrics (`recruiter_id`, `reporting_date`, `hour_slot`, `connected_calls`, `not_connected_calls`, `total_calls`, `next_day_interviews`) are stored in the database.

```
┌─────────────────────────┐
│ Recruiter Google Sheets │
└───────────┬─────────────┘
            │ In-Memory Read (Ephemeral)
            ▼
┌─────────────────────────┐
│ Aggregation & Dedupe    │ ──> Strip Candidate PII (Names, Phones)
└───────────┬─────────────┘
            │ Anonymized Metric Totals
            ▼
┌─────────────────────────┐
│ RecruiterPulse Database │ (Stores only daily aggregates & audit logs)
└─────────────────────────┘
```

---

## 4. System Modules & Functional Requirements

### Module 1 — Workspace & Agency Onboarding
* **Workspace Setup:** Agency registration, workspace name, subdomain/slug, and timezone configuration (Default: `Asia/Kolkata` / IST).
* **Team Management:** Invite MIS executives, managers, and configure recruiter rosters (names, emails, active/inactive status).
* **Roster Mapping:** Each recruiter is associated with their respective data source(s) and calendar identifier.

---

### Module 2 — Data Source Ingestion Engine

To eliminate Google OAuth authentication friction and avoid verification delays with Google's restricted API scopes:

#### A. Google Sheets (Primary Method — Service Account)
* **Ingestion Model:** The agency shares recruiter spreadsheets with the system's dedicated Service Account email (e.g., `sync@recruiterpulse-engine.iam.gserviceaccount.com`) with `Viewer` (read-only) permissions.
* **Benefits:** Zero per-recruiter OAuth logins, zero token expirations, instant onboarding, guaranteed read-only security.
* **Sync Frequency:** Automated pre-fetch 5 minutes before each hourly reporting window.

#### B. Manual File Uploads (.xlsx, .csv)
* **Ingestion Model:** On-demand upload via MIS dashboard for agencies with offline Excel workflows.
* **Preview & Verification:** In-browser sheet preview with row count before processing.
* **Operational Distinction:** Automated hourly runs apply to cloud-connected sheets. Uploaded files generate reports on-demand upon upload.

---

### Module 3 — Smart Column Detection & Status Taxonomy

#### A. Column Mapping Engine
The system analyzes headers and sample row values (first 25 rows) using heuristic matching:

| Standard System Field | Target Type | Recognized Common Aliases |
|---|---|---|
| `activity_date` | Date | Call Date, Date, Calling Date, Created On, Timestamp, Log Date |
| `call_status` | String | Call Status, Call Outcome, Response, Connection Status, Status, Disposition |
| `candidate_ref` | String/Number | Candidate Name, Applicant Name, Phone, Contact Number, Lead ID (Used only for deduplication) |
| `job_role` | String | Role, Job Title, Position, Designation, Requirement, Client Profile |

* **Confidence Thresholds:**
  * Confidence $\ge 85\%$: Automatically suggested and pre-mapped.
  * Confidence $< 85\%$: Highlighted for explicit MIS confirmation.
* **Lock-in:** Mappings are saved per spreadsheet URL/file schema. Future syncs reuse confirmed mappings automatically.

#### B. Indian Call Status Taxonomy Engine
RecruiterPulse provides an agency-level taxonomy categorizer with pre-built Indian recruitment presets:

* **Connected (Productive Activity):**  
  `Spoke`, `Connected`, `Interested`, `Screening Done`, `Profile Shared`, `L1 Scheduled`, `Salary Discussed`, `Not Interested (Valid Connect)`, `Already Placed`.
* **Not Connected (Unproductive/Attempt):**  
  `RNR (Ringing No Response)`, `Busy`, `Switched Off`, `Out of Coverage`, `Wrong Number`, `Call Disconnected`, `Invalid Number`, `Voicemail`.
* **Ignored / Non-Call:**  
  `Duplicate`, `Do Not Call`, `Blank Rows`.

*Unmapped Status Handling:* When an unmapped status is detected during a sync, the report displays an "Unmapped Status Detected" warning, prompting the MIS executive to map it with one click before final approval.

---

### Module 4 — Activity Calculation Engine

#### Metrics & Formulas
1. **Total Calls:** $\text{Connected Calls} + \text{Not Connected Calls}$
2. **Connected Call Rate (%):**  
   $$\text{Connected Rate} = \begin{cases} \left(\frac{\text{Connected Calls}}{\text{Total Calls}}\right) \times 100 & \text{if } \text{Total Calls} > 0 \\ 0\% & \text{if } \text{Total Calls} = 0 \end{cases}$$
3. **Cumulative Daily Calculation:**  
   Every hourly report (12 PM through 7 PM) calculates the **cumulative total for the current calendar day** from 00:00 to the current hour, not isolated incremental hour blocks.
4. **Deduplication Safeguard:**  
   Rows sharing the identical `(Recruiter + Candidate Ref + Date + Hour)` within a 3-minute window are treated as duplicate entries and counted once.

---

### Module 5 — Google Calendar Integration (Next-Day Interviews)

#### Purpose & Scope
Fetches interviews scheduled for **Tomorrow** ($T+1$ relative to the reporting date) and maps them to the responsible recruiter.

#### Attribution Hierarchy
To resolve shared calendars or ambiguous calendar event titles:
1. **Rule 1 (Organizer/Creator):** Event creator email matches an active recruiter profile.
2. **Rule 2 (Attendee Match):** Recruiter email exists in the event attendee list.
3. **Rule 3 (Title/Description Syntax):** Event title or description contains recognized recruiter tags (e.g., `[Recruiter: Priya]`, `Owner: Priya Sharma`).
4. **Rule 4 (Fallback):** Events that cannot be attributed are grouped under an **"Unassigned Interviews"** pool on the approval screen, allowing the MIS executive to assign them to a recruiter with a single click.

#### Quality Filters
* **Status Check:** Excludes events marked as `cancelled` or `declined`.
* **Idempotency:** Rescheduled events tracked by persistent Google `event.id` to prevent double-counting across reporting snapshots.

---

### Module 6 & 7 — Hourly Report Generation & MIS Approval Workflow

#### Reporting Schedule (IST)
Automated daily runs at: **12:00 PM, 01:00 PM, 02:00 PM, 03:00 PM, 04:00 PM, 05:00 PM, 06:00 PM, 07:00 PM**.

#### Standard Report Layout

| Recruiter | Job Roles | Connected | Not Connected | Total Calls | Conn % | Next-Day Interviews |
|---|---|---:|---:|---:|---:|---:|
| Priya Sharma | Java Backend, DevOps | 28 | 14 | 42 | 66.7% | 3 |
| Rahul Verma | React Frontend | 18 | 17 | 35 | 51.4% | 1 |
| Amit Patel | Data Engineer | 38 | 13 | 51 | 74.5% | 2 |
| **Team Total** | **All Roles** | **84** | **44** | **128** | **65.6%** | **6** |

#### Approval Life Cycle & Queue Handling
1. **T - 5 Mins (Sync & Draft):** System triggers sync, runs calculations, and creates a `DRAFT_PENDING_APPROVAL` report.
2. **Review Window:** MIS executive receives a notification badge, inspects calculations, checks for unmapped statuses or unassigned interviews, and makes line adjustments if necessary.
3. **Decision:**
   * **Approve:** Report transitions to `APPROVED` status. Becomes visible on Management Dashboard, unlocks exports, and enables WhatsApp delivery.
   * **Reject:** Report is flagged with a reason (e.g., "Awaiting recruiter afternoon sheet sync"); remains internal.
4. **Superseding Rule:** If a newer hourly report is generated before the prior hour was approved, the newer cumulative snapshot supersedes the older draft. Management always sees the **most recently approved report**.

---

### Module 8 — Management Dashboard & Multi-Channel Distribution

#### 1. Web Dashboard
* Live KPIs: Total Calls, Connected Calls, Team Connection Rate, Active Recruiters, Tomorrow's Confirmed Interviews.
* Filters: Date selector, Recruiter dropdown, Job Role dropdown.
* Audit trail: Displays "Approved by [Name] at [HH:MM IST]".

#### 2. One-Click WhatsApp Export (Key Market Feature)
A dedicated **"Copy for WhatsApp"** button formats the approved report into a clean, WhatsApp-ready message for instant posting to agency leadership groups:

```text
📊 *RecruiterPulse MIS Report*  
📅 *Date:* 12-Nov-2026 | *Time:* 03:00 PM IST  
━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *Priya Sharma* (Java, DevOps)  
   Calls: 42 (28 Conn / 14 Not Conn) | 67% | 🎯 Intrvws: 3  

👤 *Rahul Verma* (Frontend)  
   Calls: 35 (18 Conn / 17 Not Conn) | 51% | 🎯 Intrvws: 1  

👤 *Amit Patel* (Data Eng)  
   Calls: 51 (38 Conn / 13 Not Conn) | 75% | 🎯 Intrvws: 2  
━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 *Team Total:* 128 Calls | 65.6% Conn Rate | 🎯 6 Next-Day Interviews  
✅ *Status:* Approved by MIS (Pooja K.)
```

#### 3. File Exports
* **Excel (.xlsx):** Pre-formatted workbook with summary sheet and recruiter breakdown sheets.
* **PDF (.pdf):** Clean single-page executive summary formatted for A4 printing/viewing.

---

## 5. Non-Functional & Technical Requirements

### 5.1 Security & Reliability
* **Data Isolation:** Tenant identifier (`workspace_id`) enforced across all database queries.
* **Read-Only Scope:** Service Account and OAuth connections must only request read permissions.
* **Rate-Limit Resilience:** Stagger Google Sheets API polling with exponential backoff to respect Google's quota limits (300 requests/min).
* **Audit Logging:** System logs every report generation, edit, approval, and rejection event with user timestamps.

### 5.2 Performance Targets
* End-to-end sync, calculation, and draft generation completed within **$< 45$ seconds** for a 15-recruiter agency workspace.
* UI page loads under 1.5 seconds on standard 4G Indian broadband.

---

## 6. Success Metrics & Validation Milestones

| Metric | Target | Measurement Method |
|---|---|---|
| **Data Accuracy** | $\ge 99.0\%$ | Verified against manual MIS audit sheets |
| **MIS Time Saved** | $> 80\%$ reduction | Baseline: 120 mins/day $\to$ Target: $< 20$ mins/day |
| **Zero PII Leakage** | 100% compliance | Zero candidate phone numbers/names persisted in DB |
| **Pilot Conversion** | At least 2 paying agencies | ₹3,000–₹7,000/mo subscription tier within 4 weeks of pilot |

---

## 7. Implementation Roadmap

```
Phase 1: Ingestion & Engine (Weeks 1–2)
├── Service Account Google Sheets Connector
├── In-Memory Deduplication & PII Stripping
├── Column Detection & Indian Call Status Categorizer
└── Calling Calculation Engine

Phase 2: Calendar & MIS Approval (Weeks 3–4)
├── Google Calendar Event Scraper & Attribution Logic
├── Hourly Scheduled Task Runner (Cumulative Snapshots)
└── MIS Review & Approval Workflow UI

Phase 3: Dashboard & Distribution (Weeks 5–6)
├── Management Dashboard & Analytics Views
├── WhatsApp Clipboard Formatter
├── Excel & PDF Export Generators
└── Pilot Deployment with 2 Partner Agencies
```

