import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import RecruiterProfile, StatusTaxonomy, User, Workspace
from app.api.v1.workspaces import get_default_workspace
from app.services.workspace_bootstrap import ensure_default_workspace


class TestWorkspaceBootstrap(unittest.TestCase):
    def test_default_endpoint_provisions_a_missing_workspace(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()

        try:
            workspace = get_default_workspace(db)

            self.assertEqual(workspace.id, "ws-apex-101")
            self.assertEqual(workspace.slug, "apex-staffing")
            self.assertEqual(
                db.query(StatusTaxonomy).filter_by(workspace_id=workspace.id).count(),
                24
            )
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def test_default_endpoint_finds_workspace_by_id_if_slug_differs(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        db.add(Workspace(
            id="ws-apex-101",
            name="Existing Apex Workspace",
            slug="existing-apex-slug",
            timezone="Asia/Kolkata"
        ))
        db.commit()

        try:
            workspace = get_default_workspace(db)

            self.assertEqual(workspace.id, "ws-apex-101")
            self.assertEqual(workspace.slug, "existing-apex-slug")
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    def test_default_workspace_is_created_idempotently_without_replacing_other_tenants(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        db.add(Workspace(
            id="existing-workspace",
            name="Existing Tenant",
            slug="existing-tenant",
            timezone="Asia/Kolkata"
        ))
        db.commit()

        try:
            first = ensure_default_workspace(db)
            db.commit()
            second = ensure_default_workspace(db)
            db.commit()

            self.assertEqual(first.id, "ws-apex-101")
            self.assertEqual(second.id, "ws-apex-101")
            self.assertEqual(db.query(Workspace).count(), 2)
            self.assertEqual(
                db.query(StatusTaxonomy).filter_by(workspace_id="ws-apex-101").count(),
                24
            )
            self.assertEqual(
                db.query(RecruiterProfile).filter_by(workspace_id="ws-apex-101").count(),
                3
            )
            self.assertEqual(
                db.query(User).filter_by(id="usr-admin", workspace_id="ws-apex-101").count(),
                1
            )
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
