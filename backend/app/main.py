"""
GradConnectAI API Gateway — FastAPI application.
"""
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from structlog import contextvars as struct_contextvars

from app.api import router as api_router
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.rate_limit import limiter
from app.services.portfolio.embedding import preload_embedding_model
from app.services.llm_client import extract_topics_from_cv


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # Warm up heavy resources (embedding model, LLM, etc.)
    preload_embedding_model()
    try:
        # Fire a small LLM warmup call so the first user request doesn't pay model load cost.
        extract_topics_from_cv(
            cv_text="Short CV snippet about machine learning and NLP.",
            preference_fields=["machine learning", "NLP"],
        )
    except Exception:
        # LLM warmup failures should not prevent app startup.
        pass
    yield
    # Shutdown: close DB pools, etc.


app = FastAPI(
    title="GradConnectAI API",
    description="AI-driven supervisor discovery and matching for graduate students",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Bind a request_id and basic request info into the log context for each request."""
    request_id = str(uuid4())
    struct_contextvars.clear_contextvars()
    struct_contextvars.bind_contextvars(
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
    )
    logger = get_logger("http")
    logger.info("request_start")
    try:
        response = await call_next(request)
        logger.info("request_end", status_code=response.status_code)
        return response
    finally:
        # Avoid context leaking across requests
        struct_contextvars.clear_contextvars()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
