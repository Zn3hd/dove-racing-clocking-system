"""PostgreSQL session factory. Schema is managed by sql/001_schema.sql."""
import os
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_factory = None

def get_engine():
    global _engine, _factory
    if _engine is None:
        url = os.getenv("DATABASE_URL")
        if not url or not url.startswith("postgresql"):
            raise RuntimeError("Set DATABASE_URL to a PostgreSQL connection string")
        _engine = create_engine(url, pool_pre_ping=True)
        _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine

def get_db() -> Generator[Session, None, None]:
    get_engine()
    with _factory() as session:
        yield session
