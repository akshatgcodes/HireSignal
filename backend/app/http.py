"""One polite HTTP client for every source.

- A spacing per host: at most one request every `host_interval` seconds to the same host.
  With Redis the slot is shared, so several Celery workers still hit a host in turn.
- Retries with backoff on timeouts, 429 and 5xx, honouring Retry-After.
- Our own User-Agent, so a site owner can see who is calling.
"""

import ipaddress
import logging
import socket
import threading
import time
from urllib.parse import urlsplit

import httpx
import redis

from app.config import settings

log = logging.getLogger("hiresignal.http")

RETRY_STATUS = {429, 500, 502, 503, 504}


class FetchError(Exception):
    pass


def check_public_url(url: str) -> None:
    """Refuses URLs that point inside our own network. Careers URLs come from the user,
    and the server fetches them, so without this the API could be aimed at localhost,
    the Docker network or a cloud metadata address."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Only http(s) links work here")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise FetchError(f"Couldn't resolve {parts.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError(f"{parts.hostname} is not a public address")


class HostSpacing:
    """Waits until this host's slot is free. SET NX PX claims the slot for `interval`;
    whoever fails to claim it sleeps for what's left and tries again."""

    def __init__(self, interval: float, client: redis.Redis | None = None):
        self.interval = interval
        self.redis = client
        self._local: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        if self.interval <= 0:
            return
        if self.redis is not None:
            try:
                self._wait_redis(host)
                return
            except redis.RedisError:
                log.warning("redis unavailable, spacing %s in-process only", host)
        self._wait_local(host)

    def _wait_redis(self, host: str) -> None:
        key = f"hiresignal:host:{host}"
        ms = int(self.interval * 1000)
        while not self.redis.set(key, "1", nx=True, px=ms):
            left = self.redis.pttl(key)
            time.sleep(max(left, 50) / 1000)

    def _wait_local(self, host: str) -> None:
        with self._lock:
            now = time.monotonic()
            ready = self._local.get(host, 0.0)
            self._local[host] = max(now, ready) + self.interval
        if ready > now:
            time.sleep(ready - now)


class Fetcher:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        spacing: HostSpacing | None = None,
        retries: int = 3,
        backoff: float = 2.0,
    ):
        self.client = httpx.Client(
            transport=transport,
            timeout=settings.http_timeout,
            follow_redirects=True,
            headers={"User-Agent": settings.user_agent},
        )
        if spacing is None:
            r = redis.Redis.from_url(settings.redis_url) if settings.redis_url else None
            spacing = HostSpacing(settings.host_interval, r)
        self.spacing = spacing
        self.retries = retries
        self.backoff = backoff

    def get(self, url: str, **params) -> httpx.Response:
        host = urlsplit(url).hostname or ""
        last = ""
        for attempt in range(self.retries + 1):
            self.spacing.wait(host)
            try:
                res = self.client.get(url, params=params or None)
            except httpx.TransportError as e:
                last = f"{type(e).__name__}: {e}"
            else:
                if res.status_code not in RETRY_STATUS:
                    if res.status_code >= 400:
                        raise FetchError(f"{host} answered {res.status_code}")
                    return res
                last = f"{host} answered {res.status_code}"
                if attempt < self.retries:
                    time.sleep(self._delay(res, attempt))
                    continue
            if attempt < self.retries:
                time.sleep(self.backoff * 2**attempt)
        raise FetchError(f"{last} (gave up after {self.retries + 1} tries)")

    def _delay(self, res: httpx.Response, attempt: int) -> float:
        after = res.headers.get("Retry-After", "")
        if after.isdigit():
            return min(float(after), 120.0)
        return self.backoff * 2**attempt

    def page(self, url: str, max_hops: int = 4) -> str:
        """A user-supplied page. Each redirect hop is checked, so a public URL can't
        bounce the request to an internal one."""
        for _ in range(max_hops):
            check_public_url(url)
            self.spacing.wait(urlsplit(url).hostname or "")
            try:
                res = self.client.get(url, follow_redirects=False)
            except httpx.TransportError as e:
                raise FetchError(f"Couldn't load the page ({type(e).__name__})") from e
            if res.is_redirect:
                url = str(res.next_request.url) if res.next_request else ""
                continue
            if res.status_code >= 400:
                raise FetchError(f"The page answered {res.status_code}")
            return res.text[:2_000_000]
        raise FetchError("Too many redirects")

    def json(self, url: str, **params):
        return self.get(url, **params).json()

    def close(self) -> None:
        self.client.close()
