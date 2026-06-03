from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from configs.settings import settings
from loguru import logger

# Detect if SQLite is in use to inject necessary threading flags
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Configure database pool size and max overflow for high-concurrency Postgres
connect_args = {"check_same_thread": False} if is_sqlite else {}
pool_kwargs = {} if is_sqlite else {"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True}

try:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        **pool_kwargs
    )
    logger.info("Database engine created successfully.")
except Exception as e:
    logger.error(f"Failed to create database engine for URL: {settings.DATABASE_URL}. Error: {e}")
    raise e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a thread-local database session.
    Ensures rollback on exceptions and final cleanup close.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed. Rolling back database session. Error: {e}")
        raise e
    finally:
        db.close()

@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions. Useful in background threads, 
    tasks, or OpenCV pipeline runners outside FastAPI routers.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Context transaction failed. Rolling back. Error: {e}")
        raise e
    finally:
        db.close()
