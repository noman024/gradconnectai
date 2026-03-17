from fastapi import APIRouter, HTTPException

from app.schemas.email_drafts import EmailDraftGenerateRequest, EmailDraftResponse
from app.services.store import student_get, professor_get
from app.services.email_gen.generator import generate_draft

router = APIRouter()


@router.post("/generate", response_model=EmailDraftResponse)
async def generate_email_draft(body: EmailDraftGenerateRequest):
    student = student_get(body.student_id)
    professor = professor_get(body.professor_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if not professor:
        raise HTTPException(status_code=404, detail="Professor not found")
    draft = generate_draft(
        student_name=student["name"],
        student_research_topics=student.get("research_topics") or [],
        student_experience_snippet="",  # could come from CV summary
        professor_name=professor["name"],
        professor_university=professor.get("university") or "",
        professor_lab_focus=professor.get("lab_url") or "research",
        professor_recent_paper_or_topic=professor.get("research_topics", []) and str(professor["research_topics"][:2]) or None,
    )
    return EmailDraftResponse(subject=draft.subject, body=draft.body)
