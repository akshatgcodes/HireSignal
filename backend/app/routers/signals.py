from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.auth import require_owner
from app.db import get_db
from app.models import SENTIMENTS, Signal
from app.serialize import signal_dict

router = APIRouter(prefix="/api/signals", tags=["signals"], dependencies=[Depends(require_owner)])


@router.get("")
def list_signals(
    company_id: int | None = None,
    sentiment: str | None = None,
    source: str | None = None,
    unread: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    q = select(Signal).options(joinedload(Signal.company)).where(Signal.relevant.is_(True))
    if company_id:
        q = q.where(Signal.company_id == company_id)
    if sentiment:
        if sentiment not in SENTIMENTS:
            raise HTTPException(422, f"sentiment must be one of {', '.join(SENTIMENTS)}")
        q = q.where(Signal.sentiment == sentiment)
    if source:
        q = q.where(Signal.source == source)
    if unread:
        q = q.where(Signal.read.is_(False))
    # Newest finds first; within one scan, the newest article first
    q = q.order_by(Signal.found_at.desc(), Signal.published_at.desc(), Signal.id.desc())
    return [signal_dict(s) for s in db.scalars(q.limit(limit))]


@router.post("/{signal_id}/read")
def mark_read(signal_id: int, read: bool = True, db: Session = Depends(get_db)) -> dict:
    s = db.get(Signal, signal_id)
    if not s:
        raise HTTPException(404, "Signal not found")
    s.read = read
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(company_id: int | None = None, db: Session = Depends(get_db)) -> dict:
    q = update(Signal).where(Signal.read.is_(False))
    if company_id:
        q = q.where(Signal.company_id == company_id)
    n = db.execute(q.values(read=True)).rowcount
    db.commit()
    return {"updated": n}
