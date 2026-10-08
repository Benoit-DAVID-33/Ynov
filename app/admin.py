"""Admin console: `uvicorn app.admin:create_app --factory --port 8001`.

A separate service on its own port, with its own login. It keeps working when
the user-facing API, the workers or even the database are down, which is when
the logs and the service status are needed most.
"""

import logging
import secrets
import shutil
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select

from app.api import WEB_DIR, job_fields
from app.config import Settings, get_settings
from app.db import init_db, session_scope
from app.domain import JobStatus
from app.logs import setup_logging
from app.models import Job, Worker, utcnow
from app.stats import usage_stats

log = logging.getLogger("admin")

_COOKIE = "admin_session"
_SESSION_S = 8 * 3600
_MAX_FAILURES = 5
_LOCKOUT_S = 60
_LOG_TAIL_BYTES = 256 * 1024

# In memory on purpose: nothing to store, and a restart simply asks to log in again.
_sessions: dict[str, float] = {}
_failures: dict[str, tuple[int, float]] = {}  # client -> (count, locked until)
_db_ready = False


class LoginIn(BaseModel):
    password: str


def require_session(admin_session: str = Cookie(default="")) -> None:
    if _sessions.get(admin_session, 0) < time.time():
        _sessions.pop(admin_session, None)
        raise HTTPException(401, "Connexion requise")


def _database_available(settings: Settings) -> bool:
    """Connect lazily: the console must start even when the database is down."""
    global _db_ready
    if not _db_ready:
        try:
            init_db(settings.database_url)
            _db_ready = True
        except Exception:
            log.warning("database unavailable", exc_info=True)
    return _db_ready


def _api_status(settings: Settings) -> dict:
    try:
        with urllib.request.urlopen(f"{settings.api_url}/api/health", timeout=2) as response:
            return {"up": response.status == 200, "detail": None}
    except Exception as exc:
        return {"up": False, "detail": str(exc)}


def _log_path(settings: Settings, name: str) -> Path:
    # Only files listed in the logs directory: never a path built from the request.
    for path in settings.logs_dir.glob("*.log*"):
        if path.name == name:
            return path
    raise HTTPException(404, "Journal introuvable")


public = APIRouter(prefix="/api")
private = APIRouter(prefix="/api", dependencies=[Depends(require_session)])


@public.post("/login")
def login(
    body: LoginIn, request: Request, response: Response,
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.admin_password:
        raise HTTPException(503, "ADMIN_PASSWORD n'est pas configuré sur le serveur")
    client = request.client.host if request.client else "?"
    count, locked_until = _failures.get(client, (0, 0.0))
    if locked_until > time.time():
        raise HTTPException(429, "Trop de tentatives : réessayez dans une minute")
    if not secrets.compare_digest(body.password.encode(), settings.admin_password.encode()):
        count += 1
        _failures[client] = (count, time.time() + _LOCKOUT_S if count >= _MAX_FAILURES else 0.0)
        log.warning("failed admin login from %s", client)
        raise HTTPException(401, "Mot de passe incorrect")

    _failures.pop(client, None)
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time() + _SESSION_S
    response.set_cookie(_COOKIE, token, max_age=_SESSION_S, httponly=True, samesite="strict")
    log.info("admin logged in from %s", client)
    return {"status": "ok"}


@private.post("/logout")
def logout(response: Response, admin_session: str = Cookie(default="")) -> dict:
    _sessions.pop(admin_session, None)
    response.delete_cookie(_COOKIE)
    return {"status": "ok"}


@private.get("/overview")
def overview(settings: Settings = Depends(get_settings)) -> dict:
    """Service status and usage figures; each part degrades on its own."""
    disk = shutil.disk_usage(settings.storage_dir)
    result = {
        "api": _api_status(settings),
        "database": {"up": False, "detail": None},
        "workers": [],
        "disk": {"free_gb": disk.free / 1e9, "total_gb": disk.total / 1e9},
        "stats": None,
    }
    if not _database_available(settings):
        result["database"]["detail"] = "Connexion impossible"
        return result
    try:
        with session_scope() as session:
            alive_after = utcnow() - timedelta(seconds=settings.heartbeat_interval_s * 3)
            result["workers"] = [
                {"id": w.id, "device": w.device, "started_at": w.started_at, "heartbeat_at": w.heartbeat_at,
                 "up": w.heartbeat_at >= alive_after}
                for w in session.scalars(select(Worker).order_by(Worker.started_at))
            ]
            result["stats"] = usage_stats(session)
        result["database"]["up"] = True
    except Exception as exc:
        log.warning("overview: database error", exc_info=True)
        result["database"]["detail"] = str(exc)
    return result


@private.get("/jobs")
def list_jobs(
    status: JobStatus | None = None, limit: int = 100,
    settings: Settings = Depends(get_settings),
) -> list[dict]:
    if not _database_available(settings):
        raise HTTPException(503, "Base de données indisponible")
    query = select(Job).order_by(Job.created_at.desc()).limit(min(max(limit, 1), 500))
    if status is not None:
        query = query.where(Job.status == status.value)
    try:
        with session_scope() as session:
            return [
                {**job_fields(session, job), "attempts": job.attempts, "text": job.text}
                for job in session.scalars(query)
            ]
    except Exception as exc:
        log.warning("jobs: database error", exc_info=True)
        raise HTTPException(503, "Base de données indisponible") from exc


@private.get("/logs")
def list_logs(settings: Settings = Depends(get_settings)) -> list[dict]:
    files = sorted(settings.logs_dir.glob("*.log*")) if settings.logs_dir.is_dir() else []
    return [{"name": f.name, "size_bytes": f.stat().st_size, "modified_at": f.stat().st_mtime}
            for f in files]


@private.get("/logs/{name}")
def read_log(name: str, lines: int = 200, settings: Settings = Depends(get_settings)) -> dict:
    path = _log_path(settings, name)
    with path.open("rb") as stream:
        stream.seek(max(path.stat().st_size - _LOG_TAIL_BYTES, 0))
        tail = stream.read().decode("utf-8", errors="replace").splitlines()
    return {"name": name, "lines": tail[-min(max(lines, 1), 2000):]}


def create_app() -> FastAPI:
    global _db_ready
    _db_ready = False
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    setup_logging("admin", settings)

    app = FastAPI(title="Subtitle application - admin", docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.include_router(public)
    app.include_router(private)
    app.mount("/shared", StaticFiles(directory=WEB_DIR / "shared"), name="shared")
    app.mount("/", StaticFiles(directory=WEB_DIR / "admin", html=True), name="web")
    log.info("admin console ready")
    return app
