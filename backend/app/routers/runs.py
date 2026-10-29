from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import digest
from app.auth import require_owner
from app.db import get_db
from app.models import Digest, Run
from app.serialize import iso, run_dict

router = APIRouter(prefix="/api", tags=["runs"], dependencies=[Depends(require_owner)])


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)) -> list[dict]:
    return [run_dict(r) for r in db.scalars(select(Run).order_by(Run.id.desc()).limit(50))]


@router.post("/runs", status_code=202)
def scan_all() -> dict:
    from app.tasks import start_run

    return {"run_id": start_run("manual")}


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)) -> dict:
    r = db.get(Run, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return run_dict(r)


def _digest_dict(d: Digest) -> dict:
    return {
        "id": d.id,
        "created_at": iso(d.created_at),
        "trigger": d.trigger,
        "subject": d.subject,
        "signal_count": d.signal_count,
        "follow_ups": len(d.follow_ups),
        "emailed_to": d.emailed_to,
    }


@router.get("/digests")
def list_digests(db: Session = Depends(get_db)) -> list[dict]:
    return [
        _digest_dict(d) for d in db.scalars(select(Digest).order_by(Digest.id.desc()).limit(50))
    ]


@router.post("/digests")
def send_digest_now(db: Session = Depends(get_db)) -> dict:
    d = digest.build(db, "manual")
    if d is None:
        raise HTTPException(409, "Nothing new since the last digest, and no follow-ups due")
    return _digest_dict(d)


@router.get("/digests/{digest_id}")
def get_digest(digest_id: int, db: Session = Depends(get_db)) -> dict:
    d = db.get(Digest, digest_id)
    if not d:
        raise HTTPException(404, "Digest not found")
    return _digest_dict(d) | {"html": d.html}
