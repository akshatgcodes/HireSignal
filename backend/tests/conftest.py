import json
import os
import tempfile
from pathlib import Path

# Settings are read at import time, so point them at a throwaway DB before importing the app.
# TEST_DATABASE_URL runs the suite on Postgres instead (CI does), which enforces column sizes
_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_db.name}"
os.environ["APP_PASSWORD"] = "test-pass"
os.environ["REDIS_URL"] = ""
os.environ["CELERY_ALWAYS_EAGER"] = "true"
os.environ["HOST_INTERVAL"] = "0"
os.environ["LLM_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["DIGEST_TO"] = ""

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import http as app_http  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def fixture_json(name: str):
    return json.loads(fixture(name))


class FakeWeb:
    """A tiny internet for httpx.MockTransport: (host, path) → response, plus a log."""

    def __init__(self):
        self.routes: dict[tuple[str, str], list] = {}
        self.requests: list[httpx.Request] = []

    def add(self, url: str, body="", status: int = 200, headers: dict | None = None):
        u = httpx.URL(url)
        if not isinstance(body, str):
            body = json.dumps(body)
        self.routes.setdefault((u.host, u.path), []).append((status, body, headers or {}))
        return self

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self.routes.get((request.url.host, request.url.path))
        if not queue:
            return httpx.Response(404, text="not found")
        # Each registered response is served once, the last one forever
        status, body, headers = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx.Response(status, text=body, headers=headers)

    def fetcher(self, **kw) -> app_http.Fetcher:
        kw.setdefault("spacing", app_http.HostSpacing(0))
        kw.setdefault("backoff", 0)
        return app_http.Fetcher(transport=httpx.MockTransport(self.handler), **kw)

    def hosts(self) -> list[str]:
        return [r.url.host for r in self.requests]


class FakeChat:
    """Stands in for the LangChain chat model: returns canned replies, records prompts."""

    def __init__(self, *replies: str, error: Exception | None = None):
        self.replies = list(replies)
        self.error = error
        self.calls: list = []

    def invoke(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error

        class Reply:
            content = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

        return Reply()


GH_DEPTS = "https://boards-api.greenhouse.io/v1/boards/stripe/departments"
LEVER = "https://api.lever.co/v0/postings/palantir"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/openai"
GNEWS = "https://news.google.com/rss/search"
HN = "https://hn.algolia.com/api/v1/search_by_date"


@pytest.fixture
def web(monkeypatch):
    w = FakeWeb()
    w.add(GH_DEPTS, fixture("greenhouse_departments.json"))
    w.add(LEVER, fixture("lever_postings.json"))
    w.add(ASHBY, fixture("ashby_board.json"))
    w.add(GNEWS, fixture("google_news.xml"), headers={"content-type": "application/rss+xml"})
    w.add(HN, fixture("hn_search.json"))
    # Code that builds its own Fetcher gets one wired to the fake web
    monkeypatch.setattr("app.pipeline.Fetcher", w.fetcher)
    monkeypatch.setattr("app.routers.companies.Fetcher", w.fetcher)
    monkeypatch.setattr("app.http.time.sleep", lambda s: None)
    return w


@pytest.fixture
def db_reset():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:  # lifespan runs create_all
        yield c


@pytest.fixture
def user(client):
    assert client.post("/api/auth/login", json={"password": "test-pass"}).status_code == 200
    return client
