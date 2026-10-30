import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.config import settings
from app.db import Base, engine
from app.routers import applications, companies, cron, dashboard, runs, signals
from app.site import mount_site

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Small schema, so create_all on startup instead of a migration tool
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="HireSignal API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(applications.router)
app.include_router(signals.router)
app.include_router(runs.router)
app.include_router(dashboard.router)
app.include_router(cron.router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# Must come after every API route (see app/site.py)
if settings.site_dir:
    mount_site(app, settings.site_dir)
