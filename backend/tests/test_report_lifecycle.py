import unittest
from datetime import date
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.models import (
    Workspace,
    User,
    UserRole,
    HourlyReport,
    RecruiterDailyMetric,
    RecruiterProfile,
    ReportStatus,
    AuditLog,
    AuditAction
)
from app.api.v1.reports import (
    get_pending_report,
    get_latest_approved_report,
    approve_report,
    edit_draft_report,
    reject_report
)
from app.schemas.report import (
    ReportApprovalRequest,
    ReportEditRequest,
    RecruiterMetricEdit,
    ReportRejectionRequest
)


class TestReportLifecycle(unittest.TestCase):
    """Exhaustive tests for the MIS approval lifecycle, rejections, and audit trails."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()

        # Workspace & MIS User
        self.ws = Workspace(name="Talent Bridge", slug="talent-bridge")
        self.db.add(self.ws)
        self.db.flush()

        self.mis_user = User(
            workspace_id=self.ws.id,
            email="mis@talentbridge.in",
            hashed_password="pw",
            full_name="Kavita Iyer",
            role=UserRole.MIS_EXECUTIVE
        )
        self.db.add(self.mis_user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_approval_workflow_and_audit(self):
        """Verifies report creation -> review -> approval -> audit log creation."""
        # 1. Create Draft
        draft = HourlyReport(
            workspace_id=self.ws.id,
            reporting_date=date.today(),
            hour_slot="13:00",
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={"total_calls": 30}
        )
        self.db.add(draft)
        self.db.commit()

        # 2. Check pending
        pending = get_pending_report(workspace_id=self.ws.id, db=self.db)
        self.assertIsNotNone(pending)
        self.assertEqual(pending.id, draft.id)
        self.assertEqual(pending.status, ReportStatus.DRAFT_PENDING_APPROVAL)

        # 3. Approve report
        req = ReportApprovalRequest(approver_user_id=self.mis_user.id)
        approved = approve_report(report_id=draft.id, payload=req, db=self.db)

        self.assertEqual(approved.status, ReportStatus.APPROVED)
        self.assertEqual(approved.approved_by_name, "Kavita Iyer")
        self.assertIsNotNone(approved.approved_at)

        # 4. Verify Audit Log recorded
        audit = self.db.query(AuditLog).filter(
            AuditLog.workspace_id == self.ws.id,
            AuditLog.action == AuditAction.REPORT_APPROVED
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.actor_user_id, self.mis_user.id)

    def test_rejection_workflow(self):
        """Verifies report rejection records reason and audit log."""
        draft = HourlyReport(
            workspace_id=self.ws.id,
            reporting_date=date.today(),
            hour_slot="15:00",
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={"total_calls": 10}
        )
        self.db.add(draft)
        self.db.commit()

        req = ReportRejectionRequest(
            approver_user_id=self.mis_user.id,
            reason="Recruiter Rahul's sheet was not synced. Resyncing."
        )
        rejected = reject_report(report_id=draft.id, payload=req, db=self.db)

        self.assertEqual(rejected.status, ReportStatus.REJECTED)
        self.assertEqual(rejected.rejection_reason, "Recruiter Rahul's sheet was not synced. Resyncing.")

        # Audit log verification
        audit = self.db.query(AuditLog).filter(
            AuditLog.workspace_id == self.ws.id,
            AuditLog.action == AuditAction.REPORT_REJECTED
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("Rahul", audit.details.get("reason", ""))

    def test_edit_draft_recalculates_metrics_and_audits_changes(self):
        recruiter = RecruiterProfile(
            workspace_id=self.ws.id,
            full_name="Rahul Verma",
            is_active=True
        )
        draft = HourlyReport(
            workspace_id=self.ws.id,
            reporting_date=date.today(),
            hour_slot="14:00",
            status=ReportStatus.DRAFT_PENDING_APPROVAL,
            summary_totals={"total_calls": 5}
        )
        self.db.add_all([recruiter, draft])
        self.db.flush()
        metric = RecruiterDailyMetric(
            hourly_report_id=draft.id,
            recruiter_id=recruiter.id,
            job_roles=["Old Role"],
            connected_calls=2,
            not_connected_calls=3,
            total_calls=5,
            connected_rate=40,
            next_day_interviews=1,
            unassigned_interviews=0
        )
        self.db.add(metric)
        self.db.commit()

        payload = ReportEditRequest(
            approver_user_id=self.mis_user.id,
            metrics=[
                RecruiterMetricEdit(
                    id=metric.id,
                    job_roles=["Backend Engineer", "  Backend Engineer  ", "QA"],
                    connected_calls=6,
                    not_connected_calls=4,
                    next_day_interviews=2
                )
            ]
        )
        updated = edit_draft_report(draft.id, payload, self.db)

        self.assertEqual(updated.summary_totals["total_calls"], 10)
        self.assertEqual(updated.summary_totals["connected_calls"], 6)
        self.assertEqual(updated.summary_totals["not_connected_calls"], 4)
        self.assertEqual(updated.summary_totals["connected_rate"], 60)
        self.assertEqual(updated.summary_totals["next_day_interviews"], 2)
        self.assertEqual(updated.metrics[0].job_roles, ["Backend Engineer", "QA"])
        self.assertEqual(updated.metrics[0].total_calls, 10)
        self.assertEqual(updated.metrics[0].connected_rate, 60)
        audit = self.db.query(AuditLog).filter(
            AuditLog.workspace_id == self.ws.id,
            AuditLog.action == AuditAction.REPORT_EDITED
        ).one()
        self.assertEqual(audit.actor_user_id, self.mis_user.id)

    def test_approved_report_cannot_be_edited(self):
        draft = HourlyReport(
            workspace_id=self.ws.id,
            reporting_date=date.today(),
            hour_slot="15:00",
            status=ReportStatus.APPROVED,
            summary_totals={}
        )
        self.db.add(draft)
        self.db.commit()

        with self.assertRaises(HTTPException) as error:
            edit_draft_report(
                draft.id,
                ReportEditRequest(approver_user_id=self.mis_user.id, metrics=[]),
                self.db
            )
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
