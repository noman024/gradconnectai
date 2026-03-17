"""
Database-backed store using SQLAlchemy models.
Maps student_id -> Student rows, professor_id -> Professor rows, etc.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List

from sqlalchemy import select, delete, and_

from app.db.models import (
    Student,
    Professor,
    Match,
    EmailDraft,
    ProfessorSnapshot,
    Opportunity,
    OpportunityType,
)
from app.db.session import get_session


def _parse_datetime(val: Any) -> datetime | None:
    """Parse ISO string or datetime to datetime for DB."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def generate_id() -> str:
    return str(uuid.uuid4())


def _uuid(id_str: str):
    return uuid.UUID(id_str)


def student_set(student_id: str, data: dict[str, Any]) -> None:
    with get_session() as db:
        obj = Student(
            id=_uuid(student_id),
            name=data["name"],
            research_topics=data.get("research_topics") or [],
            embedding=data.get("embedding"),
            embedding_model_version=data.get("embedding_model_version"),
            cv_file=data.get("cv_file"),
            experience_snippet=data.get("experience_snippet"),
            preferences=data.get("preferences") or {},
        )
        db.merge(obj)
        db.commit()


def student_get(student_id: str) -> dict[str, Any] | None:
    with get_session() as db:
        obj = db.get(Student, _uuid(student_id))
        if not obj:
            return None
        return {
            "id": str(obj.id),
            "name": obj.name,
            "research_topics": obj.research_topics,
            "embedding": obj.embedding,
            "embedding_model_version": obj.embedding_model_version,
            "cv_file": obj.cv_file,
            "experience_snippet": obj.experience_snippet,
            "preferences": obj.preferences,
        }


def professor_set(professor_id: str, data: dict[str, Any]) -> None:
    """Upsert professor and record a simple snapshot of the current state."""
    with get_session() as db:
        obj = Professor(
            id=_uuid(professor_id),
            name=data["name"],
            university=data["university"],
            country=data.get("country"),
            region=data.get("region"),
            email=data.get("email"),
            research_topics=data.get("research_topics") or [],
            lab_url=data.get("lab_url"),
            lab_focus=data.get("lab_focus"),
            opportunity_score=float(data.get("opportunity_score", 0.5)),
            embedding=data.get("embedding"),
            embedding_model_version=data.get("embedding_model_version"),
            last_checked=_parse_datetime(data.get("last_checked")),
            active_flag=bool(data.get("active_flag")),
            sources=data.get("sources") or [],
        )
        obj = db.merge(obj)
        db.flush()
        # Persist a simple snapshot for history (valid_from = now, valid_to = None).
        snap = ProfessorSnapshot(
            professor_id=obj.id,
            name=obj.name,
            university=obj.university,
            country=obj.country,
            region=obj.region,
            email=obj.email,
            research_topics=obj.research_topics,
            lab_url=obj.lab_url,
            sources=obj.sources,
            valid_from=datetime.utcnow(),
            valid_to=None,
        )
        db.add(snap)
        db.commit()


def professor_get(professor_id: str) -> dict[str, Any] | None:
    with get_session() as db:
        obj = db.get(Professor, _uuid(professor_id))
        if not obj:
            return None
        return {
            "id": str(obj.id),
            "name": obj.name,
            "university": obj.university,
            "email": obj.email,
            "lab_url": obj.lab_url,
            "lab_focus": obj.lab_focus,
            "research_topics": obj.research_topics,
            "opportunity_score": float(obj.opportunity_score) if obj.opportunity_score is not None else 0.5,
            "sources": obj.sources,
        }


def professor_get_by_name_university(name: str, university: str) -> dict[str, Any] | None:
    """Find professor by name and university (for dedup)."""
    with get_session() as db:
        row = db.execute(
            select(Professor).where(
                and_(
                    Professor.name.ilike(name.strip()),
                    Professor.university.ilike(university.strip()),
                )
            )
        ).scalars().first()
        if not row:
            return None
        return {
            "id": str(row.id),
            "name": row.name,
            "university": row.university,
            "email": row.email,
            "lab_url": row.lab_url,
            "lab_focus": row.lab_focus,
            "research_topics": row.research_topics,
            "opportunity_score": float(row.opportunity_score) if row.opportunity_score is not None else 0.5,
            "embedding": row.embedding,
            "sources": row.sources,
        }


def professors_list() -> list[dict[str, Any]]:
    with get_session() as db:
        rows = db.execute(select(Professor)).scalars().all()
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "university": p.university,
                "email": p.email,
                "lab_url": p.lab_url,
                "lab_focus": p.lab_focus,
                "research_topics": p.research_topics,
                "opportunity_score": float(p.opportunity_score) if p.opportunity_score is not None else 0.5,
                "embedding": p.embedding,
                "sources": p.sources,
            }
            for p in rows
        ]


def matches_upsert(student_id: str, professor_id: str, score: float, opportunity_score: float, final_rank: float) -> None:
    with get_session() as db:
        sid = _uuid(student_id)
        pid = _uuid(professor_id)
        obj = db.get(Match, (sid, pid))
        if obj is None:
            obj = Match(student_id=sid, professor_id=pid, score=score, opportunity_score=opportunity_score, final_rank=final_rank)
        else:
            obj.score = score
            obj.opportunity_score = opportunity_score
            obj.final_rank = final_rank
        db.merge(obj)
        db.commit()


def matches_for_student(student_id: str) -> list[dict[str, Any]]:
    with get_session() as db:
        sid = _uuid(student_id)
        rows = db.execute(
            select(Match).where(Match.student_id == sid).order_by(Match.final_rank.desc())
        ).scalars().all()
        return [
            {
                "student_id": str(m.student_id),
                "professor_id": str(m.professor_id),
                "score": m.score,
                "opportunity_score": m.opportunity_score,
                "final_rank": m.final_rank,
            }
            for m in rows
        ]


def student_delete(student_id: str) -> bool:
    """Remove student and their matches. Returns True if existed."""
    with get_session() as db:
        sid = _uuid(student_id)
        obj = db.get(Student, sid)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True


def student_export(student_id: str) -> dict[str, Any] | None:
    """Export all data we hold for this student (GDPR)."""
    with get_session() as db:
        sid = _uuid(student_id)
        obj = db.get(Student, sid)
        if not obj:
            return None
        out = {
            "id": str(obj.id),
            "name": obj.name,
            "research_topics": obj.research_topics,
            "embedding_model_version": obj.embedding_model_version,
            "preferences": obj.preferences,
        }
        rows = db.execute(
            select(Match).where(Match.student_id == sid).order_by(Match.final_rank.desc())
        ).scalars().all()
        out["matches"] = [
            {
                "student_id": str(m.student_id),
                "professor_id": str(m.professor_id),
                "score": m.score,
                "opportunity_score": m.opportunity_score,
                "final_rank": m.final_rank,
            }
            for m in rows
        ]
        return out


def email_draft_create(student_id: str, professor_id: str, subject: str, body: str) -> str:
    """Persist one email draft for a student–professor pair and return its id."""
    with get_session() as db:
        sid = _uuid(student_id)
        pid = _uuid(professor_id)
        draft = EmailDraft(student_id=sid, professor_id=pid, subject=subject, body=body)
        db.add(draft)
        db.commit()
        return str(draft.id)


def opportunity_create_basic(
    professor_id: str,
    opp_type: OpportunityType,
    source: str | None = None,
    funding: str | None = None,
) -> str:
    """Create a basic opportunity row for a professor (used by discovery)."""
    with get_session() as db:
        pid = _uuid(professor_id)
        opp = Opportunity(
            professor_id=pid,
            type=opp_type,
            funding=funding,
            deadline=None,
            source=source,
            expired=False,
            valid_until=None,
        )
        db.add(opp)
        db.commit()
        return str(opp.id)


def email_drafts_for_student(student_id: str) -> list[dict[str, Any]]:
    """List email drafts for a student, newest first."""
    with get_session() as db:
        sid = _uuid(student_id)
        rows = (
            db.query(EmailDraft)
            .filter(EmailDraft.student_id == sid)
            .order_by(EmailDraft.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "student_id": str(r.student_id),
                "professor_id": str(r.professor_id),
                "subject": r.subject,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def professor_snapshots_for_professor(professor_id: str) -> list[dict[str, Any]]:
    """List snapshots for a professor, newest first."""
    with get_session() as db:
        pid = _uuid(professor_id)
        rows = (
            db.query(ProfessorSnapshot)
            .filter(ProfessorSnapshot.professor_id == pid)
            .order_by(ProfessorSnapshot.valid_from.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "professor_id": str(r.professor_id),
                "name": r.name,
                "university": r.university,
                "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]


def opportunities_for_professor(professor_id: str) -> list[dict[str, Any]]:
    """List opportunities for a professor, newest first."""
    with get_session() as db:
        pid = _uuid(professor_id)
        rows = (
            db.query(Opportunity)
            .filter(Opportunity.professor_id == pid)
            .order_by(Opportunity.created_at.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "professor_id": str(r.professor_id),
                "type": r.type.value if hasattr(r.type, "value") else str(r.type),
                "funding": r.funding,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "source": r.source,
                "expired": r.expired,
                "valid_until": r.valid_until.isoformat() if r.valid_until else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
