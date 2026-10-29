from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JsonColumn


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


STATUSES = ("applied", "interview", "offer", "rejected")
SENTIMENTS = ("bullish", "bearish", "neutral")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    # Where open roles come from: greenhouse | lever | ashby | "" (news only)
    board: Mapped[str] = mapped_column(String(20), default="")
    board_slug: Mapped[str] = mapped_column(String(120), default="")
    careers_url: Mapped[str] = mapped_column(String(500), default="")
    # Search phrase for news; defaults to the name. Short names like "Box" need more
    news_query: Mapped[str] = mapped_column(String(200), default="")
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    applications: Mapped[list["Application"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["JobSnapshot"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(200))
    team: Mapped[str] = mapped_column(String(120), default="")  # matched against board teams
    job_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="applied")
    applied_on: Mapped[date] = mapped_column(Date)
    follow_up_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[float] = mapped_column(Float, default=0)  # order within a column
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship(back_populates="applications")


class JobSnapshot(Base):
    """What the company's job board listed on one scan. Signals come from diffing two."""

    __tablename__ = "job_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    total: Mapped[int] = mapped_column(Integer)
    by_team: Mapped[dict] = mapped_column(JsonColumn)  # team → count
    # id → {title, team, location, url}; kept so we can say which roles appeared/vanished
    jobs: Mapped[dict] = mapped_column(JsonColumn)

    company: Mapped[Company] = relationship(back_populates="snapshots")


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("company_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    # hiring | news. Hiring signals come from snapshot diffs; news from RSS/HN + the LLM
    source: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(40))  # e.g. team_growth, layoffs, funding
    sentiment: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(500))
    explanation: Mapped[str] = mapped_column(Text, default="")
    # Google News article links run past 1,000 characters
    url: Mapped[str] = mapped_column(Text, default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    # Dedup key: the feed's guid / HN id / a hash for hiring diffs
    external_id: Mapped[str] = mapped_column(String(200))
    classified_by: Mapped[str] = mapped_column(String(20), default="")  # llm | keywords | rule
    # Off-topic news is kept (so it isn't classified again every night) but never shown
    relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    found_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    digest_id: Mapped[int | None] = mapped_column(ForeignKey("digests.id"), nullable=True)

    company: Mapped[Company] = relationship(back_populates="signals")


class Run(Base):
    """One scan: nightly or on demand, all companies or one."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(20))  # schedule | manual
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | done | failed
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # company name → {jobs, news_seen, new_signals, error, ms}
    stats: Mapped[dict] = mapped_column(JsonColumn, default=dict)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    trigger: Mapped[str] = mapped_column(String(20))
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    follow_ups: Mapped[list] = mapped_column(JsonColumn, default=list)  # application ids due
    emailed_to: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    html: Mapped[str] = mapped_column(Text, default="")
