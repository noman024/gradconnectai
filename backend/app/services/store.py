"""
In-memory store for MVP when DB is not connected. Replace with DB repository in production.
Maps student_id -> { name, research_topics, embedding, preferences, ... }
Maps professor_id -> { name, university, embedding, opportunity_score, lab_url, ... }
"""
from __future__ import annotations

import uuid
from typing import Any

_students: dict[str, dict[str, Any]] = {}
_professors: dict[str, dict[str, Any]] = {}
_matches: list[dict[str, Any]] = []


def student_set(student_id: str, data: dict[str, Any]) -> None:
    _students[student_id] = {**data, "id": student_id}


def student_get(student_id: str) -> dict[str, Any] | None:
    return _students.get(student_id)


def professor_set(professor_id: str, data: dict[str, Any]) -> None:
    _professors[professor_id] = {**data, "id": professor_id}


def professor_get(professor_id: str) -> dict[str, Any] | None:
    return _professors.get(professor_id)


def professors_list() -> list[dict[str, Any]]:
    return list(_professors.values())


def matches_upsert(student_id: str, professor_id: str, score: float, opportunity_score: float, final_rank: float) -> None:
    global _matches
    _matches = [m for m in _matches if not (m["student_id"] == student_id and m["professor_id"] == professor_id)]
    _matches.append({
        "student_id": student_id,
        "professor_id": professor_id,
        "score": score,
        "opportunity_score": opportunity_score,
        "final_rank": final_rank,
    })


def matches_for_student(student_id: str) -> list[dict[str, Any]]:
    return sorted(
        [m for m in _matches if m["student_id"] == student_id],
        key=lambda x: x["final_rank"],
        reverse=True,
    )


def generate_id() -> str:
    return str(uuid.uuid4())


def student_delete(student_id: str) -> bool:
    """Remove student and their matches. Returns True if existed."""
    if student_id not in _students:
        return False
    del _students[student_id]
    global _matches
    _matches = [m for m in _matches if m["student_id"] != student_id]
    return True


def student_export(student_id: str) -> dict[str, Any] | None:
    """Export all data we hold for this student (GDPR)."""
    s = _students.get(student_id)
    if not s:
        return None
    out = {k: v for k, v in s.items() if k != "embedding"}  # optional: include embedding for portability
    out["matches"] = matches_for_student(student_id)
    return out
