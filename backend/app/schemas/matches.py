from pydantic import BaseModel


class MatchItem(BaseModel):
    professor_id: str
    professor_name: str | None = None
    university: str | None = None
    lab_focus: str | None = None
    score: float
    opportunity_score: float
    final_rank: float


class MatchListResponse(BaseModel):
    matches: list[MatchItem]
