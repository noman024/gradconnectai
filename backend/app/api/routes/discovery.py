"""Trigger discovery pipeline and ingest professors into store."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.discovery.pipeline import run_university_lab_pipeline
from app.services.store import (
    professor_set,
    professor_get_by_name_university,
    generate_id,
    opportunity_create_basic,
)
from app.db.models import OpportunityType
from app.services.portfolio.embedding import embed_single, get_embedding_model_version

router = APIRouter()


class DiscoverySeedRequest(BaseModel):
    seed_urls: list[str]
    university_name: str


@router.post("/run")
async def run_discovery(body: DiscoverySeedRequest):
    """Crawl seed URLs, extract professors, embed and store them. Deduplicates by name+university."""
    raw_list = await run_university_lab_pipeline(body.seed_urls, body.university_name)
    version = get_embedding_model_version()
    ingested = 0
    for r in raw_list:
        existing = professor_get_by_name_university(r.name, r.university)
        professor_id = existing["id"] if existing else generate_id()
        combined = " ".join(r.research_topics) if r.research_topics else r.name + " " + r.university
        embedding = embed_single(combined)
        professor_set(
            professor_id,
            {
                "name": r.name,
                "university": r.university,
                "email": r.email,
                "lab_url": r.lab_url,
                "lab_focus": r.lab_focus,
                "research_topics": r.research_topics,
                "sources": r.sources,
                "embedding": embedding,
                "embedding_model_version": version,
                "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                "active_flag": r.active_flag,
                "opportunity_score": r.opportunity_score,
            },
        )
        # For now, record a single generic opportunity per discovered professor,
        # using their opportunity_score as a hint that something is open.
        try:
            opportunity_create_basic(
                professor_id=professor_id,
                opp_type=OpportunityType.phd,
                source=(r.sources[0] if r.sources else None),
            )
        except Exception:
            # Discovery should not fail just because opportunity persistence failed.
            pass
        ingested += 1
    return {"ingested": ingested}