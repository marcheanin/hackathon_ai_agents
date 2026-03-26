from __future__ import annotations

from analyst.session import SessionManager


def test_session_manager_creates_session_with_session_id() -> None:
    sm = SessionManager(ttl_seconds=3600)
    s = sm.get_or_create("sess_test_1")
    assert s["session_id"] == "sess_test_1"
    assert s["iteration"] == 0
    assert isinstance(s["messages"], list)

