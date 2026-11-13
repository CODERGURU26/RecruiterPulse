import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.data_sources import delete_data_source, register_google_workbook
from app.core.database import Base
from app.models import DataSource, RecruiterProfile, Workspace
from app.schemas.data_source import RegisterGoogleWorkbookRequest


class TestGoogleWorkbookRegistration(unittest.IsolatedAsyncioTestCase):
    async def test_registers_recruiter_tabs_skips_non_call_tabs_and_disconnects_source(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        workspace = Workspace(
            id="workbook-test",
            name="Workbook Test",
            slug="workbook-test",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.commit()

        tab_data = {
            "Tanmay": pd.DataFrame({
                "Date": ["13/11/2026"],
                "Call Status": ["Connected"],
                "Recruiter Name": ["Tanmay"]
            }),
            "Divya": pd.DataFrame({
                "Date": ["13/11/2026"],
                "Call Status": ["Not Connected"],
                "Recruiter Name": ["Divya"]
            }),
            "Summary": pd.DataFrame({"Role": ["Engineer"], "Count": [2]})
        }

        try:
            with patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.list_spreadsheet_tabs",
                return_value=[
                    {"gid": "1", "title": "Tanmay"},
                    {"gid": "2", "title": "Divya"},
                    {"gid": "3", "title": "Summary"}
                ]
            ), patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.fetch_via_service_account",
                side_effect=lambda _spreadsheet_id, tab_name: tab_data[tab_name]
            ):
                result = await register_google_workbook(
                    workspace.id,
                    RegisterGoogleWorkbookRequest(
                        sheet_url="https://docs.google.com/spreadsheets/d/workbook123/edit"
                    ),
                    db
                )
                repeated_result = await register_google_workbook(
                    workspace.id,
                    RegisterGoogleWorkbookRequest(
                        sheet_url="https://docs.google.com/spreadsheets/d/workbook123/edit"
                    ),
                    db
                )

            self.assertEqual(len(result["registered"]), 2)
            self.assertEqual(
                {source.id for source in result["registered"]},
                {source.id for source in repeated_result["registered"]}
            )
            self.assertEqual(db.query(DataSource).count(), 2)
            self.assertEqual(
                {source.sheet_tab_name for source in result["registered"]},
                {"Tanmay", "Divya"}
            )
            self.assertEqual(result["skipped"][0]["tab_name"], "Summary")
            self.assertEqual(db.query(RecruiterProfile).count(), 2)

            source_id = result["registered"][0].id
            deleted = delete_data_source(workspace.id, source_id, db)
            self.assertTrue(deleted["deleted"])
            self.assertIsNone(db.query(DataSource).filter(DataSource.id == source_id).first())
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    async def test_skips_ambiguous_multi_recruiter_tab(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        workspace = Workspace(
            id="ambiguous-workbook-test",
            name="Ambiguous Workbook Test",
            slug="ambiguous-workbook-test",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.commit()

        try:
            with patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.list_spreadsheet_tabs",
                return_value=[{"gid": "1", "title": "Calling Log"}]
            ), patch(
                "app.api.v1.data_sources.GoogleSheetsWorker.fetch_via_service_account",
                return_value=pd.DataFrame({
                    "Date": ["13/11/2026", "13/11/2026"],
                    "Call Status": ["Connected", "Ringing"],
                    "Recruiter Name": ["Tanmay", "Divya"]
                })
            ):
                result = await register_google_workbook(
                    workspace.id,
                    RegisterGoogleWorkbookRequest(
                        sheet_url="https://docs.google.com/spreadsheets/d/workbook456/edit"
                    ),
                    db
                )

            self.assertEqual(result["registered"], [])
            self.assertIn("multiple recruiter names", result["skipped"][0]["reason"])
            self.assertEqual(db.query(RecruiterProfile).count(), 0)
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
