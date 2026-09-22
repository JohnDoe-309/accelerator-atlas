"""Canonical schema for Accelerator Atlas.

One SQLite database, unified across YC, SPC, a16z Speedrun, EF.
All enriched fields carry (value, source, confidence, fetched_at) provenance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AcceleratorSlug(str, Enum):
    YC = "yc"
    SPC = "spc"
    SPEEDRUN = "a16z_speedrun"
    EF = "ef"


class CompanyStatus(str, Enum):
    ACTIVE = "Active"
    ACQUIRED = "Acquired"
    PUBLIC = "Public"
    DEAD = "Dead"
    UNKNOWN = "Unknown"


class Base(DeclarativeBase):
    pass


class Accelerator(Base):
    """One row per accelerator. Hand-curated meta."""

    __tablename__ = "accelerators"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    hq_location: Mapped[str | None] = mapped_column(String(128))
    website: Mapped[str | None] = mapped_column(String(256))
    founders: Mapped[list | None] = mapped_column(JSON)  # [{name, role}]
    program_duration_weeks: Mapped[int | None] = mapped_column(Integer)
    investment_amount_usd: Mapped[float | None] = mapped_column(Float)
    investment_equity_pct: Mapped[float | None] = mapped_column(Float)
    investment_terms_note: Mapped[str | None] = mapped_column(Text)
    batch_cadence: Mapped[str | None] = mapped_column(String(64))  # e.g., "biannual", "quarterly"
    focus_areas: Mapped[list | None] = mapped_column(JSON)
    description: Mapped[str | None] = mapped_column(Text)
    total_companies_funded: Mapped[int | None] = mapped_column(Integer)
    notable_alumni: Mapped[list | None] = mapped_column(JSON)
    data_sources: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    batches: Mapped[list["Batch"]] = relationship(back_populates="accelerator")
    companies: Mapped[list["Company"]] = relationship(back_populates="accelerator")


class Batch(Base):
    """One row per cohort/batch per accelerator.

    Examples:
      YC: "Winter 2024", season=Winter, year=2024
      Speedrun: "SR006", year=2026 (approx)
      EF: "EF24-LON", year=2024, location=London
      SPC: "Residency 2024" / "Fellowship Fall 2024"
    """

    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("accelerator_id", "slug", name="uq_batch"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    accelerator_id: Mapped[int] = mapped_column(ForeignKey("accelerators.id"), index=True)
    slug: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "winter-2024"
    name: Mapped[str] = mapped_column(String(128))  # e.g. "Winter 2024"
    season: Mapped[str | None] = mapped_column(String(32))  # Winter|Summer|Fall|Spring|N/A
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    location: Mapped[str | None] = mapped_column(String(128))  # for EF cohorts
    cohort_number: Mapped[int | None] = mapped_column(Integer)  # for Speedrun SR001..
    company_count: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    demo_day_date: Mapped[datetime | None] = mapped_column(DateTime)
    api_url: Mapped[str | None] = mapped_column(String(256))  # source endpoint for this batch
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accelerator: Mapped[Accelerator] = relationship(back_populates="batches")
    companies: Mapped[list["Company"]] = relationship(back_populates="batch")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("accelerator_id", "slug", name="uq_company_per_accel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    accelerator_id: Mapped[int] = mapped_column(ForeignKey("accelerators.id"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), index=True)

    source_id: Mapped[str | None] = mapped_column(String(64), index=True)  # YC's id, etc.
    slug: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    former_names: Mapped[list | None] = mapped_column(JSON)

    # Core descriptive (usually from primary source, high confidence)
    website: Mapped[str | None] = mapped_column(String(512))
    one_liner: Mapped[str | None] = mapped_column(Text)
    long_description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(512))

    # Status
    status: Mapped[str] = mapped_column(String(32), default=CompanyStatus.UNKNOWN.value, index=True)
    status_source: Mapped[str | None] = mapped_column(String(64))
    status_confidence: Mapped[float | None] = mapped_column(Float)
    status_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Taxonomy
    industry_primary: Mapped[str | None] = mapped_column(String(128), index=True)
    industry_sub: Mapped[str | None] = mapped_column(String(128))
    industries: Mapped[list | None] = mapped_column(JSON)
    tags: Mapped[list | None] = mapped_column(JSON)
    tags_normalized: Mapped[list | None] = mapped_column(JSON)  # Grok-normalized
    stage: Mapped[str | None] = mapped_column(String(64))  # Early|Growth|Unicorn|Public etc.
    is_b2b: Mapped[bool | None] = mapped_column(Boolean)
    is_ai: Mapped[bool | None] = mapped_column(Boolean)
    is_nonprofit: Mapped[bool | None] = mapped_column(Boolean)
    is_hiring: Mapped[bool | None] = mapped_column(Boolean)
    is_top_company: Mapped[bool | None] = mapped_column(Boolean)

    # Geography
    all_locations: Mapped[str | None] = mapped_column(String(256))
    hq_location: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128), index=True)
    regions: Mapped[list | None] = mapped_column(JSON)

    # Team
    team_size_current: Mapped[int | None] = mapped_column(Integer)
    team_size_source: Mapped[str | None] = mapped_column(String(64))
    team_size_confidence: Mapped[float | None] = mapped_column(Float)
    team_size_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Funding (aggregate; detailed rounds in funding_rounds)
    total_funding_usd: Mapped[float | None] = mapped_column(Float)
    total_funding_source: Mapped[str | None] = mapped_column(String(64))
    total_funding_confidence: Mapped[float | None] = mapped_column(Float)
    last_round_type: Mapped[str | None] = mapped_column(String(64))
    last_round_amount_usd: Mapped[float | None] = mapped_column(Float)
    last_round_date: Mapped[datetime | None] = mapped_column(DateTime)
    valuation_usd: Mapped[float | None] = mapped_column(Float)

    # Revenue
    revenue_estimate_usd: Mapped[float | None] = mapped_column(Float)
    revenue_source: Mapped[str | None] = mapped_column(String(64))
    revenue_confidence: Mapped[float | None] = mapped_column(Float)
    revenue_fetched_at: Mapped[datetime | None] = mapped_column(DateTime)

    # External refs
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    crunchbase_url: Mapped[str | None] = mapped_column(String(512))
    twitter_url: Mapped[str | None] = mapped_column(String(512))
    source_url: Mapped[str | None] = mapped_column(String(512))  # URL on accelerator site

    # Dates
    launched_at: Mapped[datetime | None] = mapped_column(DateTime)
    founded_year: Mapped[int | None] = mapped_column(Integer, index=True)

    # Provenance
    data_sources: Mapped[list | None] = mapped_column(JSON)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)  # original record for audit
    last_enriched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    accelerator: Mapped[Accelerator] = relationship(back_populates="companies")
    batch: Mapped["Batch | None"] = relationship(back_populates="companies")
    founders: Mapped[list["Founder"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    funding_rounds: Mapped[list["FundingRound"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Founder(Base):
    __tablename__ = "founders"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    role: Mapped[str | None] = mapped_column(String(128))  # CEO, CTO, Founding CEO, etc.
    linkedin_url: Mapped[str | None] = mapped_column(String(512))
    twitter_url: Mapped[str | None] = mapped_column(String(512))
    image_url: Mapped[str | None] = mapped_column(String(512))
    prior_exits: Mapped[int | None] = mapped_column(Integer)
    prior_companies: Mapped[list | None] = mapped_column(JSON)
    education: Mapped[list | None] = mapped_column(JSON)
    is_repeat_founder: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)

    company: Mapped[Company] = relationship(back_populates="founders")


class FundingRound(Base):
    __tablename__ = "funding_rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    round_type: Mapped[str | None] = mapped_column(String(64))  # Pre-Seed|Seed|A|B|...
    amount_usd: Mapped[float | None] = mapped_column(Float)
    valuation_usd: Mapped[float | None] = mapped_column(Float)
    round_date: Mapped[datetime | None] = mapped_column(DateTime)
    investors: Mapped[list | None] = mapped_column(JSON)
    lead_investor: Mapped[str | None] = mapped_column(String(256))
    source: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(512))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped[Company] = relationship(back_populates="funding_rounds")


class EnrichmentLog(Base):
    """Audit trail of every enrichment attempt."""

    __tablename__ = "enrichment_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    source: Mapped[str] = mapped_column(String(64))  # firecrawl|wayback|grok|yc_oss
    operation: Mapped[str] = mapped_column(String(64))  # scrape|search|extract|status_check
    url: Mapped[str | None] = mapped_column(String(512))
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    fields_updated: Mapped[list | None] = mapped_column(JSON)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # for idempotency
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Insight(Base):
    """Grok-generated narratives (whitespaces, company summaries, etc.)."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)  # whitespace|company_one_liner|category_summary
    subject_type: Mapped[str | None] = mapped_column(String(32))  # company|category|accelerator|batch
    subject_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str | None] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list | None] = mapped_column(JSON)  # citations from local DB
    input_hash: Mapped[str] = mapped_column(String(64), index=True)  # for idempotent regen
    model: Mapped[str] = mapped_column(String(64))
    usage_id: Mapped[int | None] = mapped_column(ForeignKey("grok_usage.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class GrokUsage(Base):
    """Every xAI call logged. Budget cap enforced via sum(usd_cost)."""

    __tablename__ = "grok_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    model: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(64), index=True)  # batch_normalize_tags|nl_filter|ask_anything|...
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer)
    usd_cost: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_hash: Mapped[str | None] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def get_engine(db_path: str = "data/accelerators.db", echo: bool = False):
    """Return a SQLAlchemy engine for the canonical DB."""
    return create_engine(f"sqlite:///{db_path}", echo=echo, future=True)


def init_db(db_path: str = "data/accelerators.db") -> None:
    """Create all tables if they don't exist."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
