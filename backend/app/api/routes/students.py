from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request

from app.schemas.students import StudentCreate, StudentProfileResponse, PortfolioAnalyzeResponse
from app.core.validation import validate_name, validate_cv_text, validate_preferences, MAX_CV_FILE_SIZE_BYTES
from app.core.audit import log_audit
from app.services.portfolio.analyzer import analyze_portfolio
from app.services.portfolio.pdf_extractor import extract_text_from_pdf_stream
from app.services.store import student_set, student_get, generate_id
from app.core.rate_limit import limiter
from app.core.config import settings

router = APIRouter()


@router.post("", response_model=PortfolioAnalyzeResponse)
@limiter.limit("30/minute")
async def create_student_and_analyze(request: Request, body: StudentCreate):
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
    snippet = (body.cv_text or "")[:400].strip() if body.cv_text else None
    student_set(student_id, {
        "name": body.name,
        "research_topics": result.research_topics,
        "embedding": result.embedding,
        "embedding_model_version": result.embedding_model_version,
        "experience_snippet": snippet,
        "preferences": prefs,
    })
    log_audit(None, "create_student", "student", student_id, {"name": body.name})
    return PortfolioAnalyzeResponse(
        student_id=student_id,
        research_topics=result.research_topics,
        embedding_model_version=result.embedding_model_version,
    )


@router.post("/upload", response_model=PortfolioAnalyzeResponse)
@limiter.limit(f"{settings.API_RATE_LIMIT_UPLOAD_PER_MINUTE}/minute")
async def upload_cv_and_analyze(
    request: Request,
    name: str = Form(...),
    preferences_json: str = Form("{}"),
    file: UploadFile = File(...),
):
    """Accept a PDF CV upload, extract text, and run portfolio analysis."""
    err = validate_name(name)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > MAX_CV_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_CV_FILE_SIZE_BYTES // (1024*1024)} MB",
        )
    try:
        import json

        prefs = json.loads(preferences_json or "{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid preferences_json")
    err = validate_preferences(prefs)
    if err:
        raise HTTPException(status_code=400, detail=err)

    from io import BytesIO

    cv_text = extract_text_from_pdf_stream(BytesIO(content))
    err = validate_cv_text(cv_text)
    if err:
        raise HTTPException(status_code=400, detail=err)

    result = analyze_portfolio(cv_text=cv_text, preferences=prefs)
    student_id = generate_id()
    snippet = cv_text[:400].strip() if cv_text else None
    student_set(
        student_id,
        {
            "name": name,
            "research_topics": result.research_topics,
            "embedding": result.embedding,
            "embedding_model_version": result.embedding_model_version,
            "experience_snippet": snippet,
            "preferences": prefs,
            "cv_file": file.filename,
        },
    )
    log_audit(None, "create_student_upload", "student", student_id, {"name": name, "cv_file": file.filename})
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
