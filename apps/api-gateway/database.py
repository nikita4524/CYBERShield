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
    - PostgreSQL URL → connect to PostgreSQL with timeout
    - SQLite URL (default) → local SQLite database
    """
    if TESTING:
        return create_engine(
            "sqlite:///./test.db",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    # Use DATABASE_URL from environment
    db_url = DATABASE_URL
    
    if db_url.startswith("postgresql"):
        # PostgreSQL: add connection timeout for fast failure
        try:
            return create_engine(
                db_url,
                connect_args={'connect_timeout': 5}
            )
        except Exception as e:
            # If PostgreSQL unavailable and DEBUG mode, fall back to SQLite
            if DEBUG:
                import logging
                logging.warning(f"PostgreSQL connection failed: {e}. Falling back to SQLite in DEBUG mode.")
                return create_engine(
                    "sqlite:///./cybershield.db",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                raise
    else:
        # SQLite: use check_same_thread=False and StaticPool
        return create_engine(
            db_url,
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