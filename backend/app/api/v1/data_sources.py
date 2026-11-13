from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import io
import pandas as pd

from app.core.database import get_db
from app.models import (
    Workspace,
    DataSource,
    ColumnMapping,
    RecruiterProfile,
    StatusTaxonomy,
    HourlyReport,
    RecruiterDailyMetric,
    ReportStatus,
    SyncStatus,
    StandardField,
    AuditLog,
    AuditAction,
)
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    ColumnDetectionResponse,
    ColumnMappingItem,
    ConfirmMappingRequest,
)
from app.services.column_detector import ColumnDetector
from app.services.calculation_engine import CalculationEngine
from app.services.spreadsheet_parser import SpreadsheetParser
from app.services.google_sheets_worker import GoogleSheetsWorker

router = APIRouter(prefix="/data-sources", tags=["Data Sources & Column Mapping"])


@router.post("/detect-from-file", response_model=ColumnDetectionResponse)
async def detect_columns_from_file(request: Request):
    """
    Analyzes an uploaded Excel (.xlsx) or CSV file and suggests standardized column mappings
    with confidence scores and sample values.
    """
    form = await request.form()
    file = form.get("file")
    if not file or not hasattr(file, "read"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded.")

    content = await file.read()
    await file.close()
    filename = getattr(file, "filename", "") or ""

    try:
        df, detected_sheet = SpreadsheetParser.parse_file(content, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse spreadsheet: {str(e)}"
        )

    detections = ColumnDetector.analyze_dataframe(df)

    formatted_mappings = {}
    for standard_field, item in detections.items():
        formatted_mappings[standard_field.value] = ColumnMappingItem(
            standard_field=standard_field,
            source_column=item["source_column"],
            confidence=item["confidence"],
            sample_values=item["sample_values"],
            is_confirmed=item["auto_confirmed"]
        )

    return ColumnDetectionResponse(
        total_columns_found=len(df.columns),
        detected_mappings=formatted_mappings
    )


@router.post("/process-real-file")
async def process_real_file(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Directly ingests a recruiter's real file (.xlsx, .xls, .csv):
    1. Supports single-recruiter sheets or multi-recruiter master sheets
    2. Auto-detects columns including Recruiter, Date, Status, Candidate, Role
    3. Calculates real calling metrics per recruiter
    4. Updates database HourlyReport & RecruiterDailyMetric so results immediately show on the UI
    """
    form = await request.form()
    file = form.get("file")
    google_sheet_url = str(form.get("google_sheet_url") or "").strip()
    if not (file and hasattr(file, "read")) and not google_sheet_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a file or provide a Google Sheets URL."
        )

    workspace_id = str(form.get("workspace_id") or "ws-apex-101")
    raw_recruiter = form.get("recruiter_name")
    recruiter_name = str(raw_recruiter) if raw_recruiter else None
    raw_date = form.get("target_date_str")
    target_date_str = str(raw_date) if raw_date else None

    if file and hasattr(file, "read"):
        content = await file.read()
        await file.close()
        filename = getattr(file, "filename", "") or "recruiter_data.xlsx"
    else:
        parsed_url = urlparse(google_sheet_url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in ("docs.google.com", "www.docs.google.com"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide an HTTPS URL from docs.google.com."
            )
        try:
            google_df = await GoogleSheetsWorker.fetch_sheet_dataframe(google_sheet_url)
            if google_df.empty:
                raise ValueError("The selected Google Sheets tab is empty.")
            content = google_df.to_csv(index=False).encode("utf-8")
            filename = "google_sheet.csv"
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to read Google Sheet: {exc}"
            ) from exc

    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            parsed_sheets = SpreadsheetParser.parse_excel_sheets(content)
        else:
            parsed_df, detected_sheet = SpreadsheetParser.parse_file(content, filename)
            parsed_sheets = [(parsed_df, detected_sheet)]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}"
        )

    if recruiter_name in ("__auto__", ""):
        recruiter_name = None
    process_all_recruiters = recruiter_name in (None, "Agency Master Sheet (All Recruiters)")
    canonical_names = {
        StandardField.ACTIVITY_DATE: "Activity Date",
        StandardField.CALL_STATUS: "Call Status",
        StandardField.CANDIDATE_REF: "Candidate",
        StandardField.JOB_ROLE: "Job Role",
        StandardField.RECRUITER_NAME: "Recruiter",
    }
    normalized_sheets = []
    detections = None
    detected_sheet_names = []

    for source_df, sheet_name in parsed_sheets:
        sheet_detections = ColumnDetector.analyze_dataframe(source_df)
        sheet_mapping = {
            field: item["source_column"]
            for field, item in sheet_detections.items()
            if item["source_column"] is not None
        }

        if StandardField.CALL_STATUS not in sheet_mapping:
            for column in source_df.columns:
                cleaned = ColumnDetector.clean_header(column)
                if any(term in cleaned for term in ("status", "outcome", "disposition", "remark", "response", "result")):
                    sheet_mapping[StandardField.CALL_STATUS] = column
                    sheet_detections[StandardField.CALL_STATUS] = {
                        "source_column": column,
                        "confidence": 0.75,
                        "sample_values": [str(value) for value in source_df[column].dropna().head(3).tolist()],
                        "auto_confirmed": False
                    }
                    break

        if StandardField.CALL_STATUS not in sheet_mapping:
            continue

        if detections is None or sum(item["source_column"] is not None for item in sheet_detections.values()) > sum(
            item["source_column"] is not None for item in detections.values()
        ):
            detections = sheet_detections
        detected_sheet_names.append(sheet_name or "CSV")

        recruiter_source = sheet_mapping.get(StandardField.RECRUITER_NAME)
        source_subset = source_df
        if recruiter_source and not process_all_recruiters and recruiter_name:
            recruiter_values = source_df[recruiter_source].astype(str).str.strip().str.casefold()
            source_subset = source_df[recruiter_values == recruiter_name.strip().casefold()]

        normalized = pd.DataFrame(index=source_subset.index)
        for field, canonical_name in canonical_names.items():
            source_column = sheet_mapping.get(field)
            if source_column and source_column in source_subset.columns:
                normalized[canonical_name] = source_subset[source_column]
        if "Recruiter" in normalized.columns:
            normalized["Recruiter"] = normalized["Recruiter"].replace(r"^\s*$", pd.NA, regex=True).ffill()

        if recruiter_name and not process_all_recruiters:
            normalized["Recruiter"] = recruiter_name
        elif "Recruiter" not in normalized.columns:
            fallback_name = sheet_name if len(parsed_sheets) > 1 and sheet_name else filename.rsplit(".", 1)[0]
            normalized["Recruiter"] = str(fallback_name).strip()

        normalized_sheets.append(normalized)

    if not normalized_sheets or detections is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not detect a Call Status / Outcome column. Please ensure your sheet has a column like 'Call Status', 'Status', 'Outcome', or 'Disposition'."
        )

    df = pd.concat(normalized_sheets, ignore_index=True)
    detected_sheet = ", ".join(detected_sheet_names)
    col_mapping = {
        field: canonical_names[field]
        for field in canonical_names
        if canonical_names[field] in df.columns
    }

    # 2. Date Column & Target Date Selection
    date_col = col_mapping.get(StandardField.ACTIVITY_DATE)
    target_date: Optional[date] = None

    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_date_str must use YYYY-MM-DD format."
            ) from exc

    if target_date is None and date_col and date_col in df.columns:
        parsed_dates = CalculationEngine.parse_date_series(df[date_col]).dropna()
        if not parsed_dates.empty:
            target_date = parsed_dates.max().date()
        else:
            target_date = date.today()
    elif target_date is None:
        target_date = date.today()

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' was not found. Run the backend seed script or provide a valid workspace ID."
        )

    # 3. Load Workspace Taxonomy
    taxonomies = db.query(StatusTaxonomy).filter(StatusTaxonomy.workspace_id == workspace_id).all()
    taxonomy_lookup = {t.raw_status.lower().strip(): t.category for t in taxonomies}

    # 4. Check for Multi-Recruiter Sheet
    recruiter_col = col_mapping.get(StandardField.RECRUITER_NAME)
    is_master_sheet = (
        recruiter_col is not None
        and recruiter_col in df.columns
        and (recruiter_name is None or recruiter_name == "Agency Master Sheet (All Recruiters)")
        and df[recruiter_col].dropna().nunique() > 1
    )

    # Update the existing draft for this day, but never mutate an approved report.
    report = db.query(HourlyReport).filter(
        HourlyReport.workspace_id == workspace_id,
        HourlyReport.reporting_date == target_date,
        HourlyReport.status == ReportStatus.DRAFT_PENDING_APPROVAL
    ).order_by(HourlyReport.created_at.desc()).first()

    if not report:
        current_hour = datetime.now(ZoneInfo(workspace.timezone)).hour
        existing_slots = {
            slot for (slot,) in db.query(HourlyReport.hour_slot).filter(
                HourlyReport.workspace_id == workspace_id,
                HourlyReport.reporting_date == target_date
            ).all()
        }
        available_hours = [(current_hour + offset) % 24 for offset in range(24)]
        hour_slot = next(
            (f"{hour:02d}:00" for hour in available_hours if f"{hour:02d}:00" not in existing_slots),
            f"{current_hour:02d}:00"
        )
        report = HourlyReport(
            workspace_id=workspace_id,
            reporting_date=target_date,
            hour_slot=hour_slot,
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={}
        )
        db.add(report)
        db.flush()

    processed_recruiters = []
    overall_calc_res = None
    all_unmapped = set()

    if is_master_sheet:
        # Process each recruiter individually from the master sheet
        grouped = df.groupby(recruiter_col)
        for r_name, group_df in grouped:
            clean_name = str(r_name).strip()
            if not clean_name or clean_name.lower() in ("nan", "none", "-", "total"):
                continue

            recruiter = db.query(RecruiterProfile).filter(
                RecruiterProfile.workspace_id == workspace_id,
                RecruiterProfile.full_name == clean_name
            ).first()
            if not recruiter:
                recruiter = RecruiterProfile(
                    workspace_id=workspace_id,
                    full_name=clean_name,
                    is_active=True
                )
                db.add(recruiter)
                db.flush()

            calc_res = CalculationEngine.calculate_recruiter_activity(
                df=group_df,
                column_mapping=col_mapping,
                status_taxonomy=taxonomy_lookup,
                target_date=target_date
            )
            all_unmapped.update(calc_res.unmapped_statuses)

            metric = db.query(RecruiterDailyMetric).filter(
                RecruiterDailyMetric.hourly_report_id == report.id,
                RecruiterDailyMetric.recruiter_id == recruiter.id
            ).first()
            if not metric:
                metric = RecruiterDailyMetric(
                    hourly_report_id=report.id,
                    recruiter_id=recruiter.id
                )
                db.add(metric)

            metric.job_roles = calc_res.job_roles
            metric.connected_calls = calc_res.connected_calls
            metric.not_connected_calls = calc_res.not_connected_calls
            metric.total_calls = calc_res.total_calls
            metric.connected_rate = calc_res.connected_rate
            metric.next_day_interviews = 0

            processed_recruiters.append({
                "name": clean_name,
                "total_calls": calc_res.total_calls,
                "connected_calls": calc_res.connected_calls,
                "connected_rate": calc_res.connected_rate,
                "job_roles": calc_res.job_roles
            })

        # Include recruiter identity in the dedupe key when calculating team totals.
        overall_df = df.copy()
        if "Candidate" in overall_df.columns:
            overall_df["Candidate"] = (
                overall_df["Recruiter"].astype(str) + "|" + overall_df["Candidate"].astype(str)
            )
        overall_calc_res = CalculationEngine.calculate_recruiter_activity(
            df=overall_df,
            column_mapping=col_mapping,
            status_taxonomy=taxonomy_lookup,
            target_date=target_date
        )

    else:
        # Single recruiter file
        detected_recruiters = df[recruiter_col].dropna().astype(str).str.strip().unique() if recruiter_col else []
        name_to_use = (
            recruiter_name
            or (detected_recruiters[0] if len(detected_recruiters) == 1 else None)
            or filename.rsplit(".", 1)[0].replace("_", " ").title()
        )
        if name_to_use == "Agency Master Sheet (All Recruiters)":
            name_to_use = filename.split(".")[0].replace("_", " ").title()

        recruiter = db.query(RecruiterProfile).filter(
            RecruiterProfile.workspace_id == workspace_id,
            RecruiterProfile.full_name == name_to_use
        ).first()

        if not recruiter:
            recruiter = RecruiterProfile(
                workspace_id=workspace_id,
                full_name=name_to_use,
                is_active=True
            )
            db.add(recruiter)
            db.flush()

        overall_calc_res = CalculationEngine.calculate_recruiter_activity(
            df=df,
            column_mapping=col_mapping,
            status_taxonomy=taxonomy_lookup,
            target_date=target_date
        )
        all_unmapped.update(overall_calc_res.unmapped_statuses)

        metric = db.query(RecruiterDailyMetric).filter(
            RecruiterDailyMetric.hourly_report_id == report.id,
            RecruiterDailyMetric.recruiter_id == recruiter.id
        ).first()

        if not metric:
            metric = RecruiterDailyMetric(
                hourly_report_id=report.id,
                recruiter_id=recruiter.id
            )
            db.add(metric)

        metric.job_roles = overall_calc_res.job_roles
        metric.connected_calls = overall_calc_res.connected_calls
        metric.not_connected_calls = overall_calc_res.not_connected_calls
        metric.total_calls = overall_calc_res.total_calls
        metric.connected_rate = overall_calc_res.connected_rate
        metric.next_day_interviews = 0

        processed_recruiters.append({
            "name": recruiter.full_name,
            "total_calls": overall_calc_res.total_calls,
            "connected_calls": overall_calc_res.connected_calls,
            "connected_rate": overall_calc_res.connected_rate,
            "job_roles": overall_calc_res.job_roles
        })

    if not processed_recruiters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recruiter rows were found for the selected recruiter and reporting date."
        )

    # Recalculate summary totals across all metrics in this report
    db.flush()
    all_metrics = db.query(RecruiterDailyMetric).filter(
        RecruiterDailyMetric.hourly_report_id == report.id
    ).all()

    tot = sum(m.total_calls for m in all_metrics)
    conn = sum(m.connected_calls for m in all_metrics)
    n_conn = sum(m.not_connected_calls for m in all_metrics)
    rate = round((conn / tot * 100), 2) if tot > 0 else 0.0
    intrv = sum(m.next_day_interviews for m in all_metrics)

    report.summary_totals = {
        "total_calls": tot,
        "connected_calls": conn,
        "not_connected_calls": n_conn,
        "connected_rate": rate,
        "next_day_interviews": intrv,
        "active_recruiters_count": len(all_metrics)
    }

    db.add(AuditLog(
        workspace_id=workspace_id,
        action=AuditAction.REPORT_GENERATED,
        details={
            "report_id": report.id,
            "reporting_date": str(target_date),
            "sheets": detected_sheet_names,
            "filename": filename
        }
    ))
    db.commit()

    return {
        "status": "success",
        "filename": filename,
        "sheet_name": detected_sheet,
        "recruiter_name": "Multiple Recruiters" if is_master_sheet else processed_recruiters[0]["name"],
        "is_master_sheet": is_master_sheet,
        "recruiters_processed": processed_recruiters,
        "reporting_date": str(target_date),
        "total_rows_in_file": overall_calc_res.total_rows_processed if overall_calc_res else len(df),
        "duplicates_removed": overall_calc_res.duplicates_removed if overall_calc_res else 0,
        "detected_columns": {
            field.value: {
                "source_column": res["source_column"],
                "confidence": res["confidence"],
                "sample_values": res["sample_values"],
                "auto_confirmed": res["auto_confirmed"]
            }
            for field, res in detections.items()
        },
        "metrics": overall_calc_res.to_dict() if overall_calc_res else {},
        "unmapped_statuses": sorted(list(all_unmapped)),
        "report_id": report.id
    }


@router.post("/confirm-mappings")
def confirm_mappings(payload: ConfirmMappingRequest, db: Session = Depends(get_db)):
    """
    Saves and confirms the column mapping for a specific data source.
    Transitions data source status to ACTIVE.
    """
    ds = db.query(DataSource).filter(DataSource.id == payload.data_source_id).first()
    if not ds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found.")

    # Remove existing mappings if re-confirming
    db.query(ColumnMapping).filter(ColumnMapping.data_source_id == ds.id).delete()

    for standard_field, source_col in payload.mappings.items():
        mapping = ColumnMapping(
            data_source_id=ds.id,
            standard_field=standard_field,
            source_column_name=source_col,
            confidence_score=1.0,
            is_confirmed=True
        )
        db.add(mapping)

    ds.sync_status = SyncStatus.ACTIVE
    db.commit()

    return {"message": "Column mappings confirmed successfully.", "status": ds.sync_status}


@router.post("/{workspace_id}", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_data_source(workspace_id: str, payload: DataSourceCreate, db: Session = Depends(get_db)):
    """Registers a spreadsheet or file data source for an agency or recruiter."""
    ds = DataSource(
        workspace_id=workspace_id,
        recruiter_id=payload.recruiter_id,
        source_type=payload.source_type,
        name=payload.name,
        sheet_id_or_url=payload.sheet_id_or_url,
        sheet_tab_name=payload.sheet_tab_name,
        sync_status=SyncStatus.PENDING_MAPPING
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds
