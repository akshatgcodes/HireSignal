import json
from datetime import date

import pytest
from sqlalchemy import select

from app import pipeline
from app.db import SessionLocal
from app.models import Application, Company, JobSnapshot, Signal
from tests.conftest import FakeChat, fixture, fixture_json


@pytest.fixture
def db(db_reset):
    with SessionLocal() as s:
        yield s


@pytest.fixture
def stripe(db):
    c = Company(name="Stripe", board="greenhouse", board_slug="stripe")
    db.add(c)
    db.flush()
    db.add(
        Application(
            company_id=c.id, role="SDR", team="Sales Development", applied_on=date(2026, 10, 20)
        )
    )
    db.commit()
    return c


def relevant(db):
    return db.scalars(select(Signal).where(Signal.relevant.is_(True))).all()


def test_first_scan_baseline_and_news(db, stripe, web):
    stats = pipeline.scan_company(db, stripe.id, web.fetcher())
    assert stats["jobs"] == 6 and stats["hiring_signals"] == 1 and stats["error"] == ""
    assert stats["news_seen"] > 0 and stats["news_signals"] == stats["news_new"]
    snap = db.scalars(select(JobSnapshot)).one()
    assert snap.total == 6 and sum(snap.by_team.values()) == 6
    kinds = {s.kind for s in relevant(db) if s.source == "hiring"}
    assert kinds == {"baseline"}
    # No key in tests → keyword classifier
    assert {s.classified_by for s in relevant(db) if s.source == "news"} == {"keywords"}
    assert db.get(Company, stripe.id).last_scanned_at is not None


def test_second_scan_diffs_and_dedups_news(db, stripe, web):
    pipeline.scan_company(db, stripe.id, web.fetcher())
    before = len(relevant(db))
    data = fixture_json("greenhouse_departments.json")
    dept = next(d for d in data["departments"] if d["name"].endswith("AMER Sales Development Reps"))
    dept["jobs"].append(
        {
            "id": 999,
            "title": "SDR, Fintech",
            "absolute_url": "https://stripe.com/jobs/999",
            "location": {"name": "NYC"},
        }
    )
    web.routes[("boards-api.greenhouse.io", "/v1/boards/stripe/departments")] = [
        (200, json.dumps(data), {})
    ]
    stats = pipeline.scan_company(db, stripe.id, web.fetcher())
    assert stats["news_new"] == 0 and stats["news_signals"] == 0  # same headlines
    new = relevant(db)[before:]
    assert [s.kind for s in new] == ["team_growth"]
    assert "SDR, Fintech" in new[0].explanation


def test_irrelevant_news_is_stored_hidden_and_not_reclassified(db, stripe, web):
    def reply(n):
        items = [
            {
                "i": i,
                "relevant": i != 1,
                "sentiment": "neutral",
                "kind": "product",
                "explanation": "e",
            }
            for i in range(1, n + 1)
        ]
        return json.dumps({"items": items})

    chat = FakeChat(reply(20))
    pipeline.scan_company(db, stripe.id, web.fetcher(), model=chat)
    hidden = db.scalars(select(Signal).where(Signal.relevant.is_(False))).all()
    assert len(hidden) == 1 and hidden[0].explanation == ""
    pipeline.scan_company(db, stripe.id, web.fetcher(), model=chat)
    assert len(chat.calls) == 1  # nothing new the second night, so no LLM call


def test_board_failure_still_scans_news(db, stripe, web):
    web.routes[("boards-api.greenhouse.io", "/v1/boards/stripe/departments")] = [(404, "", {})]
    stats = pipeline.scan_company(db, stripe.id, web.fetcher())
    assert "job board: boards-api.greenhouse.io answered 404" in stats["error"]
    assert stats["news_signals"] > 0
    assert db.get(Company, stripe.id).last_error.startswith("job board:")
    assert db.scalars(select(JobSnapshot)).all() == []


def test_news_only_company(db, web):
    c = Company(name="Stripe")
    db.add(c)
    db.commit()
    stats = pipeline.scan_company(db, c.id, web.fetcher())
    assert "jobs" not in stats and stats["news_signals"] > 0
    assert "boards-api.greenhouse.io" not in web.hosts()


def test_old_snapshots_drop_their_job_lists(db, stripe, web):
    for _ in range(4):
        pipeline.scan_company(db, stripe.id, web.fetcher())
    snaps = db.scalars(select(JobSnapshot).order_by(JobSnapshot.id)).all()
    assert [bool(s.jobs) for s in snaps] == [False, False, True, True]
    assert all(s.total == 6 for s in snaps)


def test_deleted_company(db, web):
    assert pipeline.scan_company(db, 12345, web.fetcher()) == {"error": "company was deleted"}


def test_one_request_per_source(db, stripe, web):
    pipeline.scan_company(db, stripe.id, web.fetcher())
    assert sorted(web.hosts()) == ["boards-api.greenhouse.io", "hn.algolia.com", "news.google.com"]
    assert any(r.url.path == "/v1/boards/stripe/departments" for r in web.requests)


def test_same_story_under_a_new_id_is_skipped(db, stripe, web):
    pipeline.scan_company(db, stripe.id, web.fetcher())
    xml = fixture("google_news.xml").replace(
        '<guid isPermaLink="false">CBMi', '<guid isPermaLink="false">NEWID'
    )
    web.routes[("news.google.com", "/rss/search")] = [(200, xml, {})]
    stats = pipeline.scan_company(db, stripe.id, web.fetcher())
    assert stats["news_new"] == 0
