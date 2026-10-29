from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import require_owner
from app.db import get_db
from app.models import STATUSES, Application, Company, utcnow
from app.serialize import application_dict

router = APIRouter(
    prefix="/api/applications", tags=["applications"], dependencies=[Depends(require_owner)]
)

FOLLOW_UP_AFTER = {"applied": 7, "interview": 3}  # default nudge, in days


class ApplicationIn(BaseModel):
    company_id: int | None = None
    company_name: str = Field(default="", max_length=120)  # creates the company if new
    role: str = Field(min_length=1, max_length=200)
    team: str = Field(default="", max_length=120)
    job_url: str = Field(default="", max_length=500)
    status: str = "applied"
    applied_on: date | None = None
    follow_up_on: date | None = None
    notes: str = Field(default="", max_length=10000)


class ApplicationPatch(BaseModel):
    role: str | None = Field(default=None, min_length=1, max_length=200)
    team: str | None = Field(default=None, max_length=120)
    job_url: str | None = Field(default=None, max_length=500)
    applied_on: date | None = None
    follow_up_on: date | None = None
    notes: str | None = Field(default=None, max_length=10000)


class MoveIn(BaseModel):
    status: str
    index: int = Field(ge=0)


def _status(s: str) -> str:
    if s not in STATUSES:
        raise HTTPException(422, f"status must be one of {', '.join(STATUSES)}")
    return s


def _column(db: Session, status: str, skip: int | None = None) -> list[Application]:
    q = select(Application).where(Application.status == status)
    if skip is not None:
        q = q.where(Application.id != skip)
    return list(db.scalars(q.order_by(Application.position, Application.id)))


def _get(db: Session, app_id: int) -> Application:
    a = db.get(Application, app_id, options=[joinedload(Application.company)])
    if not a:
        raise HTTPException(404, "Application not found")
    return a


@router.get("")
def list_applications(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(Application)
        .options(joinedload(Application.company))
        .order_by(Application.status, Application.position, Application.id)
    )
    return [application_dict(a) for a in rows]


@router.post("", status_code=201)
def create_application(body: ApplicationIn, db: Session = Depends(get_db)) -> dict:
    status = _status(body.status)
    if body.company_id:
        company = db.get(Company, body.company_id)
        if not company:
            raise HTTPException(404, "Company not found")
    else:
        name = body.company_name.strip()
        if not name:
            raise HTTPException(422, "Pick a company or type a new one")
        company = db.scalar(select(Company).where(func.lower(Company.name) == name.lower()))
        if company is None:
            company = Company(name=name)
            db.add(company)
            db.flush()
    applied_on = body.applied_on or date.today()
    follow = body.follow_up_on
    if follow is None and status in FOLLOW_UP_AFTER:
        follow = applied_on + timedelta(days=FOLLOW_UP_AFTER[status])
    top = db.scalar(select(func.min(Application.position)).where(Application.status == status))
    a = Application(
        company_id=company.id,
        role=body.role.strip(),
        team=body.team.strip(),
        job_url=body.job_url.strip(),
        status=status,
        applied_on=applied_on,
        follow_up_on=follow,
        notes=body.notes,
        position=(top - 1) if top is not None else 0,  # new cards go on top
    )
    db.add(a)
    db.commit()
    return application_dict(_get(db, a.id))


@router.patch("/{app_id}")
def update_application(app_id: int, body: ApplicationPatch, db: Session = Depends(get_db)) -> dict:
    a = _get(db, app_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if k == "role" and v is None:
            continue
        setattr(a, k, v.strip() if isinstance(v, str) and k != "notes" else v)
    db.commit()
    return application_dict(a)


@router.post("/{app_id}/move")
def move_application(app_id: int, body: MoveIn, db: Session = Depends(get_db)) -> dict:
    """Drops the card at `index` in the `status` column and renumbers that column."""
    a = _get(db, app_id)
    status = _status(body.status)
    if status != a.status:
        a.status = status
        a.status_changed_at = utcnow()
        # A new stage gets a fresh nudge; offers and rejections don't need one
        days = FOLLOW_UP_AFTER.get(status)
        a.follow_up_on = date.today() + timedelta(days=days) if days else None
    col = _column(db, status, skip=a.id)
    col.insert(min(body.index, len(col)), a)
    for i, card in enumerate(col):
        card.position = i
    db.commit()
    return application_dict(a)


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get(db, app_id))
    db.commit()
