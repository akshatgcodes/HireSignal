"""Scanning one company: job board → snapshot → hiring signals, news → LLM → news signals.

The two halves fail independently. A board that 404s still lets the news through, and
the error is kept on the company so the UI can say what went wrong.
"""

import logging
import time

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import classify, signals
from app.http import Fetcher, FetchError
from app.models import Company, JobSnapshot, Signal, utcnow
from app.sources import boards, news

log = logging.getLogger("hiresignal.pipeline")

KEEP_FULL_SNAPSHOTS = 2  # older snapshots keep their counts but drop the job list


def _add(db: Session, company: Company, existing: set[str], **fields) -> bool:
    if fields["external_id"] in existing:
        return False
    existing.add(fields["external_id"])
    db.add(Signal(company_id=company.id, **fields))
    return True


def scan_jobs(db: Session, company: Company, fetcher: Fetcher, existing: set[str]) -> dict:
    jobs = boards.fetch_jobs(fetcher, company.board, company.board_slug)
    cur = {j.id: {k: v for k, v in j.to_dict().items() if k != "id"} for j in jobs}
    by_team: dict[str, int] = {}
    for j in jobs:
        by_team[j.team] = by_team.get(j.team, 0) + 1

    prev_snap = db.scalars(
        select(JobSnapshot)
        .where(JobSnapshot.company_id == company.id)
        .order_by(JobSnapshot.taken_at.desc(), JobSnapshot.id.desc())
        .limit(1)
    ).first()
    now = utcnow()
    drafts = signals.diff(
        company.name,
        prev_snap.jobs if prev_snap else None,
        cur,
        list(company.applications),
        now.date().isoformat(),
    )
    db.add(
        JobSnapshot(company_id=company.id, taken_at=now, total=len(jobs), by_team=by_team, jobs=cur)
    )
    db.flush()
    # Only the newest snapshots need the full job list (to diff against)
    old = db.scalars(
        select(JobSnapshot.id)
        .where(JobSnapshot.company_id == company.id)
        .order_by(JobSnapshot.taken_at.desc(), JobSnapshot.id.desc())
        .offset(KEEP_FULL_SNAPSHOTS)
    ).all()
    if old:
        db.execute(update(JobSnapshot).where(JobSnapshot.id.in_(old)).values(jobs={}))

    added = 0
    for d in drafts:
        added += _add(
            db,
            company,
            existing,
            source="hiring",
            kind=d.kind,
            sentiment=d.sentiment,
            title=d.title,
            explanation=d.explanation,
            url=d.url,
            publisher=company.board.capitalize(),
            external_id=d.external_id,
            classified_by="rule",
            published_at=now,
        )
    return {"jobs": len(jobs), "hiring_signals": added}


def scan_news(
    db: Session, company: Company, fetcher: Fetcher, existing: set[str], model=None
) -> dict:
    articles = news.fetch_news(fetcher, company.name, company.news_query)
    seen_titles = {
        news.title_key(t)
        for t in db.scalars(
            select(Signal.title).where(Signal.company_id == company.id, Signal.source == "news")
        )
    }
    # New to us by id and by headline (feeds re-post the same story under new ids)
    fresh = [
        a
        for a in articles
        if a.external_id not in existing and news.title_key(a.title) not in seen_titles
    ]
    roles = [f"{a.role}" + (f" ({a.team})" if a.team else "") for a in company.applications]
    verdicts, note = classify.classify(company.name, roles, fresh, model=model)
    added = 0
    for a, v in zip(fresh, verdicts, strict=True):
        # Off-topic headlines are stored too (hidden), so tomorrow's scan skips them
        new = _add(
            db,
            company,
            existing,
            source="news",
            kind=v.kind if v.relevant else "other",
            sentiment=v.sentiment if v.relevant else "neutral",
            title=a.title,
            explanation=v.explanation if v.relevant else "",
            url=a.url,
            publisher=a.publisher,
            external_id=a.external_id,
            classified_by=v.by,
            published_at=a.published_at,
            relevant=v.relevant,
        )
        added += new and v.relevant
    return {"news_seen": len(articles), "news_new": len(fresh), "news_signals": added, "note": note}


def scan_company(db: Session, company_id: int, fetcher: Fetcher | None = None, model=None) -> dict:
    """Scans one company and commits. Returns stats for the run log."""
    company = db.get(Company, company_id)
    if company is None:
        return {"error": "company was deleted"}
    started = time.perf_counter()
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    existing = set(
        db.scalars(select(Signal.external_id).where(Signal.company_id == company.id)).all()
    )
    stats: dict = {"company": company.name}
    errors = []
    try:
        if company.board and company.board_slug:
            try:
                stats |= scan_jobs(db, company, fetcher, existing)
            except (FetchError, ValueError, KeyError, TypeError) as e:
                db.rollback()
                existing = set(
                    db.scalars(select(Signal.external_id).where(Signal.company_id == company_id))
                )
                errors.append(f"job board: {e}")
        company = db.get(Company, company_id)
        try:
            stats |= scan_news(db, company, fetcher, existing, model=model)
        except FetchError as e:
            errors.append(f"news: {e}")
    finally:
        if own:
            fetcher.close()
    company = db.get(Company, company_id)
    company.last_scanned_at = utcnow()
    company.last_error = "; ".join(errors)
    db.commit()
    stats["error"] = company.last_error
    stats["ms"] = round((time.perf_counter() - started) * 1000)
    log.info("scanned %s: %s", company.name, stats)
    return stats
