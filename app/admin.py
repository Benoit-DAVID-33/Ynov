"""Admin console: `uvicorn app.admin:create_app --factory --port 8001`.

A separate service on its own port, with its own login. It keeps working when
the user-facing API, the workers or even the database are down, which is when
the logs and the service status are needed most.
"""

import logging
import shutil
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import auth
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
_LOG_TAIL_BYTES = 256 * 1024

# Sessions are in the database (table auth_sessions). Those validated here are also
# remembered in memory, so that an administrator already logged in keeps the logs and
# the service status during a database outage, which is when they are needed most.
_known_sessions: dict[str, float] = {}  # token -> expiry
_db_ready = False


class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


def _database_available(settings: Settings) -> bool:
    """Connect lazily: the console must start even when the database is down."""
    global _db_ready
    if not _db_ready:
        try:
            init_db(settings.database_url)
            with session_scope() as session:
                auth.ensure_admin(session, settings)
            _db_ready = True
        except Exception:
            log.warning("database unavailable", exc_info=True)
    return _db_ready


def require_session(
    admin_session: str = Cookie(default=""), settings: Settings = Depends(get_settings)
) -> None:
    now = time.time()
    if _database_available(settings):
        try:
            with session_scope() as session:
                user = auth.user_for_token(session, admin_session, auth.ROLE_ADMIN)
        except SQLAlchemyError:
            log.warning("session check: database error", exc_info=True)
        else:
            if user is None:
                _known_sessions.pop(admin_session, None)
                raise HTTPException(401, "Connexion requise")
            _known_sessions.setdefault(admin_session, now + _SESSION_S)
            return
    if _known_sessions.get(admin_session, 0) > now:
        return
    raise HTTPException(401, "Connexion requise")


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
_login_limiter = auth.AttemptLimiter(limit=5, window_s=60)


@public.post("/login")
def login(
    body: LoginIn, request: Request, response: Response,
    settings: Settings = Depends(get_settings),
) -> dict:
    client = auth.client_address(request)
    if _login_limiter.blocked(client):
        raise HTTPException(429, "Trop de tentatives : réessayez dans une minute")
    if not _database_available(settings):
        raise HTTPException(503, "Base de données indisponible : connexion impossible")
    try:
        with session_scope() as session:
            user = auth.authenticate(session, body.username, body.password, role=auth.ROLE_ADMIN)
            token = auth.open_session(session, user, _SESSION_S)[0] if user else None
    except SQLAlchemyError as exc:
        log.warning("login: database error", exc_info=True)
        raise HTTPException(503, "Base de données indisponible : connexion impossible") from exc
    if token is None:
        _login_limiter.record(client)
        log.warning("failed admin login from %s", client)
        raise HTTPException(401, "Nom d'utilisateur ou mot de passe incorrect")

    _login_limiter.clear(client)
    _known_sessions[token] = time.time() + _SESSION_S
    response.set_cookie(
        _COOKIE, token, max_age=_SESSION_S, httponly=True, samesite="strict",
        secure=settings.cookie_secure or request.url.scheme == "https",
    )
    log.info("admin '%s' logged in from %s", user.username, client)
    return {"status": "ok"}


@private.post("/logout")
def logout(response: Response, admin_session: str = Cookie(default="")) -> dict:
    _known_sessions.pop(admin_session, None)
    try:
        with session_scope() as session:
            auth.close_session(session, admin_session)
    except SQLAlchemyError:
        log.warning("logout: database error", exc_info=True)
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
    # Try now, so that the first administrator exists (and a generated password is printed)
    # as soon as the console starts; if the database is not up yet, later requests retry.
    _database_available(settings)

    app = FastAPI(title="Subtitle application - admin", docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.include_router(public)
    app.include_router(private)
    app.mount("/shared", StaticFiles(directory=WEB_DIR / "shared"), name="shared")
    app.mount("/", StaticFiles(directory=WEB_DIR / "admin", html=True), name="web")
    log.info("admin console ready")
    return app
