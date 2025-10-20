# backend/apis/auth_api.py
from typing import Callable
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models import User  # updated import path (single models file)
from schemas import SignUpIn, LoginIn

def _fail(msg: str) -> dict:
    return {"status": "FAIL", "statusCode": 200, "message": msg, "data": ""}

def _success(msg: str, data: str = "") -> dict:
    return {"status": "SUCCESS", "statusCode": 200, "message": msg, "data": data}

class SignUpAPI:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.SessionLocal = session_factory

    def __call__(self, payload: SignUpIn):
        email_norm = (payload.user_email or "").strip().lower()
        if not email_norm:
            return _fail("Email is required")

        with self.SessionLocal() as db:
            # Case-insensitive uniqueness check
            exists = db.execute(
                select(User).where(func.lower(User.user_email) == email_norm)
            ).scalar_one_or_none()
            if exists:
                return _fail("Email already exists")

            user = User(
                user_email=email_norm,
                user_password=payload.user_password,       # NOTE: store a hash in production
                user_firstname=(payload.user_firstname or "").strip() or None,
                user_lastname=(payload.user_lastname or "").strip() or None,
                user_university=(payload.user_university or "").strip() or None,
                user_currentsem=(payload.user_currentsem or "").strip() or None,
            )
            db.add(user)
            db.commit()
            # optional: db.refresh(user)

            # Keep data as a STRING per your API contract
            return _success("User registered successfully", data=f"user_id={user.user_id}")

class LoginAPI:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.SessionLocal = session_factory

    def __call__(self, payload: LoginIn):
        email_norm = (payload.user_email or "").strip().lower()
        if not email_norm:
            return _fail("Email is required")

        with self.SessionLocal() as db:
            user = db.execute(
                select(User).where(func.lower(User.user_email) == email_norm)
            ).scalar_one_or_none()

            # Simple comparison; replace with hashed password check in prod
            if not user or user.user_password != payload.user_password:
                return _fail("Invalid email or password")

            # You can later put a JWT or session token here; for now keep it a string
            return _success("Login successful", data=f"user_id={user.user_id}")
