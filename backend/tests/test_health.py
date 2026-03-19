"""Tests for health and readiness endpoints."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from fastapi import HTTPException

from app.api.routes.health import health, readiness


def test_health_liveness_payload():
    payload = asyncio.run(health())
    assert payload["status"] == "ok"
    assert "environment" in payload


def test_readiness_raises_503_when_db_fails():
    with patch("app.api.routes.health.get_session", side_effect=RuntimeError("db down")):
        try:
            asyncio.run(readiness())
            assert False, "Expected readiness() to raise HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail["status"] == "not_ready"
            assert exc.detail["database"] == "error"
