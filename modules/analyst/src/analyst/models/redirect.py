from __future__ import annotations

from pydantic import BaseModel, Field


class RedirectApi(BaseModel):
    base_url: str


class RedirectResponse(BaseModel):
    """Ответ клиенту при выборе существующего агента (exact match flow)."""

    agent_name: str
    owner_team: str | None = None
    contact: str | None = None

    api: RedirectApi
    mcp_server_uri: str | None = None
    docs_url: str | None = None

    # Например: OAuth2 / куда обращаться за токеном
    auth_notes: str | None = None

    # В дальнейшем можно расширить подробностями (например id выбранного агента)
    decision: str = Field(default="redirect")

