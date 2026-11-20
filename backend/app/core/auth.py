import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Optional

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.config import settings
from app.models.enums import UserRole

SESSION_COOKIE_NAME = "recruiterpulse_session"
SESSION_DURATION_SECONDS = 12 * 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_HASH_PATTERN = re.compile(r"^pbkdf2_sha256\$(\d+)\$([0-9a-f]{32})\$([0-9a-f]{64})$")


class AuthAccount(BaseModel):
    email: str
    full_name: str
    password_hash: str
    role: UserRole


def configured_auth_accounts() -> list[AuthAccount]:
    try:
        accounts = TypeAdapter(list[AuthAccount]).validate_python(
            json.loads(settings.AUTH_USERS_JSON)
        )
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("AUTH_USERS_JSON must be a JSON array of valid account records.") from exc

    seen_emails = set()
    for account in accounts:
        email = account.email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("Every configured account must have a valid email address.")
        if email in seen_emails:
            raise ValueError("AUTH_USERS_JSON cannot contain duplicate email addresses.")
        if account.role not in (UserRole.AGENCY_OWNER, UserRole.MANAGER, UserRole.MIS_EXECUTIVE):
            raise ValueError("Configured sign-in accounts must have an owner, manager, or MIS role.")
        if not PASSWORD_HASH_PATTERN.fullmatch(account.password_hash):
            raise ValueError(f"Account {email} must use a supported PBKDF2 password hash.")
        seen_emails.add(email)

    if settings.APP_ENV.lower() == "production" and not accounts:
        raise ValueError("Set AUTH_USERS_JSON before running RecruiterPulse in production.")
    return accounts


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters long.")
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), actual_salt, PASSWORD_HASH_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$"
        f"{actual_salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    match = PASSWORD_HASH_PATTERN.fullmatch(encoded_hash)
    if not match:
        return False
    iterations = int(match.group(1))
    if iterations < 100_000 or iterations > 2_000_000:
        return False
    salt = bytes.fromhex(match.group(2))
    expected = bytes.fromhex(match.group(3))
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_session_token(user_id: str, now: Optional[int] = None) -> str:
    payload = json.dumps(
        {"sub": user_id, "exp": (now or int(time.time())) + SESSION_DURATION_SECONDS},
        separators=(",", ":")
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{encoded_payload}.{encoded_signature}"


def session_user_id(token: Optional[str], now: Optional[int] = None) -> Optional[str]:
    if not token:
        return None
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None
        payload = base64.urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )
        data = json.loads(payload)
        if not isinstance(data, dict):
            return None
        if not isinstance(data.get("sub"), str) or data.get("exp", 0) <= (now or int(time.time())):
            return None
        return data["sub"]
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def validate_production_settings() -> None:
    if settings.APP_ENV.lower() != "production":
        return
    if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY == "recruiterpulse-super-secret-key-change-in-production-2026":
        raise ValueError("Set SECRET_KEY to a unique random value of at least 32 characters.")
    if not settings.DATABASE_URL.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
        raise ValueError("Production deployments must use a managed PostgreSQL DATABASE_URL.")
    configured_auth_accounts()
