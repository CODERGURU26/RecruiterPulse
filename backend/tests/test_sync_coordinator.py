import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    AuditAction,
    AuditLog,
    CallCategory,
    ColumnMapping,
    DataSource,
    HourlyReport,
    RecruiterProfile,
    SourceType,
    StandardField,
    StatusTaxonomy,
    SyncStatus,
    Workspace,
)
from app.services.sync_coordinator import SyncCoordinator


class TestSyncCoordinator(unittest.IsolatedAsyncioTestCase):
    async def test_report_contains_only_recruiters_with_calls_for_the_day(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        workspace = Workspace(
            id="sync-active-workspace",
            name="Sync Active Test",
            slug="sync-active-test",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.add_all([
            StatusTaxonomy(
                workspace_id=workspace.id,
                raw_status="connected",
                category=CallCategory.CONNECTED,
                is_default=True
            ),
            StatusTaxonomy(
                workspace_id=workspace.id,
                raw_status="rnr",
                category=CallCategory.NOT_CONNECTED,
                is_default=True
            )
        ])

        recruiters = [
            RecruiterProfile(workspace_id=workspace.id, full_name=name)
            for name in ("Active Recruiter", "Old Sheet Recruiter", "No Sheet Recruiter")
        ]
        db.add_all(recruiters)
        db.flush()

        for recruiter, sheet_id in zip(recruiters[:2], ("active-sheet", "old-sheet")):
            data_source = DataSource(
                workspace_id=workspace.id,
                recruiter_id=recruiter.id,
                source_type=SourceType.GOOGLE_SHEET,
                name=f"{recruiter.full_name} sheet",
                sheet_id_or_url=sheet_id,
                sync_status=SyncStatus.ACTIVE
            )
            db.add(data_source)
            db.flush()
            db.add_all([
                ColumnMapping(
                    data_source_id=data_source.id,
                    standard_field=StandardField.ACTIVITY_DATE,
                    source_column_name="Date"
                ),
                ColumnMapping(
                    data_source_id=data_source.id,
                    standard_field=StandardField.CALL_STATUS,
                    source_column_name="Status"
                ),
                ColumnMapping(
                    data_source_id=data_source.id,
                    standard_field=StandardField.JOB_ROLE,
                    source_column_name="Role"
                ),
                ColumnMapping(
                    data_source_id=data_source.id,
                    standard_field=StandardField.RECRUITER_NAME,
                    source_column_name="Recruiter"
                )
            ])
        db.commit()

        target_day = date(2026, 11, 13)

        async def fetch_sheet(sheet_id, _tab_name):
            sheet_date = target_day if sheet_id == "active-sheet" else target_day - timedelta(days=1)
            recruiter_name = (
                "Active Recruiter" if sheet_id == "active-sheet" else "Old Sheet Recruiter"
            )
            return pd.DataFrame({
                "Date": [sheet_date.strftime("%d/%m/%Y"), sheet_date.strftime("%d/%m/%Y")],
                "Status": ["Connected", "Connected"],
                "Role": [f"{sheet_id} role", "Other recruiter's role"],
                "Recruiter": [recruiter_name, "Other Recruiter"]
            })

        try:
            with patch(
                "app.services.sync_coordinator.GoogleSheetsWorker.fetch_sheet_dataframe",
                new=AsyncMock(side_effect=fetch_sheet)
            ):
                report = await SyncCoordinator.run_workspace_sync(
                    workspace_id=workspace.id,
                    db=db,
                    override_date=target_day,
                    override_slot="12:00"
                )

            self.assertEqual(report.summary_totals["total_calls"], 1)
            self.assertEqual(report.summary_totals["connected_calls"], 1)
            self.assertEqual(report.summary_totals["not_connected_calls"], 0)
            self.assertEqual(report.summary_totals["active_recruiters_count"], 1)
            self.assertEqual(
                [metric.recruiter.full_name for metric in report.metrics],
                ["Active Recruiter"]
            )
            self.assertEqual(report.metrics[0].job_roles, ["active-sheet role"])

            edited_metric = report.metrics[0]
            edited_metric.connected_calls = 7
            edited_metric.not_connected_calls = 2
            edited_metric.total_calls = 9
            edited_metric.connected_rate = 77.78
            report.summary_totals = {
                **report.summary_totals,
                "connected_calls": 7,
                "not_connected_calls": 2,
                "total_calls": 9,
                "connected_rate": 77.78
            }
            db.add(AuditLog(
                workspace_id=workspace.id,
                action=AuditAction.REPORT_EDITED,
                details={"report_id": report.id, "metrics": []}
            ))
            db.commit()
            edited_metric_id = edited_metric.id

            with patch(
                "app.services.sync_coordinator.GoogleSheetsWorker.fetch_sheet_dataframe",
                new=AsyncMock(side_effect=fetch_sheet)
            ):
                refreshed = await SyncCoordinator.run_workspace_sync(
                    workspace_id=workspace.id,
                    db=db,
                    override_date=target_day,
                    override_slot="12:00"
                )

            self.assertEqual(refreshed.id, report.id)
            self.assertEqual(refreshed.summary_totals["total_calls"], 9)
            self.assertEqual(refreshed.metrics[0].id, edited_metric_id)
            self.assertEqual(refreshed.metrics[0].connected_calls, 7)
            self.assertEqual(refreshed.metrics[0].not_connected_calls, 2)
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    async def test_failed_live_source_does_not_create_empty_report(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        workspace = Workspace(
            id="sync-failure-workspace",
            name="Sync Failure Test",
            slug="sync-failure-test",
            timezone="Asia/Kolkata"
        )
        recruiter = RecruiterProfile(workspace_id=workspace.id, full_name="Live Recruiter")
        db.add_all([workspace, recruiter])
        db.flush()
        source = DataSource(
            workspace_id=workspace.id,
            recruiter_id=recruiter.id,
            source_type=SourceType.GOOGLE_SHEET,
            name="Live Recruiter sheet",
            sheet_id_or_url="sheet-id",
            sync_status=SyncStatus.ACTIVE
        )
        db.add(source)
        db.flush()
        db.add_all([
            ColumnMapping(
                data_source_id=source.id,
                standard_field=StandardField.ACTIVITY_DATE,
                source_column_name="Date"
            ),
            ColumnMapping(
                data_source_id=source.id,
                standard_field=StandardField.CALL_STATUS,
                source_column_name="Status"
            )
        ])
        db.commit()

        try:
            with patch(
                "app.services.sync_coordinator.GoogleSheetsWorker.fetch_sheet_dataframe",
                new=AsyncMock(side_effect=PermissionError("Google Sheets access denied"))
            ):
                with self.assertRaisesRegex(RuntimeError, "report was not changed"):
                    await SyncCoordinator.run_workspace_sync(
                        workspace_id=workspace.id,
                        db=db,
                        override_date=date(2026, 11, 13),
                        override_slot="12:00"
                    )

            self.assertEqual(
                db.query(HourlyReport).filter_by(workspace_id=workspace.id).count(),
                0
            )
            self.assertIn("access denied", source.last_error_message)
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
