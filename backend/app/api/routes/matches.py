from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.schemas.matches import MatchItem, MatchListResponse
from app.services.store import student_get, professors_list, professor_get, matches_for_student, matches_upsert
from app.services.matching.engine import rank_matches, MatchResult

router = APIRouter()
logger = get_logger("matches_api")


def _compute_and_store_matches(student_id: str) -> list[MatchResult]:
    student = student_get(student_id)
    if not student:
        logger.info("matches_student_missing", student_id=student_id)
        return []
    professors = professors_list()
    if not professors:
        logger.info("matches_no_professors", student_id=student_id)
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
    logger.info(
        "matches_computed",
        student_id=student_id,
        total_professors=len(professors),
        total_results=len(results),
    )
    return results


def _enrich_matches(matches: list) -> list[MatchItem]:
    """Enrich match list with professor details."""
    out = []
    for m in matches:
        prof = professor_get(m["professor_id"])
        out.append(
            MatchItem(
                professor_id=m["professor_id"],
                professor_name=prof.get("name") if prof else None,
                university=prof.get("university") if prof else None,
                lab_focus=prof.get("lab_focus") if prof else None,
                score=m["score"],
                opportunity_score=m["opportunity_score"],
                final_rank=m["final_rank"],
            )
        )
    return out


@router.get("", response_model=MatchListResponse)
async def list_matches(student_id: str):
    """Return ranked matches for a student with professor details. Recomputes if needed."""
    if not student_id:
        raise HTTPException(status_code=400, detail="student_id is required")
    student = student_get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    existing = matches_for_student(student_id)
    student_emb = student.get("embedding")
    has_embedding = student_emb is not None and len(student_emb) > 0
    profs = professors_list()
    if not existing and has_embedding and len(profs) > 0:
        results = _compute_and_store_matches(student_id)
        logger.info("matches_returned", student_id=student_id, count=len(results), from_cache=False)
        raw = [{"professor_id": r.professor_id, "score": r.score, "opportunity_score": r.opportunity_score, "final_rank": r.final_rank} for r in results]
        return MatchListResponse(matches=_enrich_matches(raw))
    logger.info("matches_returned", student_id=student_id, count=len(existing), from_cache=True)
    return MatchListResponse(matches=_enrich_matches(existing))
