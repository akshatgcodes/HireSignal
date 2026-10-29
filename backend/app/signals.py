"""Hiring signals from two snapshots of a company's job board. No LLM here: these are
counts, so they're computed exactly and the wording is fixed.

The first scan only records a baseline. After that, each scan compares with the last:
- new roles in a team you applied to            → bullish
- that team's openings at least halved           → bearish
- company-wide openings up or down by 30%+       → bullish / bearish
- the posting you applied to is no longer listed → neutral (filled, paused or moved)
"""

import hashlib
import re
from dataclasses import dataclass

from app.models import Application

GROWTH = 0.30
TEAM_SHRINK = 0.50
MIN_TOTAL = 10  # below this, a 30% swing is two or three roles and means little
MIN_TEAM = 3
ACTIVE = ("applied", "interview")


@dataclass
class Draft:
    external_id: str
    kind: str
    sentiment: str
    title: str
    explanation: str
    url: str = ""


def _key(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:16]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def posting_for(app: Application, jobs: dict[str, dict]) -> str | None:
    """The job id the application's link points at, if it's on this board."""
    url = app.job_url or ""
    if not url:
        return None
    for job_id, job in jobs.items():
        if job.get("url") == url or re.search(rf"(?<![\w-]){re.escape(job_id)}(?![\w-])", url):
            return job_id
    return None


def teams_for(app: Application, jobs: dict[str, dict], teams: set[str]) -> set[str]:
    """Board teams that correspond to an application: its posting's team, plus any team
    whose name matches the team typed on the card (either contains the other)."""
    found = set()
    job_id = posting_for(app, jobs)
    if job_id:
        found.add(jobs[job_id]["team"])
    want = f" {_norm(app.team)} "
    if want.strip():
        for t in teams:
            # Whole words either way: "Payments" ~ "Payments Infrastructure", not "Pay"
            have = f" {_norm(t)} "
            if have.strip() and (want in have or have in want):
                found.add(t)
    return found


def _titles(jobs: dict[str, dict], ids: list[str], limit: int = 3) -> str:
    names = [jobs[i]["title"] for i in ids[:limit]]
    more = len(ids) - len(names)
    return ", ".join(names) + (f" and {more} more" if more > 0 else "")


def diff(
    company: str,
    prev: dict[str, dict] | None,
    cur: dict[str, dict],
    apps: list[Application],
    day: str,
) -> list[Draft]:
    """`prev`/`cur` map job id → {title, team, location, url}. `day` makes the dedup key
    unique per scan day, so the same change isn't reported twice."""
    if prev is None:
        roles = f"{len(cur)} open role{'s' if len(cur) != 1 else ''}"
        return [
            Draft(
                external_id=f"hiring:baseline:{day}",
                kind="baseline",
                sentiment="neutral",
                title=f"Now tracking {roles} at {company}",
                explanation="First scan of this job board. Changes show up from the next scan.",
            )
        ]
    out: list[Draft] = []
    teams = {j["team"] for j in cur.values()} | {j["team"] for j in prev.values()}
    active = [a for a in apps if a.status in ACTIVE]

    def count(jobs: dict, team: str) -> int:
        return sum(1 for j in jobs.values() if j["team"] == team)

    reported: set[str] = set()
    for app in active:
        for team in sorted(teams_for(app, prev | cur, teams)):
            if team in reported:
                continue
            reported.add(team)
            new = sorted(i for i, j in cur.items() if j["team"] == team and i not in prev)
            before, after = count(prev, team), count(cur, team)
            if new:
                out.append(
                    Draft(
                        external_id=f"hiring:team_growth:{_key(team, *new)}",
                        kind="team_growth",
                        sentiment="bullish",
                        title=f"{len(new)} new role{'s' if len(new) != 1 else ''} in {team}",
                        explanation=(
                            f"{team} at {company} posted {_titles(cur, new)} since the last scan "
                            f"({before} → {after} open). A team that's adding roles is "
                            "usually still filling seats."
                        ),
                        url=cur[new[0]]["url"],
                    )
                )
            if before >= MIN_TEAM and after <= before * (1 - TEAM_SHRINK):
                out.append(
                    Draft(
                        external_id=f"hiring:team_shrink:{_key(team, day)}",
                        kind="team_shrink",
                        sentiment="bearish",
                        title=f"{team} openings fell from {before} to {after}",
                        explanation=(
                            f"Half or more of {team}'s listings at {company} came down at once. "
                            "That can mean roles were filled, or that hiring there paused."
                        ),
                    )
                )

    before, after = len(prev), len(cur)
    if before >= MIN_TOTAL and after <= before * (1 - GROWTH):
        out.append(
            Draft(
                external_id=f"hiring:company_drop:{day}",
                kind="hiring_slowdown",
                sentiment="bearish",
                title=f"Open roles at {company} fell from {before} to {after}",
                explanation=(
                    "A drop this size between two scans often comes with a hiring freeze "
                    "or a re-org. Worth a polite check-in on any open application."
                    if after
                    else "The job board is now empty: hiring looks paused company-wide."
                ),
            )
        )
    elif before >= MIN_TOTAL and after >= before * (1 + GROWTH):
        out.append(
            Draft(
                external_id=f"hiring:company_growth:{day}",
                kind="hiring_growth",
                sentiment="bullish",
                title=f"Open roles at {company} rose from {before} to {after}",
                explanation="The company is opening roles quickly, so budgets are there.",
            )
        )

    for app in active:
        job_id = posting_for(app, prev)
        if job_id and job_id not in cur:
            out.append(
                Draft(
                    external_id=f"hiring:posting_closed:{job_id}",
                    kind="posting_closed",
                    sentiment="neutral",
                    title=f"The {prev[job_id]['title']} posting is no longer listed",
                    explanation=(
                        f"The role you applied to on {app.applied_on:%d %b} came off the board. "
                        "It may have been filled or paused; it doesn't settle your application "
                        "either way."
                    ),
                    url=app.job_url,
                )
            )
    return out
