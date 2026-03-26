from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class SessionRecord:
    session_id: str
    created_at: datetime
    updated_at: datetime
    data: dict[str, Any]

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        return now - self.updated_at > timedelta(seconds=self.data.get("ttl_seconds", 3600))


class SessionManager:
    """Минимальная in-memory реализация SessionManager (для MVP каркаса)."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, SessionRecord] = {}

    def get_or_create(self, session_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        rec = self._sessions.get(session_id)
        if rec is None or rec.is_expired:
            rec = SessionRecord(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                data={"ttl_seconds": self._ttl_seconds, "session_id": session_id, "messages": [], "iteration": 0},
            )
            self._sessions[session_id] = rec
        else:
            rec.updated_at = now
        return rec.data

    def update(self, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        data = self.get_or_create(session_id)
        data.update(patch)
        return data

