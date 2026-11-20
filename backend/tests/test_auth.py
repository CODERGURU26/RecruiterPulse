import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.auth import (
    SESSION_DURATION_SECONDS,
    create_session_token,
    hash_password,
    session_user_id,
    verify_password,
)
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models import User, UserRole, Workspace


class TestAuthentication(unittest.TestCase):
    def test_password_hash_verifies_only_the_matching_password(self):
        password_hash = hash_password("a-long-test-password", salt=b"0123456789abcdef")

        self.assertTrue(verify_password("a-long-test-password", password_hash))
        self.assertFalse(verify_password("another-password", password_hash))
        self.assertFalse(verify_password("a-long-test-password", "not-a-password-hash"))

    def test_session_token_is_signed_and_expires(self):
        token = create_session_token("user-123", now=100)

        self.assertEqual(session_user_id(token, now=100), "user-123")
        self.assertIsNone(session_user_id(token + "tampered", now=100))
        self.assertIsNone(session_user_id(token, now=100 + SESSION_DURATION_SECONDS))

    def test_production_api_requires_a_session(self):
        async def make_request():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get("/api/v1/workspaces/default")

        with patch.object(settings, "APP_ENV", "production"):
            response = asyncio.run(make_request())

        self.assertEqual(response.status_code, 401)

    def test_configured_auth_accounts_reject_duplicate_emails(self):
        from app.core.auth import configured_auth_accounts

        password_hash = hash_password("a-long-test-password", salt=b"0123456789abcdef")
        account = {
            "email": "manager@example.com",
            "full_name": "Manager",
            "password_hash": password_hash,
            "role": "MANAGER"
        }
        with patch.object(settings, "AUTH_USERS_JSON", json.dumps([account, account])):
            with self.assertRaises(ValueError):
                configured_auth_accounts()


class TestAuthenticationFlow(unittest.IsolatedAsyncioTestCase):
    async def test_login_creates_a_session_for_a_configured_account(self):
        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        Base.metadata.create_all(bind=test_engine)
        db = Session(bind=test_engine)
        password_hash = hash_password("a-long-test-password", salt=b"0123456789abcdef")
        workspace = Workspace(
            name="Auth Test Workspace",
            slug="auth-test-workspace",
            timezone="Asia/Kolkata"
        )
        db.add(workspace)
        db.flush()
        db.add(User(
            workspace_id=workspace.id,
            email="manager@example.com",
            full_name="Test Manager",
            role=UserRole.MANAGER,
            hashed_password=password_hash
        ))
        db.commit()

        account = {
            "email": "manager@example.com",
            "full_name": "Test Manager",
            "password_hash": password_hash,
            "role": "MANAGER"
        }

        def override_get_db():
            yield db

        previous_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_get_db
        try:
            with (
                patch.object(settings, "APP_ENV", "production"),
                patch.object(settings, "AUTH_USERS_JSON", json.dumps([account])),
                patch.object(settings, "SECRET_KEY", "test-secret-key-" * 4)
            ):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="https://test"
                ) as client:
                    login_response = await client.post(
                        "/api/v1/auth/login",
                        json={"email": "manager@example.com", "password": "a-long-test-password"}
                    )
                    self.assertEqual(login_response.status_code, 200)

                    status_response = await client.get("/api/v1/auth/status")
                    self.assertEqual(status_response.status_code, 200)
                    self.assertTrue(status_response.json()["authenticated"])
                    self.assertEqual(status_response.json()["user"]["email"], "manager@example.com")
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
            db.close()
            test_engine.dispose()


if __name__ == "__main__":
    unittest.main()
