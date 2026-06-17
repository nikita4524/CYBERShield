"""
CyberShield AI — Database Connection & Session Management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./cybershield.db"
)

# Handle test database
TESTING = os.getenv("TESTING", "false").lower() == "true"
DEBUG = True

def _create_engine():
    """
    Create the SQLAlchemy engine.
    - TESTING=true  → lightweight SQLite (in-memory style)
    - Postgres URL   → try to connect; if DEBUG=true and it fails, fall back to
                       a local SQLite dev.db so the app starts without Postgres
    """
    if TESTING:
        return create_engine(
            "sqlite:///./test.db",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # Use SQLite directly (no PostgreSQL)
    return create_engine(
        "sqlite:///./cybershield.db",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


engine = _create_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models"""
    pass


def get_db():
    """
    FastAPI dependency — yields a database session per request.
    Automatically closes session after request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables (used in testing and initial setup)"""
    Base.metadata.create_all(bind=engine)


def drop_all_tables():
    """Drop all tables (used in testing)"""
    Base.metadata.drop_all(bind=engine)