from fastapi import APIRouter, HTTPException

from app.schemas.matches import MatchItem, MatchListResponse
from app.services.store import student_get, professors_list, matches_for_student, matches_upsert
from app.services.matching.engine import rank_matches, MatchResult

router = APIRouter()


def _compute_and_store_matches(student_id: str) -> list[MatchResult]:
    student = student_get(student_id)
    if not student:
        return []
    professors = professors_list()
    if not professors:
        return []
    student_emb = student.get("embedding")
    prof_tuples = [
        (
            p["id"],
            p.get("embedding"),
            float(p.get("opportunity_score") or 0.0),
        )
        for p in professors
    ]
    results = rank_matches(student_emb, prof_tuples)
    for r in results:
        matches_upsert(student_id, r.professor_id, r.score, r.opportunity_score, r.final_rank)
    return results


@router.get("", response_model=MatchListResponse)
async def list_matches(student_id: str):
    """Return ranked matches for a student. Recomputes if professors exist and student has embedding."""
    student = student_get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    existing = matches_for_student(student_id)
    if not existing and student.get("embedding") and professors_list():
        results = _compute_and_store_matches(student_id)
        return MatchListResponse(matches=[MatchItem(professor_id=r.professor_id, score=r.score, opportunity_score=r.opportunity_score, final_rank=r.final_rank) for r in results])
    return MatchListResponse(
        matches=[MatchItem(professor_id=m["professor_id"], score=m["score"], opportunity_score=m["opportunity_score"], final_rank=m["final_rank"]) for m in existing]
    )
