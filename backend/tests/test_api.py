from datetime import date, timedelta

import pytest


def make_company(user, name="Stripe", **kw):
    r = user.post("/api/companies", json={"name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def make_app(user, **kw):
    body = {"company_name": "Stripe", "role": "Backend Engineer"} | kw
    r = user.post("/api/applications", json=body)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/companies"),
        ("get", "/api/applications"),
        ("get", "/api/signals"),
        ("get", "/api/runs"),
        ("post", "/api/runs"),
        ("get", "/api/dashboard"),
        ("get", "/api/digests"),
        ("post", "/api/companies/detect"),
    ],
)
def test_everything_needs_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_login(client):
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    assert client.get("/api/auth/me").json() == {"owner": False}
    client.post("/api/auth/login", json={"password": "test-pass"})
    assert client.get("/api/auth/me").json() == {"owner": True}


def test_company_from_board_url(user):
    c = make_company(user, "Palantir", careers_url="https://jobs.lever.co/palantir")
    assert (c["board"], c["board_slug"]) == ("lever", "palantir")
    assert c["applications"] == 0 and c["open_roles"] is None
    assert user.post("/api/companies", json={"name": "PALANTIR "}).status_code == 409


def test_company_board_validation(user):
    r = user.post("/api/companies", json={"name": "X", "board": "workday", "board_slug": "x"})
    assert r.status_code == 422
    r = user.post("/api/companies", json={"name": "X", "board": "lever"})
    assert r.status_code == 422


def test_detect_from_board_link(user, web):
    r = user.post("/api/companies/detect", json={"url": "boards.greenhouse.io/stripe"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["board"] == "greenhouse" and d["jobs"] == 6
    assert d["top_teams"][0][1] >= d["top_teams"][-1][1]


def test_detect_from_careers_page(user, web, monkeypatch):
    monkeypatch.setattr(
        "app.http.socket.getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.215.14", 0))]
    )
    web.add("https://openai.com/careers", '<a href="https://jobs.ashbyhq.com/openai/123">Apply</a>')
    d = user.post("/api/companies/detect", json={"url": "https://openai.com/careers"}).json()
    assert (d["board"], d["board_slug"], d["jobs"]) == ("ashby", "openai", 7)


def test_detect_refuses_internal_urls(user, web):
    r = user.post("/api/companies/detect", json={"url": "http://127.0.0.1:8000/"})
    assert r.status_code == 422 and "public" in r.json()["detail"]


def test_detect_no_board(user, web, monkeypatch):
    monkeypatch.setattr(
        "app.http.socket.getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("93.184.215.14", 0))]
    )
    web.add("https://example.com/careers", "<p>Email us your CV</p>")
    r = user.post("/api/companies/detect", json={"url": "https://example.com/careers"})
    assert r.status_code == 422 and "track the company for news" in r.json()["detail"]


def test_changing_board_drops_snapshots(user, web):
    c = make_company(user, board="greenhouse", board_slug="stripe")
    user.post(f"/api/companies/{c['id']}/scan")
    assert user.get(f"/api/companies/{c['id']}").json()["trend"]
    r = user.patch(f"/api/companies/{c['id']}", json={"board": "ashby", "board_slug": "openai"})
    assert r.status_code == 200
    assert user.get(f"/api/companies/{c['id']}").json()["trend"] == []
    assert (
        user.patch(f"/api/companies/{c['id']}", json={"board": "", "board_slug": ""}).json()[
            "board"
        ]
        == ""
    )


def test_application_creates_company_and_follow_up(user):
    a = make_app(user, applied_on="2026-10-01", team="Payments")
    assert a["company"] == "Stripe" and a["status"] == "applied"
    assert a["follow_up_on"] == "2026-10-08"  # a week after applying
    b = make_app(user, company_name="stripe", role="Infra Engineer", follow_up_on="2026-11-01")
    assert b["company_id"] == a["company_id"] and b["follow_up_on"] == "2026-11-01"
    assert len(user.get("/api/companies").json()) == 1
    assert user.post("/api/applications", json={"role": "x"}).status_code == 422
    assert user.post("/api/applications", json={"company_id": 999, "role": "x"}).status_code == 404
    r = user.post("/api/applications", json={"company_name": "A", "role": "x", "status": "ghosted"})
    assert r.status_code == 422


def test_new_cards_go_on_top(user):
    a, b = make_app(user, role="A"), make_app(user, role="B")
    col = [
        x["role"] for x in sorted(user.get("/api/applications").json(), key=lambda x: x["position"])
    ]
    assert col == ["B", "A"]
    assert b["position"] < a["position"]


def test_move_between_columns_and_reorder(user):
    a, b, c = (make_app(user, role=r) for r in "ABC")
    r = user.post(f"/api/applications/{a['id']}/move", json={"status": "interview", "index": 0})
    moved = r.json()
    assert moved["status"] == "interview"
    assert moved["follow_up_on"] == (date.today() + timedelta(days=3)).isoformat()
    user.post(f"/api/applications/{b['id']}/move", json={"status": "interview", "index": 0})
    user.post(f"/api/applications/{c['id']}/move", json={"status": "interview", "index": 99})

    def column(status):
        rows = [x for x in user.get("/api/applications").json() if x["status"] == status]
        return [x["role"] for x in sorted(rows, key=lambda x: x["position"])]

    assert column("interview") == ["B", "A", "C"]
    user.post(f"/api/applications/{c['id']}/move", json={"status": "interview", "index": 1})
    assert column("interview") == ["B", "C", "A"]
    r = user.post(f"/api/applications/{a['id']}/move", json={"status": "offer", "index": 0})
    assert r.json()["follow_up_on"] is None
    assert column("applied") == []


def test_patch_and_delete_application(user):
    a = make_app(user)
    r = user.patch(
        f"/api/applications/{a['id']}", json={"notes": "  Recruiter: Sam  ", "follow_up_on": None}
    )
    assert r.json()["notes"] == "  Recruiter: Sam  " and r.json()["follow_up_on"] is None
    assert user.delete(f"/api/applications/{a['id']}").status_code == 204
    assert user.get("/api/applications").json() == []


def test_scan_run_signals_and_read_state(user, web):
    make_app(user, team="Sales Development")
    cid = user.get("/api/companies").json()[0]["id"]
    user.patch(f"/api/companies/{cid}", json={"board": "greenhouse", "board_slug": "stripe"})
    r = user.post("/api/runs")
    assert r.status_code == 202
    run = user.get(f"/api/runs/{r.json()['run_id']}").json()
    assert run["status"] == "done" and run["finished_at"]  # eager Celery: chord ran inline
    assert run["stats"]["companies"] == 1 and run["stats"]["failed"] == 0
    assert (
        run["stats"]["new_signals"]
        == run["stats"]["results"][0]["hiring_signals"] + run["stats"]["results"][0]["news_signals"]
    )

    sigs = user.get("/api/signals").json()
    assert sigs and {s["company"] for s in sigs} == {"Stripe"}
    assert {s["source"] for s in sigs} == {"hiring", "news"}
    assert all(s["sentiment"] in ("bullish", "bearish", "neutral") for s in sigs)
    only_news = user.get("/api/signals", params={"source": "news"}).json()
    assert only_news and all(s["source"] == "news" for s in only_news)
    assert user.get("/api/signals", params={"sentiment": "great"}).status_code == 422

    first = sigs[0]["id"]
    user.post(f"/api/signals/{first}/read")
    unread = user.get("/api/signals", params={"unread": True}).json()
    assert first not in {s["id"] for s in unread} and len(unread) == len(sigs) - 1
    assert user.post("/api/signals/read-all").json()["updated"] == len(sigs) - 1
    assert user.get("/api/companies").json()[0]["unread"] == 0


def test_run_records_board_errors(user, web):
    make_company(user, board="lever", board_slug="gone")
    run_id = user.post("/api/runs").json()["run_id"]
    run = user.get(f"/api/runs/{run_id}").json()
    assert run["stats"]["failed"] == 1 and "answered 404" in run["stats"]["results"][0]["error"]
    assert run["status"] == "failed"


def test_run_with_no_companies(user):
    run_id = user.post("/api/runs").json()["run_id"]
    assert user.get(f"/api/runs/{run_id}").json()["status"] == "done"


def test_digest_collects_signals_once_and_follow_ups(user, web, monkeypatch):
    sent = []
    monkeypatch.setattr("app.digest.mail.send", lambda *a: sent.append(a))
    monkeypatch.setattr("app.digest.settings.smtp_host", "mailpit")
    monkeypatch.setattr("app.digest.settings.digest_to", "me@example.com")
    assert user.post("/api/digests").status_code == 409  # nothing yet

    make_app(user, applied_on=(date.today() - timedelta(days=10)).isoformat())
    c = make_company(user, "Lever Co", board="lever", board_slug="palantir")
    user.post(f"/api/companies/{c['id']}/scan")
    r = user.post("/api/digests")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["signal_count"] > 0 and d["follow_ups"] == 1 and d["emailed_to"] == "me@example.com"
    to, subject, text, html = sent[0]
    assert subject.startswith(f"HireSignal: {d['signal_count']} new signal")
    assert "1 follow-up due" in subject
    assert "Follow up today" in text and "3 days overdue" in text
    assert "<script" not in html
    assert user.get(f"/api/digests/{d['id']}").json()["html"] == html

    # Signals go out once; the follow-up stays until it's handled
    d2 = user.post("/api/digests").json()
    assert d2["signal_count"] == 0 and d2["follow_ups"] == 1


def test_digest_escapes_titles(user, web, monkeypatch):
    from app.db import SessionLocal
    from app.digest import build
    from app.models import Signal

    c = make_company(user, "<b>Evil</b>")
    with SessionLocal() as db:
        db.add(
            Signal(
                company_id=c["id"],
                source="news",
                kind="other",
                sentiment="neutral",
                title="<img src=x onerror=alert(1)>",
                explanation="<script>",
                external_id="x",
                url='javascript:"',
            )
        )
        db.commit()
        d = build(db, "manual")
    assert "<img" not in d.html and "<script>" not in d.html and "&lt;b&gt;Evil" in d.html


def test_dashboard(user, web):
    make_app(user, applied_on=(date.today() - timedelta(days=8)).isoformat())
    a = make_app(user, role="Infra")
    user.post(f"/api/applications/{a['id']}/move", json={"status": "interview", "index": 0})
    d = user.get("/api/dashboard").json()
    assert d["by_status"] == {"applied": 1, "interview": 1, "offer": 0, "rejected": 0}
    assert d["response_rate"] == 0.5
    assert [f["role"] for f in d["follow_ups_due"]] == ["Backend Engineer"]
    assert d["last_run"] is None and d["llm"] == ""
    assert d["schedule"]["scan_hour"] == 2
    assert len(user.get("/api/follow-ups").json()) == 2


def test_company_detail_and_delete(user, web):
    c = make_company(user, board="greenhouse", board_slug="stripe")
    make_app(user)
    user.post(f"/api/companies/{c['id']}/scan")
    detail = user.get(f"/api/companies/{c['id']}").json()
    assert detail["open_roles"] == 6 and len(detail["trend"]) == 1 and detail["teams"]
    assert detail["applications"] == 1
    assert user.delete(f"/api/companies/{c['id']}").status_code == 204
    assert user.get("/api/applications").json() == []
    assert user.get("/api/signals").json() == []
    assert user.get(f"/api/companies/{c['id']}").status_code == 404
