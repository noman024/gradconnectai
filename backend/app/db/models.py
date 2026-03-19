"""
SQLAlchemy models for GradConnectAI. Mirror schema.sql.
Requires pgvector: pip install pgvector; in DB: CREATE EXTENSION vector;
"""
import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from app.core.timezone import now_dhaka


def _dhaka_now() -> datetime:
    return now_dhaka()

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # type: ignore


class Base(DeclarativeBase):
    pass


# Embedding dimension must match the model output (384 for all-MiniLM-L6-v2).
EMBEDDING_DIM = 384


class OpportunityType(str, Enum):
    master = "master"
    phd = "phd"
    postdoc = "postdoc"


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    university: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    research_topics: Mapped[list] = mapped_column(JSONB, default=list)
    lab_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lab_focus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True) if Vector else None  # type: ignore
    embedding_model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, onupdate=_dhaka_now)

    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="professor", cascade="all, delete-orphan")
    snapshots: Mapped[list["ProfessorSnapshot"]] = relationship(back_populates="professor", cascade="all, delete-orphan")


class ProfessorSnapshot(Base):
    __tablename__ = "professor_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    university: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    research_topics: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    lab_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sources: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)

    professor: Mapped["Professor"] = relationship(back_populates="snapshots")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[OpportunityType] = mapped_column(SQLEnum(OpportunityType), nullable=False)
    funding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expired: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, onupdate=_dhaka_now)

    professor: Mapped["Professor"] = relationship(back_populates="opportunities")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    research_topics: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True) if Vector else None  # type: ignore
    embedding_model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cv_file: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experience_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # preferences: { "countries": [], "universities": [], "fields": [] }
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, onupdate=_dhaka_now)

    matches: Mapped[list["Match"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    email_drafts: Mapped[list["EmailDraft"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Match(Base):
    __tablename__ = "matches"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    opportunity_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_rank: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, onupdate=_dhaka_now)

    student: Mapped["Student"] = relationship(back_populates="matches")
    professor: Mapped["Professor"] = relationship()


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    professor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("professors.id", ondelete="CASCADE"), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)

    student: Mapped["Student"] = relationship(back_populates="email_drafts")
    professor: Mapped["Professor"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)


# =========================================================
# Evidence-gated discovery models (productionization)
# =========================================================


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    robots_allowed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=True
    )
    extractor: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ProfessorEvidence(Base):
    __tablename__ = "professor_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    professor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professors.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True
    )
    extraction_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_match: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_dhaka_now)
