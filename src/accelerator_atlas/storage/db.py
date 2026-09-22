"""Session factory + convenience helpers for the canonical SQLite DB."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from accelerator_atlas.schema.models import Base, get_engine, init_db

DB_PATH = os.environ.get("ACCELERATOR_ATLAS_DB", "data/accelerators.db")


def ensure_db(db_path: str = DB_PATH) -> None:
    """Create parent dirs and initialize tables."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)


_engine = None
_SessionFactory: sessionmaker | None = None


def _factory(db_path: str = DB_PATH) -> sessionmaker:
    global _engine, _SessionFactory
    if _SessionFactory is None:
        ensure_db(db_path)
        _engine = get_engine(db_path)
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _SessionFactory


@contextmanager
def session_scope(db_path: str = DB_PATH) -> Iterator[Session]:
    """Commit-on-success, rollback-on-error session context."""
    session = _factory(db_path)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "ensure_db", "session_scope", "DB_PATH"]
