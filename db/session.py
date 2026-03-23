"""
db/session.py

Database engine setup and session management.

Provides:
  - engine        → SQLAlchemy engine (used to create tables)
  - get_db()      → FastAPI dependency (inject into route functions)
  - init_db()     → called on app startup to create all tables

Usage in a route:
    from db.session import get_db
    from sqlalchemy.orm import Session

    @router.get("/users")
    def get_users(db: Session = Depends(get_db)):
        return db.query(User).all()
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from core.config import settings
from db.models import Base

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Engine
# ─────────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    # Connection pool settings — important for production
    pool_size        = 10,    # max persistent connections
    max_overflow     = 20,    # extra connections under load
    pool_pre_ping    = True,  # test connection before using (handles dropped connections)
    pool_recycle     = 3600,  # recycle connections every 1 hour
    echo             = settings.APP_DEBUG,  # log SQL in dev only
)

# ─────────────────────────────────────────────
#  Session factory
# ─────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind          = engine,
    autocommit    = False,   # always explicit commit
    autoflush     = False,   # flush only when needed
    expire_on_commit = True,
)


# ─────────────────────────────────────────────
#  FastAPI dependency
# ─────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Session is automatically closed after the request finishes,
    even if an exception was raised.

    Inject into route:
        def my_route(db: Session = Depends(get_db)):
            users = db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────────
#  Startup initialisation
# ─────────────────────────────────────────────
def init_db():
    """
    Creates all tables if they don't exist.
    Call this once in main.py lifespan startup.

    NOTE: For production use Alembic migrations instead
    so schema changes are tracked and reversible.
    """
    try:
        # Test connection first
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK.")

        # Create all tables defined in models.py
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created / verified.")

    except Exception as e:
        logger.error(f"Database init failed: {e}")
        raise


def close_db():
    """Dispose engine connection pool on shutdown."""
    engine.dispose()
    logger.info("Database connections closed.")
