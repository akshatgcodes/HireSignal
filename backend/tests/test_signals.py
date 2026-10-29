from datetime import date

from app.models import Application
from app.signals import diff, posting_for, teams_for


def job(title, team, url=""):
    return {"title": title, "team": team, "location": "Remote", "url": url}


def board(n_eng=4, n_sales=10, extra: dict | None = None) -> dict:
    jobs = {
        f"e{i}": job(f"Engineer {i}", "Payments Engineering", f"https://x/jobs/e{i}")
        for i in range(n_eng)
    }
    jobs |= {f"s{i}": job(f"Seller {i}", "Sales", f"https://x/jobs/s{i}") for i in range(n_sales)}
    return jobs | (extra or {})


def app(team="", url="", status="applied"):
    return Application(
        role="Backend Engineer", team=team, job_url=url, status=status, applied_on=date(2026, 10, 1)
    )


def kinds(drafts):
    return sorted(d.kind for d in drafts)


def test_first_scan_is_a_baseline():
    [d] = diff("Acme", None, board(), [app("Payments")], "2026-10-30")
    assert d.kind == "baseline" and d.sentiment == "neutral"
    assert d.title == "Now tracking 14 open roles at Acme"


def test_no_change_no_signals():
    assert diff("Acme", board(), board(), [app("Payments")], "d") == []


def test_new_roles_in_your_team_are_bullish():
    cur = board(extra={"e9": job("Staff Engineer", "Payments Engineering", "https://x/jobs/e9")})
    [d] = diff("Acme", board(), cur, [app("payments")], "d")
    assert d.kind == "team_growth" and d.sentiment == "bullish"
    assert d.title == "1 new role in Payments Engineering"
    assert "Staff Engineer" in d.explanation and "(4 → 5 open)" in d.explanation
    assert d.url == "https://x/jobs/e9"


def test_new_roles_elsewhere_are_ignored():
    cur = board(extra={"s9": job("Seller 9", "Sales")})
    assert diff("Acme", board(), cur, [app("Payments")], "d") == []


def test_team_halving_is_bearish():
    [d] = diff("Acme", board(n_eng=6), board(n_eng=3), [app("Payments Engineering")], "d")
    assert (d.kind, d.sentiment) == ("team_shrink", "bearish")
    assert d.title == "Payments Engineering openings fell from 6 to 3"


def test_small_team_changes_dont_count():
    assert diff("Acme", board(n_eng=2), board(n_eng=1), [app("Payments")], "d") == []


def test_company_wide_drop_and_growth():
    [d] = diff("Acme", board(n_sales=20), board(n_sales=5), [], "d")
    assert (d.kind, d.sentiment) == ("hiring_slowdown", "bearish")
    assert "fell from 24 to 9" in d.title
    [d] = diff("Acme", board(n_sales=10), board(n_sales=20), [], "d")
    assert (d.kind, d.sentiment) == ("hiring_growth", "bullish")


def test_empty_board_says_paused():
    [d] = diff("Acme", board(), {}, [], "d")
    assert "paused company-wide" in d.explanation


def test_applied_posting_closed():
    prev = board()
    cur = {k: v for k, v in prev.items() if k != "e1"}
    drafts = diff("Acme", prev, cur, [app(url="https://x/jobs/e1")], "d")
    assert kinds(drafts) == ["posting_closed"]
    assert drafts[0].title == "The Engineer 1 posting is no longer listed"
    assert drafts[0].external_id == "hiring:posting_closed:e1"


def test_closed_applications_are_not_watched():
    prev = board()
    cur = {k: v for k, v in prev.items() if k != "e1"}
    assert diff("Acme", prev, cur, [app(url="https://x/jobs/e1", status="rejected")], "d") == []


def test_team_comes_from_the_posting_when_not_typed():
    cur = board(extra={"e9": job("Staff Engineer", "Payments Engineering")})
    drafts = diff("Acme", board(), cur, [app(url="https://x/jobs/e2")], "d")
    assert kinds(drafts) == ["team_growth"]


def test_two_applications_to_one_team_report_once():
    cur = board(extra={"e9": job("Staff Engineer", "Payments Engineering")})
    drafts = diff("Acme", board(), cur, [app("Payments"), app("payments engineering")], "d")
    assert kinds(drafts) == ["team_growth"]


def test_growth_key_is_stable_for_the_same_new_roles():
    cur = board(extra={"e9": job("Staff Engineer", "Payments Engineering")})
    a = diff("Acme", board(), cur, [app("Payments")], "day1")
    b = diff("Acme", board(), cur, [app("Payments")], "day2")
    assert a[0].external_id == b[0].external_id


def test_team_matching_is_by_whole_words():
    teams = {"Payments Engineering", "Pay Ops", "Sales", "Infrastructure"}
    assert teams_for(app("Payments"), {}, teams) == {"Payments Engineering"}
    assert teams_for(app("Pay"), {}, teams) == {"Pay Ops"}
    assert teams_for(app("Infra"), {}, teams) == set()
    # A broader board team still counts: "Sales" covers "Sales & Partnerships"
    assert teams_for(app("Sales & Partnerships"), {}, teams) == {"Sales"}
    assert teams_for(app("sales"), {}, teams) == {"Sales"}
    assert teams_for(app(""), {}, teams) == set()


def test_posting_for_matches_ids_as_whole_tokens():
    jobs = {
        "8172510": job("A", "T", "https://stripe.com/jobs/search?gh_jid=8172510"),
        "17251": job("B", "T"),
    }
    assert (
        posting_for(app(url="https://job-boards.greenhouse.io/stripe/jobs/8172510"), jobs)
        == "8172510"
    )
    assert posting_for(app(url="https://stripe.com/jobs/search?gh_jid=8172510"), jobs) == "8172510"
    assert posting_for(app(url="https://example.com/jobs/1"), jobs) is None
    assert posting_for(app(url=""), jobs) is None
