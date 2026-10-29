"""Open roles from the public job-board APIs that most tech companies post through.

All three are documented, unauthenticated endpoints meant for embedding job lists on
other sites, so reading them is within their intended use:
- Greenhouse  boards-api.greenhouse.io/v1/boards/{slug}/departments
- Lever       api.lever.co/v0/postings/{slug}?mode=json
- Ashby       api.ashbyhq.com/posting-api/job-board/{slug}
"""

import re
from dataclasses import asdict, dataclass

from bs4 import BeautifulSoup

from app.http import Fetcher

BOARDS = ("greenhouse", "lever", "ashby")

# Links a careers page (or the user) might give us, and the slug inside each
GH = r"(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?(?:embed/job_board\?for=)?([\w-]+)"
PATTERNS = [
    ("greenhouse", re.compile(GH, re.I)),
    ("greenhouse", re.compile(r"greenhouse\.io/embed/job_board(?:/js)?\?for=([\w-]+)", re.I)),
    ("lever", re.compile(r"(?:jobs|api)\.lever\.co/(?:v0/postings/)?([\w-]+)", re.I)),
    (
        "ashby",
        re.compile(
            r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([\w.-]+)", re.I
        ),
    ),
]
NOT_SLUGS = {"embed", "v1", "v0", "api", "jobs", "js"}


@dataclass
class Job:
    id: str
    title: str
    team: str
    location: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect(text: str) -> tuple[str, str] | None:
    """(board, slug) from a URL or a page's HTML, or None."""
    for board, pattern in PATTERNS:
        for m in pattern.finditer(text):
            slug = m.group(1)
            if slug.lower() not in NOT_SLUGS:
                return board, slug
    return None


def detect_from_page(html: str) -> tuple[str, str] | None:
    """Company careers pages usually embed the board: an iframe, a script or apply links."""
    soup = BeautifulSoup(html, "lxml")
    urls = [
        tag.get(attr, "")
        for tag, attr in [(t, "href") for t in soup.find_all("a")]
        + [(t, "src") for t in soup.find_all(["iframe", "script"])]
    ]
    return detect(" ".join(urls)) or detect(html)


# Some boards prefix departments with internal cost-centre codes ("1130 Sales Development")
CODE_PREFIX = re.compile(r"^\d{2,}\s+")


def _team(name: str | None) -> str:
    return CODE_PREFIX.sub("", (name or "").strip()) or "Other"


def parse_greenhouse(data: dict) -> list[Job]:
    # /departments lists each job once, under its own (leaf) department
    jobs = []
    for dept in data.get("departments", []):
        team = "Other" if dept.get("name") == "No Department" else _team(dept.get("name"))
        for j in dept.get("jobs", []):
            jobs.append(
                Job(
                    id=str(j["id"]),
                    title=j.get("title", "").strip(),
                    team=team,
                    location=(j.get("location") or {}).get("name", ""),
                    url=j.get("absolute_url", ""),
                )
            )
    return jobs


def parse_lever(data: list) -> list[Job]:
    return [
        Job(
            id=p["id"],
            title=p.get("text", "").strip(),
            team=_team((p.get("categories") or {}).get("team")),
            location=(p.get("categories") or {}).get("location", "") or "",
            url=p.get("hostedUrl", ""),
        )
        for p in data
    ]


def parse_ashby(data: dict) -> list[Job]:
    return [
        Job(
            id=j["id"],
            title=j.get("title", "").strip(),
            # "department" is the broad group; "team" can be very fine-grained
            team=_team(j.get("department") or j.get("team")),
            location=j.get("location", "") or "",
            url=j.get("jobUrl", ""),
        )
        for j in data.get("jobs", [])
        if j.get("isListed", True)
    ]


def fetch_jobs(fetcher: Fetcher, board: str, slug: str) -> list[Job]:
    if board == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/departments"
        return parse_greenhouse(fetcher.json(url))
    if board == "lever":
        return parse_lever(fetcher.json(f"https://api.lever.co/v0/postings/{slug}", mode="json"))
    if board == "ashby":
        return parse_ashby(fetcher.json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}"))
    raise ValueError(f"unknown board {board!r}")
