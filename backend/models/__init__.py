from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Shared SQLAlchemy Base for all tables."""
    pass

def init_models(engine) -> None:
    """
    Called by app.py once to ensure tables exist.
    Keeps DB connection code out of models & apis.
    """
    # Import models so they register with Base.metadata
    from .user import User  # noqa: F401
    Base.metadata.create_all(bind=engine)
