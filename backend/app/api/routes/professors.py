from fastapi import APIRouter, HTTPException

from app.services.store import professor_get, professor_set, professors_list, generate_id
from app.services.portfolio.embedding import embed_single, get_embedding_model_version

router = APIRouter()


@router.get("")
async def list_professors():
    return {"professors": professors_list()}


@router.get("/{professor_id}")
async def get_professor(professor_id: str):
    p = professor_get(professor_id)
    if not p:
        raise HTTPException(status_code=404, detail="Professor not found")
    return p
