"""
Input validation: file uploads (type, size), text inputs, preferences.
"""
from __future__ import annotations

import re

from app.core.config import settings

# Max lengths and sizes
MAX_CV_TEXT_LENGTH = 100_000
MAX_NAME_LENGTH = 200
MAX_PREFERENCES_FIELDS = 50
MAX_PREFERENCE_ITEM_LENGTH = 100
MAX_CV_FILE_SIZE_BYTES = settings.MAX_CV_FILE_SIZE_MB * 1024 * 1024


def validate_name(name: str) -> str | None:
    if not name or not isinstance(name, str):
        return "Name is required"
    name = name.strip()
    if len(name) > MAX_NAME_LENGTH:
        return f"Name must be at most {MAX_NAME_LENGTH} characters"
    if not re.match(r"^[\w\s\-.']+$", name):
        return "Name contains invalid characters"
    return None


def validate_cv_text(cv_text: str) -> str | None:
    if not isinstance(cv_text, str):
        return "CV text must be a string"
    if len(cv_text) > MAX_CV_TEXT_LENGTH:
        return f"CV text must be at most {MAX_CV_TEXT_LENGTH} characters"
    return None


def validate_preferences(preferences: dict) -> str | None:
    if not isinstance(preferences, dict):
        return "Preferences must be an object"
    for key in ("countries", "universities", "fields", "degree_targets"):
        if key in preferences and not isinstance(preferences[key], list):
            return f"preferences.{key} must be an array"
        if key in preferences:
            arr = preferences[key]
            if len(arr) > MAX_PREFERENCES_FIELDS:
                return f"preferences.{key} must have at most {MAX_PREFERENCES_FIELDS} items"
            for item in arr:
                if not isinstance(item, str) or len(item) > MAX_PREFERENCE_ITEM_LENGTH:
                    return f"Each item in preferences.{key} must be a string of at most {MAX_PREFERENCE_ITEM_LENGTH} characters"
    return None


def validate_uuid(value: str) -> str | None:
    if not value or not isinstance(value, str):
        return "ID is required"
    uuid_pattern = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    if not uuid_pattern.match(value.strip()):
        return "Invalid ID format"
    return None
