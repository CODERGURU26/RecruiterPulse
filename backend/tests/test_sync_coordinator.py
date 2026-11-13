import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    CallCategory,
    ColumnMapping,
    DataSource,
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
                )
            ])
        db.commit()

        target_day = date(2026, 11, 13)

        async def fetch_sheet(sheet_id, _tab_name):
            sheet_date = target_day if sheet_id == "active-sheet" else target_day - timedelta(days=1)
            return pd.DataFrame({
                "Date": [sheet_date.strftime("%d/%m/%Y")],
                "Status": ["Connected"],
                "Role": [f"{sheet_id} role"]
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
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
