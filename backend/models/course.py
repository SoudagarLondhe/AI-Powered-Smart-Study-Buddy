from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text

# If you already have a shared Base in models/__init__.py, import that instead:
try:
    from . import Base  # reuse shared Base
except Exception:
    Base = declarative_base()

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True, autoincrement=True)
    course_name = Column(String(255), nullable=False)
    course_content = Column(Text, nullable=False) 
