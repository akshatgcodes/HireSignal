from app.models import Application, Company, Run, Signal


def iso(dt) -> str | None:
    # Stored as naive UTC
    return dt.isoformat() + "Z" if dt else None


def company_dict(c: Company, extra: dict | None = None) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "board": c.board,
        "board_slug": c.board_slug,
        "careers_url": c.careers_url,
        "news_query": c.news_query,
        "last_scanned_at": iso(c.last_scanned_at),
        "last_error": c.last_error,
    } | (extra or {})


def application_dict(a: Application) -> dict:
    return {
        "id": a.id,
        "company_id": a.company_id,
        "company": a.company.name,
        "role": a.role,
        "team": a.team,
        "job_url": a.job_url,
        "status": a.status,
        "applied_on": a.applied_on.isoformat(),
        "follow_up_on": a.follow_up_on.isoformat() if a.follow_up_on else None,
        "notes": a.notes,
        "position": a.position,
        "status_changed_at": iso(a.status_changed_at),
    }


def signal_dict(s: Signal) -> dict:
    return {
        "id": s.id,
        "company_id": s.company_id,
        "company": s.company.name,
        "source": s.source,
        "kind": s.kind,
        "sentiment": s.sentiment,
        "title": s.title,
        "explanation": s.explanation,
        "url": s.url,
        "publisher": s.publisher,
        "classified_by": s.classified_by,
        "published_at": iso(s.published_at),
        "found_at": iso(s.found_at),
        "read": s.read,
    }


def run_dict(r: Run) -> dict:
    return {
        "id": r.id,
        "trigger": r.trigger,
        "status": r.status,
        "started_at": iso(r.started_at),
        "finished_at": iso(r.finished_at),
        "stats": r.stats,
    }
