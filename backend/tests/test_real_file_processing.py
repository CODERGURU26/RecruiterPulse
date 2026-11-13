import io
import unittest

import httpx
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import AsyncMock, patch

from app.core.database import Base, get_db
from app.main import app
from app.models import CallCategory, StatusTaxonomy, Workspace


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
            for recruiter, candidate, status in (
                ("Priya Sharma", "Candidate 1", "Connected"),
                ("Rahul Verma", "Candidate 2", "RNR")
            ):
                pd.DataFrame([
                    ["Date", "Call Status", "Candidate", "Profile"],
                    ["12/11/2026", status, candidate, "Software Engineer"]
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
            with patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.fetch_sheet_dataframe",
                new=AsyncMock(return_value=pd.DataFrame({
                    "Date": ["13/11/2026"],
                    "Call Status": ["Connected"],
                    "Candidate": ["Candidate Google"],
                    "Profile": ["QA Engineer"]
                }))
            ):
                google_response = await client.post(
                    "/api/v1/data-sources/process-real-file",
                    data={
                        "workspace_id": workspace_id,
                        "target_date_str": "2026-11-13",
                        "recruiter_name": "Nina Shah",
                        "google_sheet_url": "https://docs.google.com/spreadsheets/d/example/edit"
                    }
                )

        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["reporting_date"], "2026-11-12")
        self.assertEqual(result["metrics"]["total_calls"], 2)
        self.assertTrue(result["is_master_sheet"])
        self.assertEqual(
            {recruiter["name"] for recruiter in result["recruiters_processed"]},
            {"Priya Sharma", "Rahul Verma"}
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["summary_totals"]["next_day_interviews"], 0)
        self.assertEqual(google_response.status_code, 200, google_response.text)
        self.assertEqual(google_response.json()["metrics"]["total_calls"], 1)
        self.assertEqual(google_response.json()["recruiter_name"], "Nina Shah")
