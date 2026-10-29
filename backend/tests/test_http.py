import time

import fakeredis
import httpx
import pytest

from app import http as app_http
from app.http import FetchError, HostSpacing
from tests.conftest import FakeWeb

URL = "https://api.example.com/x"


@pytest.fixture
def sleeps(monkeypatch):
    log: list[float] = []
    monkeypatch.setattr("app.http.time.sleep", log.append)
    return log


def test_retries_5xx_then_succeeds(sleeps):
    w = FakeWeb().add(URL, "", 503).add(URL, "", 502).add(URL, {"ok": 1})
    assert w.fetcher(backoff=1).json(URL) == {"ok": 1}
    assert len(w.requests) == 3
    assert sleeps == [1, 2]  # exponential backoff


def test_honours_retry_after(sleeps):
    w = FakeWeb().add(URL, "", 429, {"Retry-After": "7"}).add(URL, "ok")
    assert w.fetcher(backoff=1).get(URL).text == "ok"
    assert sleeps == [7.0]


def test_retry_after_is_capped(sleeps):
    w = FakeWeb().add(URL, "", 429, {"Retry-After": "86400"}).add(URL, "ok")
    w.fetcher().get(URL)
    assert sleeps == [120.0]


def test_gives_up(sleeps):
    w = FakeWeb().add(URL, "", 503)
    with pytest.raises(FetchError, match="gave up after 3 tries"):
        w.fetcher(retries=2).get(URL)
    assert len(w.requests) == 3


def test_4xx_is_not_retried(sleeps):
    w = FakeWeb().add(URL, "", 404)
    with pytest.raises(FetchError, match="answered 404"):
        w.fetcher().get(URL)
    assert len(w.requests) == 1


def test_transport_errors_are_retried(sleeps):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("slow", request=request)
        return httpx.Response(200, text="ok")

    f = app_http.Fetcher(transport=httpx.MockTransport(handler), spacing=HostSpacing(0))
    assert f.get(URL).text == "ok"
    assert len(calls) == 2


def test_local_spacing_waits_between_same_host(monkeypatch):
    waits: list[float] = []
    clock = [100.0]
    monkeypatch.setattr("app.http.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.http.time.sleep", waits.append)
    s = HostSpacing(2.0)
    s.wait("a.com")
    s.wait("b.com")  # another host isn't delayed
    s.wait("a.com")
    assert waits == [2.0]
    clock[0] += 5
    s.wait("a.com")
    assert waits == [2.0]


def test_redis_spacing_is_shared_between_clients():
    r = fakeredis.FakeRedis()
    a, b = HostSpacing(0.2, r), HostSpacing(0.2, r)
    start = time.monotonic()
    a.wait("x.com")
    b.wait("x.com")  # a second process must wait for the first one's slot
    assert time.monotonic() - start >= 0.15


def test_redis_down_falls_back_to_local(monkeypatch):
    class Broken:
        def set(self, *a, **k):
            import redis

            raise redis.ConnectionError("down")

    s = HostSpacing(1.0, Broken())
    monkeypatch.setattr("app.http.time.sleep", lambda s: None)
    s.wait("x.com")  # doesn't raise
    assert "x.com" in s._local


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/",
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "http:///nohost",
    ],
)
def test_private_and_odd_urls_are_refused(url):
    with pytest.raises(FetchError):
        app_http.check_public_url(url)


def test_page_checks_every_redirect(monkeypatch):
    monkeypatch.setattr(
        "app.http.socket.getaddrinfo",
        lambda host, *a, **k: [
            (0, 0, 0, "", ("127.0.0.1" if host == "localhost" else "93.184.215.14", 0))
        ],
    )
    w = FakeWeb().add(
        "https://careers.example.com/", "", 302, {"Location": "http://localhost/admin"}
    )
    with pytest.raises(FetchError, match="not a public address"):
        w.fetcher().page("https://careers.example.com/")
    assert [r.url.host for r in w.requests] == ["careers.example.com"]


def test_page_follows_public_redirects(monkeypatch):
    monkeypatch.setattr(
        "app.http.socket.getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.215.14", 0))]
    )
    w = (
        FakeWeb()
        .add("https://example.com/careers", "", 301, {"Location": "https://example.com/jobs"})
        .add("https://example.com/jobs", "<html>jobs</html>")
    )
    assert w.fetcher().page("https://example.com/careers") == "<html>jobs</html>"
