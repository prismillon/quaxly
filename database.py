import os
from contextlib import contextmanager

import redis
import redis.asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool

from models import Base

def _database_url() -> str:
    """Return the SQLAlchemy URL with the psycopg (v3) driver made explicit.

    The deployment secret stores a plain ``postgresql://`` URL. SQLAlchemy 2.1
    already defaults that to psycopg v3, but spelling the driver out keeps the
    behaviour stable across SQLAlchemy versions.
    """
    url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/quaxly")
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


DATABASE_URL = _database_url()

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=os.environ.get("SQL_DEBUG", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ScopedSession = scoped_session(SessionLocal)

redis_url = os.getenv("REDIS_URL", "localhost")
r = redis.asyncio.Redis(host=redis_url, port=6379, socket_keepalive=True)
rs = redis.Redis(host=redis_url, port=6379)


def create_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all tables in the database (use with caution!)"""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Ensures proper cleanup and error handling.

    Usage:
        with get_db_session() as session:
            # Use session here
            user = session.query(User).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_session():
    """
    Get a database session.
    Remember to call session.close() when done!

    For async code, prefer using get_db_session() context manager.
    """
    return SessionLocal()


class AsyncSessionManager:
    """
    Async session manager for use in async functions.
    This is a simple wrapper that can be extended for async SQLAlchemy if needed.
    """

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = SessionLocal()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()


def get_async_session():
    """Get an async session manager"""
    return AsyncSessionManager()


def health_check():
    """Check if database connection is healthy"""
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False


def init_db():
    """Initialize the database with all tables"""
    try:
        create_tables()
        print("Database initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize database: {e}")
        return False
