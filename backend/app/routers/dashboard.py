from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import digest
from app.auth import require_owner
from app.config import settings
from app.db import get_db
from app.models import STATUSES, Application, Run, Signal, utcnow
from app.serialize import application_dict, run_dict

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(require_owner)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    by_status = dict(
        db.execute(select(Application.status, func.count()).group_by(Application.status)).all()
    )
    week = utcnow() - timedelta(days=7)
    mood = dict(
        db.execute(
            select(Signal.sentiment, func.count())
            .where(Signal.relevant.is_(True), Signal.found_at >= week)
            .group_by(Signal.sentiment)
        ).all()
    )
    unread = db.scalar(
        select(func.count()).where(Signal.read.is_(False), Signal.relevant.is_(True))
    )
    last_run = db.scalars(select(Run).order_by(Run.id.desc()).limit(1)).first()
    follow = digest.due_follow_ups(db, digest.today())
    total = sum(by_status.values())
    responded = by_status.get("interview", 0) + by_status.get("offer", 0)
    return {
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "response_rate": round(responded / total, 3) if total else None,
        "signals_7d": {s: mood.get(s, 0) for s in ("bullish", "bearish", "neutral")},
        "unread": unread,
        "follow_ups_due": [application_dict(a) for a in follow],
        "last_run": run_dict(last_run) if last_run else None,
        "schedule": {
            "timezone": settings.timezone,
            "scan_hour": settings.scan_hour,
            "digest_hour": settings.digest_hour,
            "emails_to": settings.digest_to if settings.smtp_host else "",
        },
        "llm": settings.llm_model if settings.llm_key else "",
    }


@router.get("/follow-ups")
def follow_ups(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Application)
        .options(joinedload(Application.company))
        .where(Application.follow_up_on.is_not(None), Application.status.in_(digest.ACTIVE))
        .order_by(Application.follow_up_on)
    )
    return [application_dict(a) for a in rows]
