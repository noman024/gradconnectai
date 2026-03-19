"""Shared test fixtures for GradConnectAI backend tests."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_student_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_professor_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_student_data() -> dict:
    return {
        "name": "Alice Researcher",
        "research_topics": ["machine learning", "natural language processing", "computer vision"],
        "embedding": [0.1] * 384,
        "embedding_model_version": "all-MiniLM-L6-v2-v1",
        "cv_file": None,
        "experience_snippet": "Experienced in NLP and deep learning with 2 years of research.",
        "preferences": {
            "countries": ["USA", "UK"],
            "universities": [],
            "fields": ["AI"],
            "degree_targets": ["phd"],
        },
    }


@pytest.fixture
def sample_professor_data() -> dict:
    return {
        "name": "Dr. Bob Smith",
        "university": "MIT",
        "country": "USA",
        "region": "North America",
        "email": "bob.smith@mit.edu",
        "research_topics": ["deep learning", "reinforcement learning"],
        "lab_url": "https://mit.edu/bob-lab",
        "lab_focus": "Deep reinforcement learning for robotics",
        "opportunity_score": 0.8,
        "embedding": [0.2] * 384,
        "embedding_model_version": "all-MiniLM-L6-v2-v1",
        "last_checked": None,
        "active_flag": True,
        "sources": ["https://mit.edu/bob-lab"],
    }


@pytest.fixture
def mock_db_session():
    """Return a mock database session for unit tests that don't need real DB."""
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session
