from pydantic import BaseModel


class MatchItem(BaseModel):
    professor_id: str
    score: float
    opportunity_score: float
    final_rank: float


class MatchListResponse(BaseModel):
    matches: list[MatchItem]
