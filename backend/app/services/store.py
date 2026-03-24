"""
Database-backed store using SQLAlchemy models.
Maps student_id -> Student rows, professor_id -> Professor rows, etc.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
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
    SourceDocument,
    ExtractionRun,
    ProfessorEvidence,
)
from app.db.session import get_session
from app.core.timezone import now_dhaka, to_dhaka


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


def _iso_dhaka(dt: datetime | date | None) -> str | None:
    """Serialize datetime/date values into ISO strings in Dhaka timezone."""
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        # Keep date-only fields stable and timezone-agnostic.
        return dt.isoformat()
    converted = to_dhaka(dt)
    return converted.isoformat() if converted else None


def source_document_create(
    *,
    url: str,
    status_code: int | None = None,
    robots_allowed: bool | None = None,
    content_type: str | None = None,
    content_hash: str | None = None,
    content_text: str | None = None,
) -> str:
    """Create a source_documents row and return its id."""
    with get_session() as db:
        doc = SourceDocument(
            url=url,
            status_code=status_code,
            robots_allowed=robots_allowed,
            content_type=content_type,
            content_hash=content_hash,
            content_text=content_text,
        )
        db.add(doc)
        db.commit()
        return str(doc.id)


def extraction_run_create(
    *,
    source_document_id: str | None,
    extractor: str,
    llm_model: str | None = None,
    prompt_version: str | None = None,
    success: bool = False,
    error: str | None = None,
) -> str:
    """Create an extraction_runs row and return its id."""
    with get_session() as db:
        run = ExtractionRun(
            source_document_id=_uuid(source_document_id) if source_document_id else None,
            extractor=extractor,
            llm_model=llm_model,
            prompt_version=prompt_version,
            success=success,
            error=error,
        )
        db.add(run)
        db.commit()
        return str(run.id)


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


def professor_set(
    professor_id: str,
    data: dict[str, Any],
    *,
    evidence: list[dict[str, Any]] | None = None,
    source_document_id: str | None = None,
    extraction_run_id: str | None = None,
) -> None:
    """Upsert professor and record a simple snapshot of the current state (and optional evidence)."""
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
            valid_from=now_dhaka(),
            valid_to=None,
        )
        db.add(snap)
        # Persist evidence (if provided) for auditability.
        if evidence:
            for e in evidence:
                db.add(
                    ProfessorEvidence(
                        professor_id=obj.id,
                        source_document_id=_uuid(source_document_id) if source_document_id else None,
                        extraction_run_id=_uuid(extraction_run_id) if extraction_run_id else None,
                        url=str(e.get("url") or (data.get("lab_url") or "")),
                        evidence_type=str(e.get("evidence_type") or "unknown"),
                        evidence_value=(str(e["evidence_value"]) if e.get("evidence_value") is not None else None),
                        raw_match=(str(e["raw_match"]) if e.get("raw_match") is not None else None),
                        snippet=(str(e["snippet"]) if e.get("snippet") is not None else None),
                        selector=(str(e["selector"]) if e.get("selector") is not None else None),
                        confidence=float(e.get("confidence") or 1.0),
                    )
                )
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


def professors_list(*, include_embedding: bool = False) -> list[dict[str, Any]]:
    with get_session() as db:
        rows = db.execute(select(Professor)).scalars().all()
        result: list[dict[str, Any]] = []
        for p in rows:
            item = {
                "id": str(p.id),
                "name": p.name,
                "university": p.university,
                "email": p.email,
                "lab_url": p.lab_url,
                "lab_focus": p.lab_focus,
                "research_topics": p.research_topics,
                "opportunity_score": float(p.opportunity_score) if p.opportunity_score is not None else 0.5,
                "sources": p.sources,
            }
            if include_embedding:
                item["embedding"] = p.embedding
            result.append(item)
        return result


def matches_latest_timestamp(student_id: str) -> datetime | None:
    """Return the most recent updated_at of matches for a student, or None if none exist."""
    with get_session() as db:
        sid = _uuid(student_id)
        row = db.execute(
            select(Match.updated_at).where(Match.student_id == sid).order_by(Match.updated_at.desc()).limit(1)
        ).scalar_one_or_none()
        return row


def professors_updated_since(since: datetime) -> bool:
    """Return True if any professor has been updated after the given timestamp."""
    with get_session() as db:
        row = db.execute(
            select(Professor.id).where(Professor.updated_at > since).limit(1)
        ).scalar_one_or_none()
        return row is not None


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


def opportunity_create_structured(
    professor_id: str,
    opportunities: list[dict[str, Any]],
    *,
    default_source: str | None = None,
) -> int:
    """Create multiple structured opportunity rows for a professor. Returns created count."""
    with get_session() as db:
        pid = _uuid(professor_id)
        created = 0
        for o in opportunities or []:
            if not isinstance(o, dict):
                continue
            raw_type = str(o.get("type") or "phd").strip().lower()
            if raw_type not in {"master", "phd", "postdoc"}:
                raw_type = "phd"
            opp_type = OpportunityType(raw_type)
            signal = (str(o.get("signal") or "").strip() or None)
            confidence = o.get("confidence")
            try:
                conf_text = f"{float(confidence):.2f}"
            except Exception:
                conf_text = None
            funding = signal
            if conf_text:
                funding = f"{signal or 'signal'} (confidence={conf_text})"
            source = (str(o.get("source_url") or "").strip() or default_source)
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
            created += 1
        if created > 0:
            db.commit()
        return created


def email_drafts_for_student(student_id: str) -> list[dict[str, Any]]:
    """List email drafts for a student, newest first."""
    with get_session() as db:
        sid = _uuid(student_id)
        rows = db.execute(
            select(EmailDraft)
            .where(EmailDraft.student_id == sid)
            .order_by(EmailDraft.created_at.desc())
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "student_id": str(r.student_id),
                "professor_id": str(r.professor_id),
                "subject": r.subject,
                "created_at": _iso_dhaka(r.created_at),
            }
            for r in rows
        ]


def professor_snapshots_for_professor(professor_id: str) -> list[dict[str, Any]]:
    """List snapshots for a professor, newest first."""
    with get_session() as db:
        pid = _uuid(professor_id)
        rows = db.execute(
            select(ProfessorSnapshot)
            .where(ProfessorSnapshot.professor_id == pid)
            .order_by(ProfessorSnapshot.valid_from.desc())
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "professor_id": str(r.professor_id),
                "name": r.name,
                "university": r.university,
                "valid_from": _iso_dhaka(r.valid_from),
                "valid_to": _iso_dhaka(r.valid_to),
            }
            for r in rows
        ]


def opportunities_for_professor(professor_id: str) -> list[dict[str, Any]]:
    """List opportunities for a professor, newest first."""
    with get_session() as db:
        pid = _uuid(professor_id)
        rows = db.execute(
            select(Opportunity)
            .where(Opportunity.professor_id == pid)
            .order_by(Opportunity.created_at.desc())
        ).scalars().all()
        return [
            {
                "id": str(r.id),
                "professor_id": str(r.professor_id),
                "type": r.type.value if hasattr(r.type, "value") else str(r.type),
                "funding": r.funding,
                "deadline": _iso_dhaka(r.deadline),
                "source": r.source,
                "expired": r.expired,
                "valid_until": _iso_dhaka(r.valid_until),
                "created_at": _iso_dhaka(r.created_at),
            }
            for r in rows
        ]


def evidence_retention_cleanup(*, older_than_days: int = 90, dry_run: bool = True) -> dict[str, Any]:
    """
    Cleanup old evidence artifacts.

    Targets:
    - professor_evidence.created_at
    - extraction_runs.started_at
    - source_documents.fetched_at
    """
    days = max(1, int(older_than_days))
    cutoff = now_dhaka() - timedelta(days=days)

    with get_session() as db:
        from sqlalchemy import func

        evidence_count = db.execute(
            select(func.count()).select_from(ProfessorEvidence).where(ProfessorEvidence.created_at < cutoff)
        ).scalar() or 0
        runs_count = db.execute(
            select(func.count()).select_from(ExtractionRun).where(ExtractionRun.started_at < cutoff)
        ).scalar() or 0
        docs_count = db.execute(
            select(func.count()).select_from(SourceDocument).where(SourceDocument.fetched_at < cutoff)
        ).scalar() or 0

        if dry_run:
            return {
                "dry_run": True,
                "older_than_days": days,
                "cutoff_iso": _iso_dhaka(cutoff),
                "would_delete": {
                    "professor_evidence": evidence_count,
                    "extraction_runs": runs_count,
                    "source_documents": docs_count,
                },
            }

        deleted_evidence = db.execute(
            delete(ProfessorEvidence).where(ProfessorEvidence.created_at < cutoff)
        ).rowcount
        deleted_runs = db.execute(
            delete(ExtractionRun).where(ExtractionRun.started_at < cutoff)
        ).rowcount
        deleted_docs = db.execute(
            delete(SourceDocument).where(SourceDocument.fetched_at < cutoff)
        ).rowcount
        db.commit()

        return {
            "dry_run": False,
            "older_than_days": days,
            "cutoff_iso": _iso_dhaka(cutoff),
            "deleted": {
                "professor_evidence": int(deleted_evidence or 0),
                "extraction_runs": int(deleted_runs or 0),
                "source_documents": int(deleted_docs or 0),
            },
        }
