from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_owner
from app.db import get_db
from app.http import Fetcher, FetchError
from app.models import Application, Company, JobSnapshot, Signal
from app.serialize import company_dict
from app.sources import boards

router = APIRouter(
    prefix="/api/companies", tags=["companies"], dependencies=[Depends(require_owner)]
)


class DetectIn(BaseModel):
    url: str = Field(max_length=500)


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    careers_url: str = Field(default="", max_length=500)
    board: str = ""
    board_slug: str = Field(default="", max_length=120)
    news_query: str = Field(default="", max_length=200)


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    careers_url: str | None = Field(default=None, max_length=500)
    board: str | None = None
    board_slug: str | None = Field(default=None, max_length=120)
    news_query: str | None = Field(default=None, max_length=200)


def detect_board(url: str, fetcher: Fetcher | None = None) -> dict:
    """Finds the job board behind a careers link and checks it answers."""
    url = url.strip()
    if not url:
        raise HTTPException(422, "Paste a careers page or job board link")
    if "://" not in url:
        url = "https://" + url
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    try:
        found = boards.detect(url)
        if not found:
            found = boards.detect_from_page(fetcher.page(url))
        if not found:
            raise HTTPException(
                422,
                "No Greenhouse, Lever or Ashby board found on that page. "
                "You can still track the company for news.",
            )
        board, slug = found
        jobs = boards.fetch_jobs(fetcher, board, slug)
    except FetchError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        if own:
            fetcher.close()
    teams: dict[str, int] = {}
    for j in jobs:
        teams[j.team] = teams.get(j.team, 0) + 1
    top = sorted(teams.items(), key=lambda kv: -kv[1])[:8]
    return {"board": board, "board_slug": slug, "jobs": len(jobs), "top_teams": top}


@router.post("/detect")
def detect(body: DetectIn) -> dict:
    return detect_board(body.url)


def _validate_board(board: str, slug: str) -> None:
    if board and board not in boards.BOARDS:
        raise HTTPException(422, f"board must be one of {', '.join(boards.BOARDS)}")
    if bool(board) != bool(slug):
        raise HTTPException(422, "Set both board and board_slug, or neither")


def _summaries(db: Session) -> dict[int, dict]:
    apps = dict(
        db.execute(
            select(Application.company_id, func.count()).group_by(Application.company_id)
        ).all()
    )
    unread = dict(
        db.execute(
            select(Signal.company_id, func.count())
            .where(Signal.read.is_(False), Signal.relevant.is_(True))
            .group_by(Signal.company_id)
        ).all()
    )
    mood: dict[int, dict] = {}
    for cid, sentiment, n in db.execute(
        select(Signal.company_id, Signal.sentiment, func.count())
        .where(Signal.relevant.is_(True))
        .group_by(Signal.company_id, Signal.sentiment)
    ):
        mood.setdefault(cid, {"bullish": 0, "bearish": 0, "neutral": 0})[sentiment] = n
    latest = {}
    for cid, total in db.execute(
        select(JobSnapshot.company_id, JobSnapshot.total).order_by(JobSnapshot.taken_at)
    ):
        latest[cid] = total
    return {
        cid: {
            "applications": apps.get(cid, 0),
            "unread": unread.get(cid, 0),
            "sentiment": mood.get(cid, {"bullish": 0, "bearish": 0, "neutral": 0}),
            "open_roles": latest.get(cid),
        }
        for cid in set(apps) | set(unread) | set(mood) | set(latest)
    }


def _empty_summary() -> dict:
    return {
        "applications": 0,
        "unread": 0,
        "sentiment": {"bullish": 0, "bearish": 0, "neutral": 0},
        "open_roles": None,
    }


@router.get("")
def list_companies(db: Session = Depends(get_db)) -> list[dict]:
    summaries = _summaries(db)
    rows = db.scalars(select(Company).order_by(func.lower(Company.name)))
    return [company_dict(c, summaries.get(c.id) or _empty_summary()) for c in rows]


def get_or_404(db: Session, company_id: int) -> Company:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    return c


def _name_taken(db: Session, name: str, not_id: int | None = None) -> bool:
    q = select(Company.id).where(func.lower(Company.name) == name.lower())
    if not_id:
        q = q.where(Company.id != not_id)
    return db.scalar(q) is not None


@router.post("", status_code=201)
def create_company(body: CompanyIn, db: Session = Depends(get_db)) -> dict:
    name = body.name.strip()
    if _name_taken(db, name):
        raise HTTPException(409, f"{name} is already tracked")
    board, slug = body.board, body.board_slug.strip()
    if not board and body.careers_url:
        found = boards.detect(body.careers_url)
        if found:
            board, slug = found
    _validate_board(board, slug)
    c = Company(
        name=name,
        careers_url=body.careers_url.strip(),
        board=board,
        board_slug=slug,
        news_query=body.news_query.strip(),
    )
    db.add(c)
    db.commit()
    return company_dict(c, _empty_summary())


@router.get("/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db)) -> dict:
    c = get_or_404(db, company_id)
    snaps = db.scalars(
        select(JobSnapshot)
        .where(JobSnapshot.company_id == c.id)
        .order_by(JobSnapshot.taken_at)
        .limit(90)
    ).all()
    latest = snaps[-1] if snaps else None
    teams = sorted((latest.by_team if latest else {}).items(), key=lambda kv: -kv[1])
    return company_dict(c, _summaries(db).get(c.id) or _empty_summary()) | {
        "trend": [{"at": s.taken_at.isoformat() + "Z", "total": s.total} for s in snaps],
        "teams": teams,
    }


@router.patch("/{company_id}")
def update_company(company_id: int, body: CompanyPatch, db: Session = Depends(get_db)) -> dict:
    c = get_or_404(db, company_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        data["name"] = data["name"].strip()
        if _name_taken(db, data["name"], c.id):
            raise HTTPException(409, f"{data['name']} is already tracked")
    board = data.get("board", c.board) or ""
    slug = (data.get("board_slug", c.board_slug) or "").strip()
    _validate_board(board, slug)
    if (board, slug) != (c.board, c.board_slug):
        # A different board: the old snapshots would diff against the wrong list
        for s in list(c.snapshots):
            db.delete(s)
    for k, v in data.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    c.board, c.board_slug = board, slug
    db.commit()
    return company_dict(c, _summaries(db).get(c.id) or _empty_summary())


@router.delete("/{company_id}", status_code=204)
def delete_company(company_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(get_or_404(db, company_id))
    db.commit()


@router.post("/{company_id}/scan", status_code=202)
def scan_company(company_id: int, db: Session = Depends(get_db)) -> dict:
    from app.tasks import start_run

    get_or_404(db, company_id)
    return {"run_id": start_run("manual", [company_id])}
