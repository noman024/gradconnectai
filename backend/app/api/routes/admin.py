"""Admin/debug endpoints for data inspection. Disabled in production."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.core.audit import get_recent_audit
from app.services.store import (
    professors_list,
    email_drafts_for_student,
    professor_snapshots_for_professor,
    opportunities_for_professor,
    evidence_retention_cleanup,
)

router = APIRouter()


def _admin_allowed() -> bool:
    return settings.ENVIRONMENT != "production"


class EvidenceCleanupRequest(BaseModel):
    older_than_days: int = 90
    dry_run: bool = True


@router.get("/professors")
async def admin_list_professors():
    """List all professors with counts. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    profs = professors_list()
    return {
        "count": len(profs),
        "professors": [
            {
                "id": p["id"],
                "name": p["name"],
                "university": p["university"],
                "lab_focus": p.get("lab_focus"),
                "opportunity_score": p.get("opportunity_score"),
            }
            for p in profs[:100]
        ],
    }


@router.get("/stats")
async def admin_stats():
    """Basic stats for debugging. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    profs = professors_list()
    return {
        "professors_count": len(profs),
        "environment": settings.ENVIRONMENT,
    }


@router.get("/audit")
async def admin_audit(limit: int = 100):
    """Return recent audit_log entries. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    return {"entries": get_recent_audit(limit=limit)}


@router.get("/students/{student_id}/email-drafts")
async def admin_student_email_drafts(student_id: str):
    """List email drafts for a student. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    return {"drafts": email_drafts_for_student(student_id)}


@router.get("/professors/{professor_id}/snapshots")
async def admin_professor_snapshots(professor_id: str):
    """List snapshots for a professor. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    return {"snapshots": professor_snapshots_for_professor(professor_id)}


@router.get("/professors/{professor_id}/opportunities")
async def admin_professor_opportunities(professor_id: str):
    """List opportunities for a professor. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    return {"opportunities": opportunities_for_professor(professor_id)}


@router.post("/cleanup/evidence")
async def admin_cleanup_evidence(body: EvidenceCleanupRequest):
    """Dry-run or execute retention cleanup for evidence artifacts. Admin only in production."""
    if not _admin_allowed():
        raise HTTPException(status_code=403, detail="Admin endpoints disabled in production")
    return evidence_retention_cleanup(
        older_than_days=body.older_than_days,
        dry_run=body.dry_run,
    )
