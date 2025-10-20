# backend/models/__init__.py
from .db_model import Base, init_models, User, Course

__all__ = ["Base", "init_models", "User", "Course"]
