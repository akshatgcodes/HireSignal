"""Celery: the nightly scan and the morning digest.

    worker:  celery -A app.tasks worker --concurrency 4
    beat:    celery -A app.tasks beat

nightly_scan opens a Run, then fans out one scan_company task per company and joins them
with a chord, so finish_run writes the run's stats once every company is done. Companies
are scanned in parallel; the per-host spacing in app.http keeps each site at one request
every couple of seconds no matter how many workers there are.
"""

import logging

from celery import Celery, chord
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app import digest, pipeline
from app.config import settings
from app.db import SessionLocal
from app.models import Company, Run, utcnow

log = logging.getLogger("hiresignal.tasks")

broker = settings.redis_url or "memory://"
celery = Celery("hiresignal", broker=broker, backend=settings.redis_url or "cache+memory://")
celery.conf.update(
    timezone=settings.timezone,
    task_always_eager=settings.celery_always_eager,
    task_eager_propagates=True,
    task_acks_late=True,  # a worker killed mid-scan hands the company to another worker
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "nightly-scan": {
            "task": "hiresignal.nightly_scan",
            "schedule": crontab(hour=settings.scan_hour, minute=0),
        },
        "morning-digest": {
            "task": "hiresignal.send_digest",
            "schedule": crontab(hour=settings.digest_hour, minute=0),
        },
    },
)


def start_run(trigger: str, company_ids: list[int] | None = None) -> int:
    """Creates the Run row and queues the scans. Returns the run id."""
    with SessionLocal() as db:
        ids = company_ids or list(db.scalars(select(Company.id).order_by(Company.id)))
        run = Run(trigger=trigger, stats={"companies": len(ids)})
        db.add(run)
        db.commit()
        run_id = run.id
    if not ids:
        finish_run.delay([], run_id)
    else:
        chord(scan_company.s(cid) for cid in ids)(finish_run.s(run_id))
    return run_id


@celery.task(name="hiresignal.nightly_scan")
def nightly_scan() -> int:
    return start_run("schedule")


@celery.task(
    name="hiresignal.scan_company",
    autoretry_for=(OperationalError,),  # DB hiccups; HTTP retries happen inside the fetcher
    retry_backoff=30,
    max_retries=3,
)
def scan_company(company_id: int) -> dict:
    with SessionLocal() as db:
        try:
            return pipeline.scan_company(db, company_id)
        except OperationalError:
            raise
        except Exception as e:  # noqa: BLE001 — one company must not sink the chord
            log.exception("scan of company %s failed", company_id)
            return {"company_id": company_id, "error": f"{type(e).__name__}: {e}"}


@celery.task(name="hiresignal.finish_run")
def finish_run(results: list[dict], run_id: int) -> None:
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if run is None:
            return
        failed = [r for r in results if r.get("error")]
        run.stats = {
            "companies": len(results),
            "failed": len(failed),
            "new_signals": sum(
                r.get("hiring_signals", 0) + r.get("news_signals", 0) for r in results
            ),
            "results": results,
        }
        run.status = "failed" if results and len(failed) == len(results) else "done"
        run.finished_at = utcnow()
        db.commit()


@celery.task(name="hiresignal.send_digest")
def send_digest() -> int | None:
    with SessionLocal() as db:
        d = digest.build(db, "schedule")
        return d.id if d else None
