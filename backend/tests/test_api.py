import sys
import os
import io
import asyncio
from datetime import date

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models import HourlyReport, RecruiterDailyMetric, RecruiterProfile, ReportStatus, User


async def test_api_lifecycle():
    print("=" * 60, flush=True)
    print("RUNNING RECRUITERPULSE FASTAPI END-TO-END API TEST", flush=True)
    print("=" * 60, flush=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "healthy"}
        print("✓ Health check endpoint: OK", flush=True)

        # 2. Workspace Registration
        ws_payload = {
            "name": "Global Tech Staffing",
            "slug": "global-tech-staffing",
            "admin_name": "Rohan Mehra",
            "admin_email": "rohan@globaltechstaffing.com",
            "admin_password": "secure_admin_password_123",
            "timezone": "Asia/Kolkata"
        }
        res = await client.post("/api/v1/workspaces", json=ws_payload)
        assert res.status_code == 201, res.text
        ws_data = res.json()
        ws_id = ws_data["id"]
        print(f"✓ Workspace Created: '{ws_data['name']}' (ID: {ws_id})", flush=True)

        # 3. Add Recruiter to Roster
        recruiter_payload = {
            "full_name": "Ananya Sen",
            "email": "ananya@globaltechstaffing.com",
            "calendar_identifier": "ananya@globaltechstaffing.com"
        }
        res = await client.post(f"/api/v1/workspaces/{ws_id}/recruiters", json=recruiter_payload)
        assert res.status_code == 201
        recruiter_data = res.json()
        recruiter_id = recruiter_data["id"]
        print(f"✓ Recruiter Added: '{recruiter_data['full_name']}' (ID: {recruiter_id})", flush=True)

        # 4. Upload sample CSV file for Column Detection
        csv_content = (
            "Calling Date,Candidate Name,Mobile,Role,Call Outcome\n"
            "12/11/2026,Karan Joshi,9876501234,React Developer,Connected\n"
            "12/11/2026,Divya Sharma,9876505678,Java Developer,RNR\n"
        )
        files = {
            "file": ("daily_calls.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        res = await client.post("/api/v1/data-sources/detect-from-file", files=files)
        assert res.status_code == 200, res.text
        detection_data = res.json()
        mappings = detection_data["detected_mappings"]
        assert mappings["activity_date"]["source_column"] == "Calling Date"
        assert mappings["call_status"]["source_column"] == "Call Outcome"
        print(f"✓ File Column Detection API: Successfully identified {detection_data['total_columns_found']} columns", flush=True)

        # 5. Seed a Draft Hourly Report in DB for Approval Test
        db = SessionLocal()
        try:
            draft_report = HourlyReport(
                workspace_id=ws_id,
                reporting_date=date.today(),
                hour_slot="14:00",
                status=ReportStatus.DRAFT_PENDING_APPROVAL,
                summary_totals={
                    "total_calls": 35,
                    "connected_calls": 22,
                    "not_connected_calls": 13,
                    "connected_rate": 62.86,
                    "next_day_interviews": 2
                }
            )
            db.add(draft_report)
            db.flush()

            metric = RecruiterDailyMetric(
                hourly_report_id=draft_report.id,
                recruiter_id=recruiter_id,
                job_roles=["React Developer"],
                connected_calls=22,
                not_connected_calls=13,
                total_calls=35,
                connected_rate=62.86,
                next_day_interviews=2,
                unassigned_interviews=0
            )
            db.add(metric)
            db.commit()
            report_id = draft_report.id
            
            # Fetch admin user id for approval
            admin_user = db.query(User).filter(User.workspace_id == ws_id).first()
            admin_id = admin_user.id
        finally:
            db.close()

        # 6. Fetch Pending Report via API
        res = await client.get(f"/api/v1/reports/pending?workspace_id={ws_id}")
        assert res.status_code == 200
        pending_data = res.json()
        assert pending_data["id"] == report_id
        assert pending_data["status"] == "DRAFT_PENDING_APPROVAL"
        print(f"✓ Pending Report API: Found Draft Report for Slot {pending_data['hour_slot']}", flush=True)

        # 7. Approve the Report via API
        approve_payload = {"approver_user_id": admin_id}
        res = await client.post(f"/api/v1/reports/{report_id}/approve", json=approve_payload)
        assert res.status_code == 200
        approved_data = res.json()
        assert approved_data["status"] == "APPROVED"
        assert approved_data["approved_by_name"] == "Rohan Mehra"
        print(f"✓ Approve Report API: Report successfully approved by {approved_data['approved_by_name']}", flush=True)

        # 8. Fetch WhatsApp Formatted Text
        res = await client.get(f"/api/v1/reports/{report_id}/whatsapp")
        assert res.status_code == 200
        whatsapp_data = res.json()
        assert "Global Tech Staffing" in whatsapp_data["formatted_text"]
        assert "Rohan Mehra" in whatsapp_data["formatted_text"]
        print("✓ WhatsApp Clipboard API: Formatted text generated:", flush=True)
        print("-" * 40, flush=True)
        print(whatsapp_data["formatted_text"], flush=True)
        print("-" * 40, flush=True)

    print("\nALL FASTAPI ENDPOINTS TESTED AND VERIFIED (100% PASS)!\n", flush=True)


if __name__ == "__main__":
    asyncio.run(test_api_lifecycle())
