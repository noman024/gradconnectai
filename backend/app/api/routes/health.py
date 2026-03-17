from fastapi import APIRouter

from app.core.config import settings
from app.db.session import get_session
from app.db.models import Professor, Student

router = APIRouter()


@router.get("")
async def health():
    """Basic liveness check."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}


@router.get("/ready")
async def readiness():
    """Readiness: DB connectivity and basic counts."""
    try:
        with get_session() as db:
            from sqlalchemy import func, select
            prof_count = db.execute(select(func.count(Professor.id))).scalar_one_or_none() or 0
            student_count = db.execute(select(func.count(Student.id))).scalar_one_or_none() or 0
        return {
            "status": "ready",
            "database": "connected",
            "professors": prof_count,
            "students": student_count,
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "database": "error",
            "error": str(e),
        }
