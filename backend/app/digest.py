"""The morning email: new signals since the last digest, plus follow-ups that are due."""

import html
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import mail
from app.config import settings
from app.models import Application, Digest, Signal

log = logging.getLogger("hiresignal.digest")

COLOR = {"bullish": "#15803d", "bearish": "#b91c1c", "neutral": "#57534e"}
ARROW = {"bullish": "▲", "bearish": "▼", "neutral": "●"}
ACTIVE = ("applied", "interview")


def today() -> date:
    return datetime.now(ZoneInfo(settings.timezone)).date()


def pending_signals(db: Session) -> list[Signal]:
    return list(
        db.scalars(
            select(Signal)
            .options(joinedload(Signal.company))
            .where(Signal.digest_id.is_(None), Signal.relevant.is_(True))
            .order_by(Signal.company_id, Signal.found_at.desc())
        )
    )


def due_follow_ups(db: Session, on: date) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .options(joinedload(Application.company))
            .where(
                Application.follow_up_on.is_not(None),
                Application.follow_up_on <= on,
                Application.status.in_(ACTIVE),
            )
            .order_by(Application.follow_up_on)
        )
    )


def render(sigs: list[Signal], follow: list[Application], on: date) -> tuple[str, str, str]:
    esc = html.escape
    n = len(sigs)
    parts = []
    if n:
        parts.append(f"{n} new signal{'s' if n != 1 else ''}")
    if follow:
        parts.append(f"{len(follow)} follow-up{'s' if len(follow) != 1 else ''} due")
    subject = "HireSignal: " + ", ".join(parts)

    text_lines, blocks = [], []
    if follow:
        text_lines.append("Follow up today")
        items = []
        for a in follow:
            late = (on - a.follow_up_on).days
            when = "today" if late == 0 else f"{late} day{'s' if late != 1 else ''} overdue"
            text_lines.append(f"  - {a.company.name}: {a.role} ({when})")
            items.append(
                f"<li><b>{esc(a.company.name)}</b>: {esc(a.role)} "
                f'<span style="color:#78716c">({when})</span></li>'
            )
        blocks.append(
            '<h2 style="font:600 15px sans-serif;margin:20px 0 6px">Follow up today</h2>'
            f'<ul style="font:14px/1.6 sans-serif;padding-left:18px">{"".join(items)}</ul>'
        )
    by_company: dict[str, list[Signal]] = {}
    for s in sigs:
        by_company.setdefault(s.company.name, []).append(s)
    for company, items in by_company.items():
        text_lines.append(f"\n{company}")
        rows = []
        for s in items:
            text_lines.append(f"  {ARROW[s.sentiment]} {s.title}\n    {s.explanation}")
            title = esc(s.title)
            if s.url:
                title = f'<a href="{esc(s.url)}" style="color:#1c1917">{title}</a>'
            color, arrow = COLOR[s.sentiment], ARROW[s.sentiment]
            rows.append(
                f'<div style="margin:0 0 12px;padding:8px 12px;border-left:3px solid {color}">'
                f'<div style="font:14px sans-serif"><span style="color:{color}">{arrow}</span> '
                f"{title}</div>"
                f'<div style="font:13px/1.5 sans-serif;color:#57534e;margin-top:3px">'
                f"{esc(s.explanation)}</div></div>"
            )
        blocks.append(
            f'<h2 style="font:600 15px sans-serif;margin:20px 0 8px">{esc(company)}</h2>'
            + "".join(rows)
        )
    text = "\n".join(text_lines) + f"\n\nOpen HireSignal: {settings.public_url}\n"
    body = (
        '<div style="max-width:600px;margin:0 auto;padding:24px;color:#1c1917">'
        f'<h1 style="font:600 20px sans-serif;margin:0">Your morning signals</h1>'
        f'<p style="font:13px sans-serif;color:#78716c;margin:4px 0 0">{on:%A, %d %B}</p>'
        + "".join(blocks)
        + f'<p style="font:13px sans-serif;margin-top:24px"><a href="{esc(settings.public_url)}">'
        "Open HireSignal</a></p></div>"
    )
    return subject, text, body


def build(db: Session, trigger: str, on: date | None = None) -> Digest | None:
    """Collects, saves and (if SMTP is set up) emails a digest. None if there's nothing."""
    on = on or today()
    sigs = pending_signals(db)
    follow = due_follow_ups(db, on)
    if not sigs and not follow:
        return None
    subject, text, body = render(sigs, follow, on)
    d = Digest(
        trigger=trigger,
        signal_count=len(sigs),
        follow_ups=[a.id for a in follow],
        subject=subject,
        html=body,
    )
    db.add(d)
    db.flush()
    for s in sigs:
        s.digest_id = d.id
    db.commit()
    if settings.digest_to and settings.smtp_host:
        try:
            mail.send(settings.digest_to, subject, text, body)
            d.emailed_to = settings.digest_to
            db.commit()
        except Exception:  # noqa: BLE001 — the digest is saved even if email fails
            log.exception("digest email failed")
    return d
