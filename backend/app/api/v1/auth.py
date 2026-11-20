from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import (
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
    configured_auth_accounts,
    create_session_token,
    session_user_id,
    verify_password,
)
from app.core.config import settings
from app.core.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


def current_session_user(request: Request, db: Session) -> User | None:
    user_id = session_user_id(request.cookies.get(SESSION_COOKIE_NAME))
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        return None
    if settings.APP_ENV.lower() == "production":
        from app.core.auth import configured_auth_accounts

        if user.email.lower() not in {account.email.strip().lower() for account in configured_auth_accounts()}:
            return None
    return user


def authenticated_user_id(request: Request) -> str | None:
    return getattr(request.state, "authenticated_user_id", None)


@router.get("/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    user = current_session_user(request, db)
    required = settings.APP_ENV.lower() == "production"
    return {
        "required": required,
        "authenticated": user is not None if required else True,
        "user": (
            {"id": user.id, "email": user.email, "full_name": user.full_name}
            if user else None
        )
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    if settings.APP_ENV.lower() != "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    email = payload.email.strip().lower()
    allowed_emails = {
        account.email.strip().lower() for account in configured_auth_accounts()
    }
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if email not in allowed_emails or not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(user.id),
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/"
    )
    return {"authenticated": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        samesite="strict",
        path="/"
    )
    return {"authenticated": False}
