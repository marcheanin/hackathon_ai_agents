from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SnippetSummary(BaseModel):
    id: str
    name: str | None = None
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    domain: str | None = None
    stack: list[str] = Field(default_factory=list)

    # Простые значения из примера (дальше можно расширять)
    complexity: Literal["low", "medium", "high"] | str | None = None
    files_count: int | None = None

