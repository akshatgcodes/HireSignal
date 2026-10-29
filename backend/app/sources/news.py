"""Recent news about a company: Google News RSS and Hacker News (Algolia search).

Google News RSS is free to read in a personal feed reader for personal, non-commercial
use (its feed says so). HireSignal is a single-user tracker, which is that use; anyone
turning it into a hosted product would need a licensed news API instead.
"""

import html
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from app.config import settings
from app.http import Fetcher


@dataclass
class Article:
    external_id: str
    title: str
    url: str
    publisher: str
    published_at: datetime | None
    source: str  # google_news | hn

    @property
    def text(self) -> str:
        return self.title


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


def parse_google_news(xml: str) -> list[Article]:
    soup = BeautifulSoup(xml, "xml")
    out = []
    for item in soup.find_all("item"):
        title = item.title.get_text(strip=True) if item.title else ""
        publisher = item.source.get_text(strip=True) if item.source else ""
        # Titles end with " - Publisher"; drop it so the LLM sees only the headline
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3]
        guid = item.guid.get_text(strip=True) if item.guid else ""
        link = item.link.get_text(strip=True) if item.link else ""
        try:
            published = _naive_utc(parsedate_to_datetime(item.pubDate.get_text(strip=True)))
        except (AttributeError, TypeError, ValueError):
            published = None
        if title and (guid or link):
            out.append(
                Article(
                    external_id=f"gn:{guid or link}"[:200],
                    title=html.unescape(title),
                    url=link,
                    publisher=publisher,
                    published_at=published,
                    source="google_news",
                )
            )
    return out


def parse_hn(data: dict) -> list[Article]:
    out = []
    for h in data.get("hits", []):
        if not h.get("title"):
            continue
        try:
            published = _naive_utc(datetime.fromisoformat(h["created_at"].replace("Z", "+00:00")))
        except (KeyError, ValueError):
            published = None
        out.append(
            Article(
                external_id=f"hn:{h['objectID']}",
                title=h["title"],
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                publisher="Hacker News",
                published_at=published,
                source="hn",
            )
        )
    return out


def _mentions(name: str, title: str) -> bool:
    """Whole-word match: keeps "Stripe" from matching "pinstripe"."""
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", title, re.I) is not None


def title_key(title: str) -> str:
    """Same story, different feed: "Palantir’s chief" and "Palantir's chief" are one."""
    return re.sub(r"[\W_]+", " ", title.lower()).strip()


def dedupe(articles: list[Article]) -> list[Article]:
    seen, out = set(), []
    for a in articles:
        k = title_key(a.title)
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out


def fetch_news(fetcher: Fetcher, name: str, query: str = "") -> list[Article]:
    phrase = query or f'"{name}"'
    feed = fetcher.get(
        "https://news.google.com/rss/search",
        q=f"{phrase} when:{settings.news_days}d",
        hl="en-US",
        gl="US",
        ceid="US:en",
    ).text
    since = int(datetime.now(UTC).timestamp()) - settings.news_days * 86400
    hn = fetcher.json(
        "https://hn.algolia.com/api/v1/search_by_date",
        query=phrase,
        tags="story",
        numericFilters=f"created_at_i>{since}",
        hitsPerPage=20,
    )
    articles = parse_google_news(feed) + parse_hn(hn)
    # Both searches are fuzzy; keep headlines that actually name the company
    articles = [a for a in articles if _mentions(name, a.title)]
    articles.sort(key=lambda a: a.published_at or datetime.min, reverse=True)
    return dedupe(articles)[: settings.news_per_company]
