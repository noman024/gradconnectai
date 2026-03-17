"""API router aggregating all route modules."""
from fastapi import APIRouter

from app.api.routes import health, students, professors, matches, email_drafts, gdpr, discovery, admin

router = APIRouter()

router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(students.router, prefix="/students", tags=["students"])
router.include_router(professors.router, prefix="/professors", tags=["professors"])
router.include_router(matches.router, prefix="/matches", tags=["matches"])
router.include_router(email_drafts.router, prefix="/email-drafts", tags=["email-drafts"])
router.include_router(gdpr.router, prefix="/gdpr", tags=["gdpr"])
router.include_router(discovery.router, prefix="/discovery", tags=["discovery"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
