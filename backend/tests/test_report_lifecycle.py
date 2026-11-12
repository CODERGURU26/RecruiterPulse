import unittest
from datetime import date
from app.core.database import Base, engine, SessionLocal
from app.models import (
    Workspace,
    User,
    UserRole,
    HourlyReport,
    ReportStatus,
    AuditLog,
    AuditAction
)
from app.api.v1.reports import (
    get_pending_report,
    get_latest_approved_report,
    approve_report,
    reject_report
)
from app.schemas.report import ReportApprovalRequest, ReportRejectionRequest


class TestReportLifecycle(unittest.TestCase):
    """Exhaustive tests for the MIS approval lifecycle, rejections, and audit trails."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        self.db.query(AuditLog).delete()
        self.db.query(HourlyReport).delete()
        self.db.query(User).delete()
        self.db.query(Workspace).delete()
        self.db.commit()

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


if __name__ == "__main__":
    unittest.main()

