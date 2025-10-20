# backend/models/db_model.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Integer, String, DateTime, Text, func, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

# ---------- Base ----------
Base = declarative_base()

# ---------- Tables ----------
class User(Base):
    __tablename__ = "User"
    __table_args__ = (UniqueConstraint("user_email", name="uq_user_email"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_password: Mapped[str] = mapped_column(String(255), nullable=False)  # store a hash in prod
    user_firstname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_lastname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_university: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_currentsem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

# ---------- bootstrap ----------
def init_models(engine) -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(engine)
