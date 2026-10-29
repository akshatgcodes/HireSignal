from datetime import datetime

import pytest

from app.sources import boards, news
from tests.conftest import fixture, fixture_json


def test_greenhouse_departments_become_teams():
    jobs = boards.parse_greenhouse(fixture_json("greenhouse_departments.json"))
    assert len(jobs) == 6
    assert len({j.id for j in jobs}) == 6  # each job listed once
    teams = {j.team for j in jobs}
    # Cost-centre codes are stripped from department names
    assert "Global Sales Development Mgrs" in teams
    assert not any(t[0].isdigit() for t in teams)
    j = jobs[0]
    assert j.url.startswith("https://stripe.com/jobs/") and j.title and j.location


def test_greenhouse_no_department_is_other():
    data = {"departments": [{"name": "No Department", "jobs": [{"id": 1, "title": "X"}]}]}
    assert boards.parse_greenhouse(data)[0].team == "Other"


def test_lever_postings():
    jobs = boards.parse_lever(fixture_json("lever_postings.json"))
    assert len(jobs) == 8
    assert {j.team for j in jobs} == {"Administrative", "Business Development", "Dev"}
    assert jobs[0].url.startswith("https://jobs.lever.co/palantir/")


def test_ashby_uses_department_and_skips_unlisted():
    jobs = boards.parse_ashby(fixture_json("ashby_board.json"))
    assert len(jobs) == 7  # the fixture's last job is marked unlisted
    assert "Applied AI" in {j.team for j in jobs}
    assert "Applied AI Engineering" not in {j.team for j in jobs}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("https://boards.greenhouse.io/stripe", ("greenhouse", "stripe")),
        ("https://job-boards.greenhouse.io/figma/jobs/123", ("greenhouse", "figma")),
        ("boards-api.greenhouse.io/v1/boards/airbnb/jobs", ("greenhouse", "airbnb")),
        ("https://boards.greenhouse.io/embed/job_board?for=discord", ("greenhouse", "discord")),
        ("https://jobs.lever.co/palantir/6ed76ce8", ("lever", "palantir")),
        ("https://jobs.ashbyhq.com/openai", ("ashby", "openai")),
        ("https://jobs.ashbyhq.com/Notion.so/abc", ("ashby", "Notion.so")),
        ("https://stripe.com/jobs", None),
    ],
)
def test_detect(text, expected):
    assert boards.detect(text) == expected


def test_detect_from_page_reads_embeds_and_links():
    page = """<html><body><h1>Careers</h1>
    <script src="https://boards.greenhouse.io/embed/job_board/js?for=acme"></script>
    </body></html>"""
    assert boards.detect_from_page(page) == ("greenhouse", "acme")
    page = '<a href="https://jobs.lever.co/acme-inc/123">Apply</a>'
    assert boards.detect_from_page(page) == ("lever", "acme-inc")
    assert boards.detect_from_page("<p>We're hiring! Email us.</p>") is None


def test_google_news_parses_items_and_strips_publisher():
    items = news.parse_google_news(fixture("google_news.xml"))
    assert len(items) == 6
    first = items[0]
    assert first.title == "Stripe Pay Targets Instant B2B Payments"
    assert first.publisher == "PYMNTS.com"
    assert first.external_id.startswith("gn:CBMi")
    assert first.published_at == datetime(2026, 10, 28, 2, 4, 32)
    assert first.url.startswith("https://news.google.com/rss/articles/")
    # Unicode punctuation survives
    assert any("’" in a.title for a in items)


def test_hn_hits():
    items = news.parse_hn(fixture_json("hn_search.json"))
    assert len(items) == 5
    assert all(a.external_id.startswith("hn:") and a.publisher == "Hacker News" for a in items)
    assert items[0].published_at.year == 2026


def test_hn_hit_without_url_links_to_discussion():
    data = {
        "hits": [
            {"objectID": "9", "title": "Ask HN: Stripe?", "created_at": "2026-10-01T00:00:00Z"}
        ]
    }
    assert news.parse_hn(data)[0].url == "https://news.ycombinator.com/item?id=9"


@pytest.mark.parametrize(
    "title,hit",
    [
        ("Stripe raises $1B", True),
        ("Why stripe's API is good", True),
        ("Stripe-backed startup", True),
        ("Pinstripe suits are back", False),
        ("Stripes and dots", False),
    ],
)
def test_mentions_whole_word(title, hit):
    assert news._mentions("Stripe", title) is hit


def test_fetch_news_merges_sources_filters_and_sorts(web):
    f = web.fetcher()
    items = news.fetch_news(f, "Stripe")
    assert {a.source for a in items} == {"google_news", "hn"}
    assert all(news._mentions("Stripe", a.title) for a in items)
    dates = [a.published_at for a in items]
    assert dates == sorted(dates, reverse=True)
    gn = next(r for r in web.requests if r.url.host == "news.google.com")
    assert gn.url.params["q"] == '"Stripe" when:30d'
    assert gn.headers["user-agent"].startswith("HireSignal/")
    hn = next(r for r in web.requests if r.url.host == "hn.algolia.com")
    assert hn.url.params["numericFilters"].startswith("created_at_i>")


def test_fetch_news_uses_custom_query(web):
    news.fetch_news(web.fetcher(), "Box", '"Box Inc" OR "box.com"')
    gn = next(r for r in web.requests if r.url.host == "news.google.com")
    assert gn.url.params["q"].startswith('"Box Inc" OR "box.com"')


@pytest.mark.parametrize(
    "board,slug,host",
    [
        ("greenhouse", "stripe", "boards-api.greenhouse.io"),
        ("lever", "palantir", "api.lever.co"),
        ("ashby", "openai", "api.ashbyhq.com"),
    ],
)
def test_fetch_jobs_hits_the_right_api(web, board, slug, host):
    jobs = boards.fetch_jobs(web.fetcher(), board, slug)
    assert jobs and web.hosts() == [host]


def test_fetch_jobs_unknown_board(web):
    with pytest.raises(ValueError):
        boards.fetch_jobs(web.fetcher(), "workday", "x")


def test_dedupe_by_headline():
    a = news.Article("gn:1", "Palantir’s chief warns", "u", "p", None, "google_news")
    b = news.Article("hn:2", "Palantir's chief warns!", "u", "p", None, "hn")
    c = news.Article("hn:3", "Palantir hires", "u", "p", None, "hn")
    assert [x.external_id for x in news.dedupe([a, b, c])] == ["gn:1", "hn:3"]
