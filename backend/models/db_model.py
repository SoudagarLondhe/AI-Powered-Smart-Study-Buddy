# backend/models/db_model.py
from __future__ import annotations
from typing import Optional

from sqlalchemy import (
    Integer, String, Text, UniqueConstraint, ForeignKey
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()

class User(Base):
    __tablename__ = "User"
    __table_args__ = (UniqueConstraint("user_email", name="uq_user_email"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_password: Mapped[str] = mapped_column(String(255), nullable=False)  # hash in prod
    user_firstname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_lastname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_university: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_currentsem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_content: Mapped[str] = mapped_column(Text, nullable=False)

class Summary(Base):
    __tablename__ = "summary"
    __table_args__ = (UniqueConstraint("course_id", "summary_length", name="uq_course_summary"),)

    summary_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False)
    summary_length: Mapped[str] = mapped_column(String(20), nullable=False)  # short|medium|long
    summary_content: Mapped[str] = mapped_column(Text, nullable=False)

class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (UniqueConstraint("course_id", "card_index", name="uq_course_card_slot"),)

    flashcard_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.course_id", ondelete="CASCADE"), nullable=False)
    card_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..10
    front_text: Mapped[str] = mapped_column(Text, nullable=False)
    back_text: Mapped[str] = mapped_column(Text, nullable=False)

def init_models(engine) -> None:
    Base.metadata.create_all(engine)
