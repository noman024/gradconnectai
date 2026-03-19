"""Trigger discovery pipeline and optionally dry-run extraction without writes."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any

from app.core.logging import get_logger
from app.services.discovery.pipeline import run_university_lab_pipeline
from app.services.discovery.query_planner import build_discovery_query_plan
from app.services.discovery.harvester import run_automated_search_harvester
from app.services.discovery.google_search import google_search_collect_links
from app.services.discovery.google_browser_search import google_search_collect_links_browser
from app.services.discovery.linkedin_discovery import discover_linkedin_candidates
from app.services.discovery.browser_use_search import browser_use_collect_linkedin_posts, browser_use_collect_links
from app.services.store import (
    professor_set,
    professor_get_by_name_university,
    generate_id,
    opportunity_create_basic,
    opportunity_create_structured,
    source_document_create,
    extraction_run_create,
    student_get,
)
from app.db.models import OpportunityType
from app.services.portfolio.embedding import embed_single, get_embedding_model_version
from app.core.config import settings

import hashlib

logger = get_logger("discovery.api")
router = APIRouter()


class DiscoverySeedRequest(BaseModel):
    seed_urls: list[str]
    university_name: str
    dry_run: bool = False


class DiscoveryQueryPlanRequest(BaseModel):
    student_id: str | None = None
    cv_text: str | None = None
    preferences: dict | None = None
    research_topics: list[str] | None = None


class GoogleSearchIngestionRequest(BaseModel):
    queries: list[str]
    max_links_per_query: int = 10


class GoogleBrowserSearchIngestionRequest(BaseModel):
    queries: list[str]
    max_links_per_query: int = 10


class LinkedInDiscoveryRequest(BaseModel):
    queries: list[str]
    session_id: str | None = None
    li_at_cookie: str | None = None
    cookie_header: str | None = None
    max_links_per_query: int | None = None
    use_authenticated_browser: bool = True
    posts_only: bool = True
    latest_first: bool = True


class BrowserUseSearchRequest(BaseModel):
    queries: list[str]
    max_links_per_query: int = 30
    time_filter: str = "month"


class DiscoveryHarvestRequest(BaseModel):
    student_id: str | None = None
    cv_text: str | None = None
    preferences: dict | None = None
    research_topics: list[str] | None = None
    use_browser_google: bool = True
    max_queries_per_source: int = 6
    max_links_per_query: int = 10
    top_k: int = 40
    verified_only: bool = False
    linkedin_session_id: str | None = None
    linkedin_li_at_cookie: str | None = None


@router.post("/run")
async def run_discovery(body: DiscoverySeedRequest):
    """Crawl seed URLs, extract professors, embed and store them. Deduplicates by name+university."""
    raw_list = await run_university_lab_pipeline(body.seed_urls, body.university_name)
    if body.dry_run:
        candidates: list[dict[str, Any]] = []
        for r in raw_list:
            candidates.append(
                {
                    "name": r.name,
                    "university": r.university,
                    "email": r.email,
                    "profile_url": r.profile_url,
                    "lab_url": r.lab_url,
                    "lab_focus": r.lab_focus,
                    "research_topics": r.research_topics,
                    "sources": r.sources,
                    "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                    "active_flag": r.active_flag,
                    "opportunity_score": r.opportunity_score,
                    "opportunities": r.opportunities,
                    "opportunity_explanation": r.opportunity_explanation,
                    "evidence": r.evidence or [],
                }
            )
        return {
            "dry_run": True,
            "ingested": 0,
            "would_ingest": len(candidates),
            "candidates": candidates,
        }

    version = get_embedding_model_version()
    ingested = 0
    for r in raw_list:
        # Persist a minimal auditable source_document + extraction_run per ingested record.
        # (We store truncated evidence context via professor_evidence; full page storage can be added later.)
        url = r.lab_url or (r.sources[0] if r.sources else "")
        content_hash = hashlib.sha256((url or "").encode("utf-8")).hexdigest() if url else None
        source_document_id = None
        extraction_run_id = None
        try:
            if url:
                source_document_id = source_document_create(
                    url=url,
                    status_code=200,
                    robots_allowed=True,
                    content_type="text/markdown",
                    content_hash=content_hash,
                    content_text=None,
                )
                extraction_run_id = extraction_run_create(
                    source_document_id=source_document_id,
                    extractor="qwen_professor_extract",
                    llm_model=settings.LLM_MODEL,
                    prompt_version="v1",
                    success=True,
                )
        except Exception:
            # Evidence persistence failures should not block ingestion in MVP.
            source_document_id = None
            extraction_run_id = None

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
                "opportunities": r.opportunities,
                "opportunity_explanation": r.opportunity_explanation,
            },
            evidence=(r.evidence or []),
            source_document_id=source_document_id,
            extraction_run_id=extraction_run_id,
        )
        # Persist structured opportunities when extracted; fallback to one generic row.
        try:
            created = opportunity_create_structured(
                professor_id=professor_id,
                opportunities=r.opportunities or [],
                default_source=(r.sources[0] if r.sources else None),
            )
            if created <= 0:
                opportunity_create_basic(
                    professor_id=professor_id,
                    opp_type=OpportunityType.phd,
                    source=(r.sources[0] if r.sources else None),
                )
        except Exception:
            # Discovery should not fail just because opportunity persistence failed.
            pass
        ingested += 1
    return {"dry_run": False, "ingested": ingested}


@router.post("/query-plan")
async def discovery_query_plan(body: DiscoveryQueryPlanRequest):
    """
    Build discovery search queries from student profile signal.
    Accepts explicit topics/preferences and can also read by student_id.
    """
    topics: list[str] = list(body.research_topics or [])
    prefs: dict[str, Any] = dict(body.preferences or {})

    if body.student_id:
        student = student_get(body.student_id)
        if student:
            topics = topics + list(student.get("research_topics") or [])
            # Explicit request preferences win, but we merge missing keys from student.
            sp = student.get("preferences") or {}
            if isinstance(sp, dict):
                merged = dict(sp)
                merged.update(prefs)
                prefs = merged

    if body.cv_text and not topics:
        # Lightweight fallback: create coarse topics from CV tokens if caller didn't provide extracted topics.
        cv_tokens = [w for w in body.cv_text.replace("\n", " ").split(" ") if len(w) > 4]
        topics = cv_tokens[:20]

    plan = build_discovery_query_plan(research_topics=topics, preferences=prefs)
    return {
        "student_id": body.student_id,
        "query_plan": plan,
    }


@router.post("/google-search")
async def discovery_google_search(body: GoogleSearchIngestionRequest):
    """
    Collect and score top links from Google search queries.
    """
    logger.info("google_search_request", queries=body.queries, max_links=body.max_links_per_query)
    result = await google_search_collect_links(
        body.queries,
        max_links_per_query=body.max_links_per_query,
    )
    logger.info("google_search_done", total_deduped=result.get("total_deduped", 0))
    return result


@router.post("/google-search-browser")
async def discovery_google_search_browser(body: GoogleBrowserSearchIngestionRequest):
    """
    Collect and score top links from Google search using a real browser session.
    """
    logger.info("google_browser_search_request", queries=body.queries, max_links=body.max_links_per_query)
    result = await google_search_collect_links_browser(
        body.queries,
        max_links_per_query=body.max_links_per_query,
    )
    logger.info("google_browser_search_done", total_deduped=result.get("total_deduped", 0), fallback=result.get("fallback_used"))
    return result


@router.post("/linkedin-discovery")
async def discovery_linkedin(body: LinkedInDiscoveryRequest):
    """
    Discover LinkedIn profile/post URLs with session tracking and recency weighting.
    """
    logger.info("linkedin_discovery_request", queries=body.queries, posts_only=body.posts_only, auth_browser=body.use_authenticated_browser)
    result = await discover_linkedin_candidates(
        queries=body.queries,
        session_id=body.session_id,
        li_at_cookie=body.li_at_cookie,
        cookie_header=body.cookie_header,
        max_links_per_query=body.max_links_per_query,
        use_authenticated_browser=body.use_authenticated_browser,
        posts_only=body.posts_only,
        latest_first=body.latest_first,
    )
    logger.info("linkedin_discovery_done", total_ranked=result.get("total_ranked", 0))
    return result


@router.post("/browser-use-search")
async def discovery_browser_use_search(body: BrowserUseSearchRequest):
    """
    AI-driven browser search using browser-use + Ollama.
    Mimics human search behaviour to find recent LinkedIn posts.
    """
    logger.info("browser_use_linkedin_request", queries=body.queries, time_filter=body.time_filter)
    result = await browser_use_collect_linkedin_posts(
        body.queries,
        max_links_per_query=body.max_links_per_query,
        time_filter=body.time_filter,
    )
    logger.info("browser_use_linkedin_done", total=result.get("total", 0), errors=result.get("errors"))
    return result


class BrowserUseGeneralSearchRequest(BaseModel):
    queries: list[str]
    max_links_per_query: int = 20
    time_filter: str = "month"


@router.post("/browser-use-general")
async def discovery_browser_use_general(body: BrowserUseGeneralSearchRequest):
    """
    AI-driven general web search using browser-use + Ollama + DuckDuckGo.
    Returns all result links (not just LinkedIn).
    """
    logger.info("browser_use_general_request", queries=body.queries, time_filter=body.time_filter)
    result = await browser_use_collect_links(
        body.queries,
        max_links_per_query=body.max_links_per_query,
        time_filter=body.time_filter,
    )
    logger.info("browser_use_general_done", total_deduped=result.get("total_deduped", 0), errors=result.get("errors"))
    return result


@router.post("/harvest")
async def discovery_harvest(body: DiscoveryHarvestRequest):
    """
    End-to-end automated search harvester:
    query planning -> Google/LinkedIn collection -> dedupe -> ranked seed URLs.
    """
    topics: list[str] = list(body.research_topics or [])
    prefs: dict[str, Any] = dict(body.preferences or {})

    if body.student_id:
        student = student_get(body.student_id)
        if student:
            topics = topics + list(student.get("research_topics") or [])
            sp = student.get("preferences") or {}
            if isinstance(sp, dict):
                merged = dict(sp)
                merged.update(prefs)
                prefs = merged
    if body.cv_text and not topics:
        tokens = [w for w in body.cv_text.replace("\n", " ").split(" ") if len(w) > 4]
        topics = tokens[:20]

    logger.info("harvest_request", topics=topics[:5], use_browser=body.use_browser_google, top_k=body.top_k)
    harvest = await run_automated_search_harvester(
        research_topics=topics,
        preferences=prefs,
        use_browser_google=body.use_browser_google,
        max_queries_per_source=body.max_queries_per_source,
        max_links_per_query=body.max_links_per_query,
        top_k=body.top_k,
        verified_only=body.verified_only,
        linkedin_session_id=body.linkedin_session_id,
        linkedin_li_at_cookie=body.linkedin_li_at_cookie,
    )
    logger.info("harvest_done", total_seed_urls=harvest.get("total_seed_urls", 0), sources=harvest.get("sources"))
    return {
        "student_id": body.student_id,
        **harvest,
    }