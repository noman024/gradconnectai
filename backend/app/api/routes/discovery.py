"""Trigger discovery pipeline and ingest professors into store."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.discovery.pipeline import run_university_lab_pipeline
from app.services.store import professor_set, generate_id
from app.services.portfolio.embedding import embed_single, get_embedding_model_version

router = APIRouter()


class DiscoverySeedRequest(BaseModel):
    seed_urls: list[str]
    university_name: str


@router.post("/run")
async def run_discovery(body: DiscoverySeedRequest):
    """Crawl seed URLs, extract professors, embed and store them."""
    raw_list = await run_university_lab_pipeline(body.seed_urls, body.university_name)
    version = get_embedding_model_version()
    for r in raw_list:
        combined = " ".join(r.research_topics) if r.research_topics else r.name + " " + r.university
        embedding = embed_single(combined)
        professor_id = generate_id()
        professor_set(professor_id, {
            "name": r.name,
            "university": r.university,
            "email": r.email,
            "lab_url": r.lab_url,
            "research_topics": r.research_topics,
            "sources": r.sources,
            "embedding": embedding,
            "embedding_model_version": version,
            "last_checked": r.last_checked.isoformat() if r.last_checked else None,
            "active_flag": r.active_flag,
            "opportunity_score": 0.5,
        })
    return {"ingested": len(raw_list)}