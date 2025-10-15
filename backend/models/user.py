from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime, func, UniqueConstraint

from . import Base

class User(Base):
    __tablename__ = "User"  
    __table_args__ = (UniqueConstraint("user_email", name="uq_user_email"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_password: Mapped[str] = mapped_column(String(255), nullable=False)  # plaintext per your spec
    user_firstname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_lastname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_university: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_currentsem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
