from fastapi import APIRouter, HTTPException

from app.schemas.students import StudentCreate, StudentProfileResponse, PortfolioAnalyzeResponse
from app.core.validation import validate_name, validate_cv_text, validate_preferences
from app.core.audit import log_audit
from app.services.portfolio.analyzer import analyze_portfolio
from app.services.store import student_set, student_get, generate_id

router = APIRouter()


@router.post("", response_model=PortfolioAnalyzeResponse)
async def create_student_and_analyze(body: StudentCreate):
    err = validate_name(body.name)
    if err:
        raise HTTPException(status_code=400, detail=err)
    err = validate_cv_text(body.cv_text)
    if err:
        raise HTTPException(status_code=400, detail=err)
    prefs = body.preferences if isinstance(body.preferences, dict) else body.preferences.model_dump()
    err = validate_preferences(prefs)
    if err:
        raise HTTPException(status_code=400, detail=err)
    """Create student profile and run portfolio analysis (topics + embedding)."""
    result = analyze_portfolio(cv_text=body.cv_text, preferences=prefs)
    student_id = generate_id()
    student_set(student_id, {
        "name": body.name,
        "research_topics": result.research_topics,
        "embedding": result.embedding,
        "embedding_model_version": result.embedding_model_version,
        "preferences": prefs,
    })
    log_audit(None, "create_student", "student", student_id, {"name": body.name})
    return PortfolioAnalyzeResponse(
        student_id=student_id,
        research_topics=result.research_topics,
        embedding_model_version=result.embedding_model_version,
    )


@router.get("/{student_id}", response_model=StudentProfileResponse)
async def get_student(student_id: str):
    s = student_get(student_id)
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentProfileResponse(
        id=s["id"],
        name=s["name"],
        research_topics=s.get("research_topics") or [],
        embedding_model_version=s.get("embedding_model_version"),
    )
