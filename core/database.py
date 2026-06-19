"""
SQLite database layer using SQLAlchemy ORM.
Stores program snapshots and change history.
"""

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import config
from loguru import logger


class Base(DeclarativeBase):
    pass


# ── ORM Models ────────────────────────────────────────────────────────────────

class DBProgram(Base):
    """Stores the latest known state of each program."""
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    handle = Column(String(200), nullable=False)
    name = Column(String(500))
    url = Column(String(1000))
    state = Column(String(50), default="public")
    offers_bounties = Column(Boolean, default=True)
    bounty_min = Column(Float, nullable=True)
    bounty_max = Column(Float, nullable=True)
    bounty_currency = Column(String(10), default="USD")
    # Serialized JSON list of scope identifiers for quick diff
    in_scope_json = Column(Text, default="[]")
    out_of_scope_json = Column(Text, default="[]")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_snapshot = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_in_scope(self) -> list:
        return json.loads(self.in_scope_json or "[]")

    def set_in_scope(self, items: list) -> None:
        self.in_scope_json = json.dumps(items)

    def get_out_of_scope(self) -> list:
        return json.loads(self.out_of_scope_json or "[]")

    def set_out_of_scope(self, items: list) -> None:
        self.out_of_scope_json = json.dumps(items)


class DBChangeLog(Base):
    """Immutable log of every detected change."""
    __tablename__ = "change_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False)
    program_handle = Column(String(200), nullable=False)
    program_name = Column(String(500))
    program_url = Column(String(1000))
    change_type = Column(String(50), nullable=False)
    detail = Column(Text)
    added_scopes_json = Column(Text, default="[]")
    removed_scopes_json = Column(Text, default="[]")
    old_bounty = Column(String(200), nullable=True)
    new_bounty = Column(String(200), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)


# ── Engine & Session ──────────────────────────────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{config.database_path}"
        _engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})

        # Enable WAL mode for better concurrent reads
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def init_db() -> None:
    """Create all tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info(f"Database initialized at: {config.database_path}")


def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal()


# ── Database Operations ───────────────────────────────────────────────────────

def get_program(platform: str, handle: str) -> Optional[DBProgram]:
    """Fetch a program record by platform + handle."""
    with get_session() as session:
        return (
            session.query(DBProgram)
            .filter_by(platform=platform, handle=handle)
            .first()
        )


def upsert_program(
    platform: str,
    handle: str,
    name: str,
    url: str,
    in_scope: list,
    out_of_scope: list,
    state: str = "public",
    offers_bounties: bool = True,
    bounty_min: Optional[float] = None,
    bounty_max: Optional[float] = None,
    bounty_currency: str = "USD",
) -> DBProgram:
    """Insert or update a program snapshot."""
    with get_session() as session:
        prog = (
            session.query(DBProgram)
            .filter_by(platform=platform, handle=handle)
            .first()
        )
        if prog is None:
            prog = DBProgram(
                platform=platform,
                handle=handle,
                name=name,
                url=url,
                state=state,
                offers_bounties=offers_bounties,
                bounty_min=bounty_min,
                bounty_max=bounty_max,
                bounty_currency=bounty_currency,
                first_seen=datetime.utcnow(),
            )
            session.add(prog)
        else:
            prog.name = name
            prog.url = url
            prog.state = state
            prog.offers_bounties = offers_bounties
            prog.bounty_min = bounty_min
            prog.bounty_max = bounty_max
            prog.bounty_currency = bounty_currency
            prog.last_snapshot = datetime.utcnow()

        prog.set_in_scope(in_scope)
        prog.set_out_of_scope(out_of_scope)
        session.commit()
        session.refresh(prog)
        return prog


def log_change(
    platform: str,
    program_handle: str,
    program_name: str,
    program_url: str,
    change_type: str,
    detail: str,
    added_scopes: list = None,
    removed_scopes: list = None,
    old_bounty: str = None,
    new_bounty: str = None,
    detected_at: datetime = None,
) -> DBChangeLog:
    """Persist a detected change to the change log."""
    with get_session() as session:
        entry = DBChangeLog(
            platform=platform,
            program_handle=program_handle,
            program_name=program_name,
            program_url=program_url,
            change_type=change_type,
            detail=detail,
            added_scopes_json=json.dumps(added_scopes or []),
            removed_scopes_json=json.dumps(removed_scopes or []),
            old_bounty=old_bounty,
            new_bounty=new_bounty,
            detected_at=detected_at or datetime.utcnow(),
            notified=False,
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def get_recent_changes(limit: int = 50) -> List[DBChangeLog]:
    """Fetch the most recent change log entries."""
    with get_session() as session:
        return (
            session.query(DBChangeLog)
            .order_by(DBChangeLog.detected_at.desc(), DBChangeLog.id.asc())
            .limit(limit)
            .all()
        )


def get_all_programs(platform: Optional[str] = None) -> List[DBProgram]:
    """List all tracked programs, optionally filtered by platform."""
    with get_session() as session:
        q = session.query(DBProgram)
        if platform:
            q = q.filter_by(platform=platform)
        return q.order_by(DBProgram.platform, DBProgram.name).all()


def get_new_programs(limit: int = 10) -> List[DBProgram]:
    """Fetch recently discovered programs, sorted by discovery date."""
    with get_session() as session:
        return (
            session.query(DBProgram)
            .order_by(DBProgram.first_seen.desc())
            .limit(limit)
            .all()
        )


def get_recent_updates(limit: int = 10) -> List[DBChangeLog]:
    """Fetch recent change log entries, filtered by program updates."""
    with get_session() as session:
        return (
            session.query(DBChangeLog)
            .order_by(DBChangeLog.detected_at.desc(), DBChangeLog.id.asc())
            .limit(limit)
            .all()
        )


def get_recent_updates_by_platform(platform: str, limit: int = 3) -> List[DBChangeLog]:
    """Fetch recent change log entries for a specific platform, filtered by scope/program changes."""
    from core.models import ChangeType
    with get_session() as session:
        return (
            session.query(DBChangeLog)
            .filter_by(platform=platform)
            .filter(DBChangeLog.change_type.in_([
                ChangeType.NEW_SCOPE.value,
                ChangeType.REMOVED_SCOPE.value,
                ChangeType.NEW_PROGRAM.value
            ]))
            .order_by(DBChangeLog.detected_at.desc(), DBChangeLog.id.asc())
            .limit(limit)
            .all()
        )
