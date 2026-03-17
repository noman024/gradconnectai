from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field

# Documented shape for preferences (plan)
# { "countries": [], "universities": [], "fields": [] }
class StudentPreferences(BaseModel):
    countries: list = Field(default_factory=list, description="Preferred countries")
    universities: list = Field(default_factory=list, description="Preferred universities")
    fields: list = Field(default_factory=list, description="Research fields")


class StudentCreate(BaseModel):
    name: str
    cv_text: str = ""
    preferences: Union[StudentPreferences, dict] = Field(default_factory=dict)


class StudentProfileResponse(BaseModel):
    id: str
    name: str
    research_topics: list = Field(default_factory=list)
    embedding_model_version: Union[str, None] = None


class PortfolioAnalyzeResponse(BaseModel):
    student_id: str
    research_topics: list[str]
    embedding_model_version: str
