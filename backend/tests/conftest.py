import pytest


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    """Tests do not wait between searches, and behave like a backend that has been up for a while."""
    from app import progress, scheduler

    monkeypatch.setattr(scheduler, "SEARCH_GAP_SECONDS", (0, 0))
    monkeypatch.setattr(progress, "uptime_seconds", lambda: 24 * 3600)
