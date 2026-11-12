import unittest
from datetime import date
from app.core.database import Base, engine, SessionLocal
from app.models import (
    Workspace,
    User,
    UserRole,
    RecruiterProfile,
    DataSource,
    HourlyReport,
    RecruiterDailyMetric,
    ReportStatus
)
from app.api.v1.workspaces import list_recruiters
from app.api.v1.reports import get_pending_report, get_latest_approved_report


class TestMultiTenancyIsolation(unittest.TestCase):
    """Verifies that complete row-level tenant isolation is maintained across agencies."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        # Clean test tables
        self.db.query(RecruiterDailyMetric).delete()
        self.db.query(HourlyReport).delete()
        self.db.query(DataSource).delete()
        self.db.query(RecruiterProfile).delete()
        self.db.query(User).delete()
        self.db.query(Workspace).delete()
        self.db.commit()

        # Agency A
        self.ws_a = Workspace(name="Agency Alpha", slug="agency-alpha")
        self.db.add(self.ws_a)
        self.db.flush()

        # Agency B
        self.ws_b = Workspace(name="Agency Beta", slug="agency-beta")
        self.db.add(self.ws_b)
        self.db.flush()

        # Recruiters for Agency A
        self.rec_a1 = RecruiterProfile(workspace_id=self.ws_a.id, full_name="Alpha Recruiter 1")
        self.rec_a2 = RecruiterProfile(workspace_id=self.ws_a.id, full_name="Alpha Recruiter 2")
        self.db.add_all([self.rec_a1, self.rec_a2])

        # Recruiter for Agency B
        self.rec_b1 = RecruiterProfile(workspace_id=self.ws_b.id, full_name="Beta Recruiter 1")
        self.db.add(self.rec_b1)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_recruiter_isolation(self):
        """Agency Alpha must only see its own recruiters; Agency Beta must only see its own."""
        alpha_recruiters = list_recruiters(workspace_id=self.ws_a.id, db=self.db)
        beta_recruiters = list_recruiters(workspace_id=self.ws_b.id, db=self.db)

        self.assertEqual(len(alpha_recruiters), 2)
        self.assertEqual({r.full_name for r in alpha_recruiters}, {"Alpha Recruiter 1", "Alpha Recruiter 2"})

        self.assertEqual(len(beta_recruiters), 1)
        self.assertEqual({r.full_name for r in beta_recruiters}, {"Beta Recruiter 1"})

        # Cross-tenant pollution check
        for r in alpha_recruiters:
            self.assertNotEqual(r.full_name, "Beta Recruiter 1")

    def test_report_isolation(self):
        """Reports generated for Agency Alpha must never be returned when querying Agency Beta."""
        report_a = HourlyReport(
            workspace_id=self.ws_a.id,
            reporting_date=date.today(),
            hour_slot="14:00",
            status=ReportStatus.APPROVED,
            summary_totals={"total_calls": 50, "connected_rate": 60.0}
        )
        self.db.add(report_a)
        self.db.commit()

        # Agency A queries latest report -> Found
        res_a = get_latest_approved_report(workspace_id=self.ws_a.id, db=self.db)
        self.assertIsNotNone(res_a)
        self.assertEqual(res_a.workspace_id, self.ws_a.id)

        # Agency B queries latest report -> None (Zero leakage)
        res_b = get_latest_approved_report(workspace_id=self.ws_b.id, db=self.db)
        self.assertIsNone(res_b)


if __name__ == "__main__":
    unittest.main()

