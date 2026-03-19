"""Tests for input validation helpers."""
import uuid

from app.core.validation import (
    validate_name,
    validate_cv_text,
    validate_preferences,
    validate_uuid,
    MAX_NAME_LENGTH,
    MAX_CV_TEXT_LENGTH,
    MAX_PREFERENCES_FIELDS,
)


class TestValidateName:
    def test_valid_name(self):
        assert validate_name("Alice Researcher") is None

    def test_valid_name_with_special_chars(self):
        assert validate_name("O'Brien-Smith") is None

    def test_empty_name(self):
        assert validate_name("") is not None

    def test_none_name(self):
        assert validate_name(None) is not None

    def test_too_long(self):
        assert validate_name("A" * (MAX_NAME_LENGTH + 1)) is not None

    def test_invalid_characters(self):
        assert validate_name("Alice<script>") is not None

    def test_whitespace_only(self):
        result = validate_name("   ")
        assert result is not None


class TestValidateCvText:
    def test_valid_cv(self):
        assert validate_cv_text("My research experience includes...") is None

    def test_too_long(self):
        assert validate_cv_text("x" * (MAX_CV_TEXT_LENGTH + 1)) is not None

    def test_not_string(self):
        assert validate_cv_text(123) is not None

    def test_empty_string(self):
        assert validate_cv_text("") is None


class TestValidatePreferences:
    def test_valid_preferences(self):
        prefs = {
            "countries": ["USA", "UK"],
            "universities": ["MIT"],
            "fields": ["AI"],
            "degree_targets": ["phd"],
        }
        assert validate_preferences(prefs) is None

    def test_empty_dict(self):
        assert validate_preferences({}) is None

    def test_not_dict(self):
        assert validate_preferences("string") is not None

    def test_countries_not_list(self):
        assert validate_preferences({"countries": "USA"}) is not None

    def test_too_many_items(self):
        prefs = {"countries": ["C"] * (MAX_PREFERENCES_FIELDS + 1)}
        assert validate_preferences(prefs) is not None

    def test_item_too_long(self):
        prefs = {"countries": ["A" * 200]}
        assert validate_preferences(prefs) is not None

    def test_non_string_item(self):
        prefs = {"countries": [123]}
        assert validate_preferences(prefs) is not None


class TestValidateUuid:
    def test_valid_uuid(self):
        assert validate_uuid(str(uuid.uuid4())) is None

    def test_invalid_format(self):
        assert validate_uuid("not-a-uuid") is not None

    def test_empty(self):
        assert validate_uuid("") is not None

    def test_none(self):
        assert validate_uuid(None) is not None
