from typing import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.user import User
from schemas import SignUpIn, LoginIn

def _fail(msg: str):    return {"status": "FAIL",    "statusCode": 200, "message": msg}
def _success(msg: str): return {"status": "SUCCESS", "statusCode": 200, "message": msg}

class SignUpAPI:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.SessionLocal = session_factory

    def __call__(self, payload: SignUpIn):
        with self.SessionLocal() as db:
            # email exists?
            exists = db.execute(
                select(User).where(User.user_email == payload.user_email)
            ).scalar_one_or_none()
            if exists:
                return _fail("Email already exists")

            user = User(
                user_email=payload.user_email,
                user_password=payload.user_password,
                user_firstname=payload.user_firstname,
                user_lastname=payload.user_lastname,
                user_university=payload.user_university,
                user_currentsem=payload.user_currentsem,
            )
            db.add(user)
            db.commit()
            return _success("User registered successfully")

class LoginAPI:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.SessionLocal = session_factory

    def __call__(self, payload: LoginIn):
        with self.SessionLocal() as db:
            user = db.execute(
                select(User).where(User.user_email == payload.user_email)
            ).scalar_one_or_none()
            if not user or user.user_password != payload.user_password:
                return _fail("Invalid email or password")
            return _success("Login successful")
