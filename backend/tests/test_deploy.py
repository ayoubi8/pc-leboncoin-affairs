from __future__ import annotations

from fastapi.testclient import TestClient

from app import config, main
from app.api import cron


def _client(monkeypatch, password="", cron_secret=""):
    monkeypatch.setattr(config, "APP_PASSWORD", password)
    monkeypatch.setattr(config, "CRON_SECRET", cron_secret)
    return TestClient(main.app)  # no `with`: skip lifespan (db + scheduler)


def test_no_password_means_open_api(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/api/auth/me").json() == {"auth_required": False, "authenticated": True}


def test_password_blocks_api_until_login(monkeypatch):
    client = _client(monkeypatch, password="s3cret")
    assert client.get("/api/health").status_code == 200  # health stays open
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    assert client.get("/api/settings").status_code == 401
    assert client.post("/api/auth/login", json={"password": "s3cret"}).status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True
    assert client.get("/api/settings").status_code != 401
    client.post("/api/auth/logout")
    assert client.get("/api/settings").status_code == 401


def test_cron_requires_secret(monkeypatch):
    client = _client(monkeypatch, password="s3cret", cron_secret="")
    assert client.get("/api/cron/tick").status_code == 503  # not configured, even though cron skips the login
    client = _client(monkeypatch, password="s3cret", cron_secret="abc")
    assert client.get("/api/cron/tick").status_code == 401
    assert client.get("/api/cron/tick", headers={"Authorization": "Bearer wrong"}).status_code == 401
    monkeypatch.setattr(cron, "check_due_searches", lambda budget_seconds=None: {"ran": [3], "budget": budget_seconds})
    response = client.get("/api/cron/tick", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 200 and response.json()["ran"] == [3]


def test_postgres_urls_are_normalized():
    assert config._normalize_db_url("postgres://u:p@h:6543/db") == "postgresql+psycopg://u:p@h:6543/db"
    assert config._normalize_db_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert config._normalize_db_url("sqlite:///x.db") == "sqlite:///x.db"
