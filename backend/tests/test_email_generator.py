"""Tests for email generation: topic sanitization, fallback, and post-processing."""
import pytest
from unittest.mock import patch

from app.services.email_gen.generator import (
    _sanitize_topics,
    _fallback_body,
    generate_draft,
    EmailDraft,
)


class TestSanitizeTopics:
    def test_normal_topics(self):
        topics = ["machine learning", "natural language processing", "computer vision"]
        result = _sanitize_topics(topics)
        assert result == topics

    def test_filters_noise_words(self):
        topics = ["email", "phone", "deep learning"]
        result = _sanitize_topics(topics)
        assert result == ["deep learning"]

    def test_filters_single_names(self):
        topics = ["Mutasim", "Billah", "reinforcement learning"]
        result = _sanitize_topics(topics)
        assert result == ["reinforcement learning"]

    def test_filters_short_tokens(self):
        topics = ["AI", "ab", "deep learning"]
        result = _sanitize_topics(topics)
        assert result == ["deep learning"]

    def test_keeps_3_char_tokens(self):
        topics = ["NLP", "deep learning"]
        result = _sanitize_topics(topics)
        assert result == ["NLP", "deep learning"]

    def test_caps_at_12(self):
        topics = [f"topic_{i}" for i in range(20)]
        result = _sanitize_topics(topics)
        assert len(result) == 12

    def test_empty_input(self):
        assert _sanitize_topics([]) == []

    def test_strips_whitespace(self):
        topics = ["  machine learning  ", " robotics "]
        result = _sanitize_topics(topics)
        assert result == ["machine learning", "robotics"]

    def test_skips_non_strings(self):
        topics = [None, 123, "deep learning"]
        result = _sanitize_topics(topics)
        assert result == ["deep learning"]


class TestFallbackBody:
    def test_contains_student_and_professor(self):
        body = _fallback_body("Alice", "Dr. Bob Smith", "MIT", "machine learning, NLP")
        assert "Alice" in body
        assert "Smith" in body
        assert "MIT" in body
        assert "machine learning" in body

    def test_starts_with_salutation(self):
        body = _fallback_body("Alice", "Dr. Bob Smith", "MIT", "research")
        assert body.startswith("Dear Professor")


class TestGenerateDraft:
    def test_llm_success(self, monkeypatch):
        email_body = "Dear Professor Smith,\n\nI am writing to express my interest.\n\nBest regards,\nAlice"
        monkeypatch.setattr(
            "app.services.email_gen.generator._call_llm",
            lambda prompt: email_body,
        )
        draft = generate_draft(
            student_name="Alice",
            student_research_topics=["machine learning"],
            student_experience_snippet="2 years of ML research",
            professor_name="Dr. Bob Smith",
            professor_university="MIT",
            professor_lab_focus="Deep learning",
        )
        assert isinstance(draft, EmailDraft)
        assert "Alice" in draft.subject
        assert "Dear Professor" in draft.body

    def test_llm_empty_triggers_fallback(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.email_gen.generator._call_llm",
            lambda prompt: "",
        )
        draft = generate_draft(
            student_name="Alice",
            student_research_topics=["machine learning"],
            student_experience_snippet="",
            professor_name="Dr. Bob Smith",
            professor_university="MIT",
            professor_lab_focus="Deep learning",
        )
        assert "Dear Professor Smith" in draft.body

    def test_meta_reasoning_stripped(self, monkeypatch):
        body_with_meta = "Let me think about this...\nDear Professor Smith,\n\nI am interested.\n\nBest,\nAlice"
        monkeypatch.setattr(
            "app.services.email_gen.generator._call_llm",
            lambda prompt: body_with_meta,
        )
        draft = generate_draft(
            student_name="Alice",
            student_research_topics=["machine learning"],
            student_experience_snippet="",
            professor_name="Dr. Bob Smith",
            professor_university="MIT",
            professor_lab_focus="Deep learning",
        )
        assert "Let me think" not in draft.body
        assert draft.body.startswith("Dear Professor")
