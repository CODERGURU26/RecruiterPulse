import io
import unittest
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.core.database import Base, get_db
from app.main import app
from app.models import (
    CallCategory,
    ColumnMapping,
    DataSource,
    RecruiterProfile,
    StandardField,
    StatusTaxonomy,
    SyncStatus,
    Workspace,
)


class TestRealFileProcessing(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.session_factory = sessionmaker(bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)
        cls.engine.dispose()

    async def test_excel_tabs_generate_real_recruiter_report(self):
        db = self.session_factory()
        workspace = Workspace(
            id="upload-test-workspace",
            name="Upload Test",
            slug="upload-test",
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
        db.commit()
        workspace_id = workspace.id
        db.close()

        workbook = io.BytesIO()
        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            recruiter_tabs = {
                "Priya Sharma": [
                    ("12/11/2026", "Connected", "Candidate 1", "Software Engineer"),
                    ("12/11/2026", "RNR", "Candidate 2", "QA Engineer"),
                ],
                "Rahul Verma": [
                    ("12/11/2026", "RNR", "Candidate 3", "DevOps Engineer"),
                ],
                "Amit Patel": [
                    ("11/11/2026", "Connected", "Candidate 4", "Data Engineer"),
                ],
            }
            for recruiter, rows in recruiter_tabs.items():
                pd.DataFrame([
                    ["Date", "Call Status", "Candidate", "Profile"],
                    *rows
                ]).to_excel(writer, sheet_name=recruiter, index=False, header=False)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/data-sources/process-real-file",
                data={
                    "workspace_id": workspace_id,
                    "target_date_str": "2026-11-12"
                },
                files={
                    "file": (
                        "calling_data.xlsx",
                        workbook.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                }
            )
            report_response = await client.get(
                f"/api/v1/reports/pending?workspace_id={workspace_id}"
            )
            specific_recruiter_response = await client.post(
                "/api/v1/data-sources/process-real-file",
                data={
                    "workspace_id": workspace_id,
                    "target_date_str": "2026-11-12",
                    "recruiter_name": "Priya Sharma"
                },
                files={
                    "file": (
                        "calling_data.xlsx",
                        workbook.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                }
            )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["reporting_date"], "2026-11-12")
        self.assertEqual(result["metrics"]["total_calls"], 3)
        self.assertEqual(result["metrics"]["connected_calls"], 1)
        self.assertEqual(result["metrics"]["not_connected_calls"], 2)
        self.assertTrue(result["is_master_sheet"])
        self.assertEqual(
            {recruiter["name"] for recruiter in result["recruiters_processed"]},
            {"Priya Sharma", "Rahul Verma"}
        )
        priya = next(
            recruiter for recruiter in result["recruiters_processed"]
            if recruiter["name"] == "Priya Sharma"
        )
        self.assertEqual(priya["total_calls"], 2)
        self.assertEqual(priya["job_roles"], ["QA Engineer", "Software Engineer"])
        self.assertEqual(report_response.status_code, 200, report_response.text)
        report_data = report_response.json()
        self.assertEqual(report_data["summary_totals"]["total_calls"], 3)
        self.assertEqual(report_data["summary_totals"]["active_recruiters_count"], 2)
        self.assertEqual(
            {metric["recruiter_name"] for metric in report_data["metrics"]},
            {"Priya Sharma", "Rahul Verma"}
        )
        self.assertEqual(report_data["summary_totals"]["next_day_interviews"], 0)
        self.assertEqual(specific_recruiter_response.status_code, 200, specific_recruiter_response.text)
        self.assertEqual(specific_recruiter_response.json()["metrics"]["total_calls"], 2)
        self.assertEqual(
            [recruiter["name"] for recruiter in specific_recruiter_response.json()["recruiters_processed"]],
            ["Priya Sharma"]
        )

        stale_workbook = io.BytesIO()
        with pd.ExcelWriter(stale_workbook, engine="openpyxl") as writer:
            for recruiter in ("Priya Sharma", "Rahul Verma", "Amit Patel"):
                pd.DataFrame([
                    ["Date", "Call Status", "Candidate", "Profile"],
                    ["11/11/2026", "Connected", f"{recruiter} Candidate", "Old Role"]
                ]).to_excel(writer, sheet_name=recruiter, index=False, header=False)

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            empty_upload = await client.post(
                "/api/v1/data-sources/process-real-file",
                data={
                    "workspace_id": workspace_id,
                    "target_date_str": "2026-11-12"
                },
                files={
                    "file": (
                        "calling_data.xlsx",
                        stale_workbook.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                }
            )
            empty_report = await client.get(
                f"/api/v1/reports/pending?workspace_id={workspace_id}"
            )

        self.assertEqual(empty_upload.status_code, 200, empty_upload.text)
        self.assertEqual(empty_upload.json()["recruiters_processed"], [])
        self.assertEqual(empty_report.status_code, 200, empty_report.text)
        self.assertEqual(empty_report.json()["metrics"], [])
        self.assertEqual(empty_report.json()["summary_totals"]["active_recruiters_count"], 0)
        self.assertEqual(empty_report.json()["summary_totals"]["total_calls"], 0)

        with patch(
            "app.api.v1.data_sources.GoogleSheetsWorker.fetch_sheet_dataframe",
            new=AsyncMock(return_value=pd.DataFrame({
                "Date": ["13/11/2026"],
                "Call Status": ["Connected"],
                "Candidate": ["Candidate Google"],
                "Profile": ["QA Engineer"]
            }))
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                missing_google_recruiter = await client.post(
                    "/api/v1/data-sources/process-real-file",
                    data={
                        "workspace_id": workspace_id,
                        "target_date_str": "2026-11-13",
                        "google_sheet_url": "https://docs.google.com/spreadsheets/d/example/edit?gid=123"
                    }
                )
                google_response = await client.post(
                    "/api/v1/data-sources/process-real-file",
                    data={
                        "workspace_id": workspace_id,
                        "target_date_str": "2026-11-13",
                        "recruiter_name": "Nina Shah",
                        "google_sheet_url": "https://docs.google.com/spreadsheets/d/example/edit?gid=123"
                    }
                )

        self.assertEqual(missing_google_recruiter.status_code, 400, missing_google_recruiter.text)
        self.assertIn("Enter the recruiter name", missing_google_recruiter.json()["detail"])
        self.assertEqual(google_response.status_code, 200, google_response.text)
        self.assertEqual(google_response.json()["metrics"]["total_calls"], 1)
        self.assertEqual(google_response.json()["recruiter_name"], "Nina Shah")

    async def test_upload_defaults_to_workspace_today_not_latest_old_date(self):
        workspace_today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        db = self.session_factory()
        workspace = Workspace(
            id="today-default-workspace",
            name="Today Default Test",
            slug="today-default-test",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.add(StatusTaxonomy(
            workspace_id=workspace.id,
            raw_status="connected",
            category=CallCategory.CONNECTED,
            is_default=True
        ))
        db.commit()
        workspace_id = workspace.id
        db.close()

        file_buffer = io.BytesIO()
        pd.DataFrame({
            "Date": [
                (workspace_today - timedelta(days=1)).strftime("%d/%m/%Y"),
                workspace_today.strftime("%d/%m/%Y")
            ],
            "Call Status": ["Connected", "Connected"],
            "Candidate": ["Yesterday", "Today"],
            "Profile": ["Old Role", "Current Role"]
        }).to_csv(file_buffer, index=False)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/data-sources/process-real-file",
                data={"workspace_id": workspace_id, "recruiter_name": "Today Recruiter"},
                files={"file": ("daily.csv", file_buffer.getvalue(), "text/csv")}
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["reporting_date"], workspace_today.isoformat())
        self.assertEqual(response.json()["metrics"]["total_calls"], 1)
        self.assertEqual(response.json()["metrics"]["job_roles"], ["Current Role"])

    async def test_live_sheet_registration_saves_explicit_tab_and_rejects_job_source(self):
        db = self.session_factory()
        workspace = Workspace(
            id="live-sheet-test-workspace",
            name="Live Sheet Test",
            slug="live-sheet-test",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.commit()
        workspace_id = workspace.id
        db.close()

        sheet_url = "https://docs.google.com/spreadsheets/d/example/edit?gid=123"
        sheet_dataframe = pd.DataFrame({
            "Activity Date": ["13/11/2026"],
            "Call Status": ["Connected"],
            "Job Role": ["QA Engineer"]
        })
        transport = httpx.ASGITransport(app=app)
        fetch_mock = AsyncMock(return_value=sheet_dataframe)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.fetch_sheet_dataframe",
                new=fetch_mock
            ):
                response = await client.post(
                    f"/api/v1/data-sources/{workspace_id}/google-sheet",
                    json={"recruiter_name": "Tanmay", "sheet_url": sheet_url}
                )
                rejected_portal = await client.post(
                    f"/api/v1/data-sources/{workspace_id}/google-sheet",
                    json={"recruiter_name": "Naukri", "sheet_url": sheet_url}
                )

            sources_response = await client.get(f"/api/v1/data-sources/{workspace_id}")

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["name"], "Tanmay live sheet")
        self.assertEqual(response.json()["sync_status"], SyncStatus.ACTIVE.value)
        self.assertEqual(rejected_portal.status_code, 400, rejected_portal.text)
        self.assertEqual(fetch_mock.await_count, 1)
        self.assertEqual(sources_response.status_code, 200, sources_response.text)
        self.assertEqual(len(sources_response.json()), 1)

        db = self.session_factory()
        try:
            source = db.query(DataSource).filter_by(workspace_id=workspace_id).one()
            recruiter = db.query(RecruiterProfile).filter_by(id=source.recruiter_id).one()
            fields = {
                mapping.standard_field
                for mapping in db.query(ColumnMapping).filter_by(data_source_id=source.id).all()
            }
            self.assertEqual(source.sheet_id_or_url, sheet_url)
            self.assertEqual(recruiter.full_name, "Tanmay")
            self.assertEqual(
                fields,
                {StandardField.ACTIVITY_DATE, StandardField.CALL_STATUS, StandardField.JOB_ROLE}
            )
        finally:
            db.close()
