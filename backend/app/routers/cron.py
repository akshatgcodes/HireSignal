"""Scheduled jobs for hosts that can't run Celery beat and a worker (free tiers usually
can't). Any outside scheduler (GitHub Actions, cron-job.org) can POST here with the
X-Cron-Secret header. With CELERY_ALWAYS_EAGER the scan runs inside the request."""

import secrets

from fastapi import APIRouter, Header, HTTPException

from app import digest
from app.config import settings
from app.db import SessionLocal

router = APIRouter(prefix="/api/cron", tags=["cron"])


def _check(secret: str | None) -> None:
    if not settings.cron_secret:
        raise HTTPException(404, "Not found")  # off unless configured
    if not secret or not secrets.compare_digest(secret.encode(), settings.cron_secret.encode()):
        raise HTTPException(401, "Bad cron secret")


@router.post("/scan", status_code=202)
def cron_scan(x_cron_secret: str | None = Header(default=None)) -> dict:
    _check(x_cron_secret)
    from app.tasks import start_run

    return {"run_id": start_run("schedule")}


@router.post("/digest")
def cron_digest(x_cron_secret: str | None = Header(default=None)) -> dict:
    _check(x_cron_secret)
    with SessionLocal() as db:
        d = digest.build(db, "schedule")
        return {"digest_id": d.id if d else None}
