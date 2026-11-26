import os
import tempfile

import pytest

# Tests never touch the real database (data/app.db): this runs before any app module reads DATABASE_URL.
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="deal-finder-tests-"), "test.db")
os.environ["DATABASE_URL"] = "sqlite:///" + _TEST_DB.replace("\\", "/")
os.environ["SCHEDULER_ENABLED"] = "false"  # no background scans or Telegram polling during tests


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    """Tests do not wait between searches, and behave like a backend that has been up for a while."""
    from app import progress, scheduler

    monkeypatch.setattr(scheduler, "SEARCH_GAP_SECONDS", (0, 0))
    monkeypatch.setattr(progress, "uptime_seconds", lambda: 24 * 3600)
