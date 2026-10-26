"""User-facing HTTP API + web UI: `uvicorn app.api:create_app --factory`.

The admin console is a separate service, see app/admin.py.
"""

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth, jobs, media, retention
from app.auth import current_user, current_user_id
from app.config import Settings, get_settings
from app.db import get_session, init_db
from app.domain import ALLOWED_OUTPUTS, EXTENSIONS, JobStatus, MediaKind, OutputType
from app.logs import setup_logging
from app.models import Job, Upload, UploadSession, User, new_id, utcnow
from app.pipeline import delivered_language
from app.transcription import registered_transcribers
from app.translation import available_targets

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_CHUNK = 1024 * 1024
# One chunk is appended at a time: the offset check and the write must not interleave.
_append_lock = threading.Lock()

log = logging.getLogger("api")


class CredentialsIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class UserOut(BaseModel):
    username: str
    role: str


class UploadOut(BaseModel):
    id: str
    filename: str
    kind: MediaKind
    size_bytes: int
    duration_s: float | None
    allowed_outputs: list[OutputType]


class UploadSessionIn(BaseModel):
    filename: str = Field(max_length=255)
    size_bytes: int = Field(gt=0)


class UploadSessionOut(BaseModel):
    id: str
    size_bytes: int
    received_bytes: int
    chunk_bytes: int


class SubtitleStyle(BaseModel):
    """Look of the subtitles burned into the picture (video_embedded only)."""

    size: Literal["small", "medium", "large"] = "medium"
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9a-fA-F]{6}$")


class JobIn(BaseModel):
    upload_id: str
    output_type: OutputType
    model: str | None = None
    # Language to translate the result into; None keeps the spoken language.
    translate_to: str | None = None
    subtitle_style: SubtitleStyle | None = None


class ArtifactOut(BaseModel):
    name: str
    media_type: str
    primary: bool


class JobOut(BaseModel):
    id: str
    upload_id: str
    filename: str
    input_kind: MediaKind
    output_type: OutputType
    model: str
    target_language: str | None
    status: JobStatus
    stage: str | None
    progress: int
    error: str | None
    queue_position: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    compute_s: float | None
    duration_s: float | None
    artifacts: list[ArtifactOut]


class SegmentOut(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None


class SegmentsIn(BaseModel):
    """Corrected text of each subtitle, in order; timings are kept."""

    texts: list[Annotated[str, Field(max_length=500)]]


class TranscriptOut(BaseModel):
    job_id: str
    language: str
    source_language: str
    text: str
    segments: list[SegmentOut]


def job_fields(session: Session, job: Job) -> dict:
    return {
        "id": job.id,
        "upload_id": job.upload_id,
        "filename": job.upload.filename,
        "input_kind": job.upload.kind,
        "output_type": job.output_type,
        "model": job.model,
        "target_language": job.target_language,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "error": job.error,
        "queue_position": jobs.queue_position(session, job),
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "compute_s": job.compute_s,
        "duration_s": job.upload.duration_s,
        "artifacts": job.artifacts or [],
    }


def _is_owner(upload: Upload, owner_id: str) -> bool:
    return upload.owner_id == owner_id


def _own_upload(session: Session, upload_id: str, owner_id: str) -> Upload:
    upload = session.get(Upload, upload_id)
    # Someone else's file answers like a missing one: identifiers reveal nothing.
    if upload is None or not _is_owner(upload, owner_id):
        raise HTTPException(404, "Fichier introuvable")
    return upload


def _own_job(session: Session, job_id: str, owner_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or not _is_owner(job.upload, owner_id):
        raise HTTPException(404, "Traitement introuvable")
    return job


def _own_done_job(session: Session, job_id: str, owner_id: str) -> Job:
    job = _own_job(session, job_id, owner_id)
    if job.status != JobStatus.DONE.value:
        raise HTTPException(409, f"Résultat indisponible (statut : {job.status})")
    return job


def _artifact_response(job: Job, artifact: dict, settings: Settings, inline: bool) -> FileResponse:
    path = settings.results_dir / job.id / artifact["name"]
    if not path.is_file():
        raise HTTPException(410, "Fichier résultat supprimé")
    return FileResponse(
        path,
        media_type=artifact["media_type"],
        filename=f"{Path(job.upload.filename).stem}-{artifact['name']}",
        content_disposition_type="inline" if inline else "attachment",
    )


def _delivered_segments(job: Job) -> list[dict]:
    return job.edited_segments or job.translated_segments or job.segments


def _upload_fields(upload: Upload) -> UploadOut:
    kind = MediaKind(upload.kind)
    return UploadOut(
        id=upload.id, filename=upload.filename, kind=kind, size_bytes=upload.size_bytes,
        duration_s=upload.duration_s, allowed_outputs=ALLOWED_OUTPUTS[kind],
    )


def _minutes(seconds: float) -> int:
    return int(seconds // 60)


def _set_session_cookie(response: Response, request: Request, token: str, settings: Settings) -> None:
    response.set_cookie(
        auth.USER_COOKIE, token, max_age=int(settings.session_days * 24 * 3600), httponly=True,
        samesite="lax", secure=settings.cookie_secure or request.url.scheme == "https",
    )


def _check_extension(filename: str) -> tuple[str, MediaKind]:
    extension = Path(filename).suffix.lower()
    kind = EXTENSIONS.get(extension)
    if kind is None:
        raise HTTPException(415, "Format non supporté : seuls les fichiers .mp4 et .wav sont acceptés")
    return extension, kind


def _too_big(settings: Settings) -> HTTPException:
    return HTTPException(413, f"Fichier trop volumineux (maximum {settings.max_upload_mb} Mo)")


def _register_upload(
    session: Session, settings: Settings, upload_id: str, path: Path, filename: str,
    kind: MediaKind, owner_id: str,
) -> Upload:
    """Validate a fully received file and record it. The file is removed if refused."""
    duration = media.probe_duration(path)
    if duration is None or duration > settings.max_duration_s:
        path.unlink(missing_ok=True)
        if duration is None:
            raise HTTPException(422, "Fichier illisible : impossible de déterminer sa durée")
        raise HTTPException(
            413, f"Fichier trop long (maximum {_minutes(settings.max_duration_s)} min)"
        )
    upload = Upload(
        id=upload_id,
        filename=Path(filename).name[:255],
        kind=kind.value,
        path=str(path),
        size_bytes=path.stat().st_size,
        duration_s=duration,
        owner_id=owner_id,
    )
    session.add(upload)
    # Commit before answering: the client may use the id in its very next request.
    session.commit()
    log.info("upload %s received (%s, %d bytes, %.0fs)", upload.id, upload.filename,
             upload.size_bytes, duration)
    return upload


def _session_fields(upload_session: UploadSession, settings: Settings) -> dict:
    path = settings.partial_dir / f"{upload_session.id}.part"
    return {
        "id": upload_session.id,
        "size_bytes": upload_session.size_bytes,
        "received_bytes": path.stat().st_size if path.exists() else 0,
        "chunk_bytes": settings.upload_chunk_mb * 1024 * 1024,
    }


def _own_session(session: Session, session_id: str, owner_id: str) -> UploadSession:
    upload_session = session.get(UploadSession, session_id)
    if upload_session is None or upload_session.owner_id != owner_id:
        raise HTTPException(404, "Envoi introuvable ou expiré")
    return upload_session


def _queue_state(session: Session, settings: Settings) -> dict:
    pending = jobs.pending_media_s(session)
    return {
        "pending_media_s": pending,
        "max_pending_media_s": settings.max_pending_media_s,
        "accepting": pending < settings.max_pending_media_s,
    }


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
def config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "models": settings.model_names,
        "default_model": settings.effective_default_model,
        "translation_targets": available_targets(),
        "max_upload_mb": settings.max_upload_mb,
        "max_duration_s": settings.max_duration_s,
        "max_pending_jobs_per_visitor": settings.max_pending_jobs_per_visitor,
        "extensions": {ext: kind.value for ext, kind in EXTENSIONS.items()},
        "allowed_outputs": {
            kind.value: [o.value for o in outputs] for kind, outputs in ALLOWED_OUTPUTS.items()
        },
    }


@router.get("/queue")
def queue(session: Session = Depends(get_session), settings: Settings = Depends(get_settings)) -> dict:
    """Load of the processing queue; `accepting` is false when new jobs would be refused."""
    return _queue_state(session, settings)


@router.post("/auth/register", response_model=UserOut, status_code=201)
def register(
    body: CredentialsIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Open to everyone. The new account is logged in at once."""
    address = auth.client_address(request)
    if auth.registration_limiter.blocked(address):
        raise HTTPException(429, "Trop de créations de compte depuis cette adresse : réessayez plus tard")
    auth.registration_limiter.record(address)
    try:
        user = auth.create_user(session, body.username, body.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except auth.UsernameTaken as exc:
        raise HTTPException(409, "Ce nom d'utilisateur est déjà pris") from exc
    token, _ = auth.open_session(session, user, settings.session_days * 24 * 3600)
    session.commit()
    _set_session_cookie(response, request, token, settings)
    log.info("account '%s' created", user.username)
    return user


@router.post("/auth/login", response_model=UserOut)
def login(
    body: CredentialsIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    address = auth.client_address(request)
    if auth.login_limiter.blocked(address):
        raise HTTPException(429, "Trop de tentatives : réessayez dans une minute")
    user = auth.authenticate(session, body.username, body.password)
    if user is None:
        auth.login_limiter.record(address)
        log.warning("failed login from %s", address)
        raise HTTPException(401, "Nom d'utilisateur ou mot de passe incorrect")
    auth.login_limiter.clear(address)
    token, _ = auth.open_session(session, user, settings.session_days * 24 * 3600)
    session.commit()
    _set_session_cookie(response, request, token, settings)
    return user


@router.post("/auth/logout")
def logout(
    request: Request, response: Response, session: Session = Depends(get_session)
) -> dict:
    auth.close_session(session, request.cookies.get(auth.USER_COOKIE, ""))
    session.commit()
    response.delete_cookie(auth.USER_COOKIE)
    return {"status": "ok"}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/uploads", response_model=UploadOut, status_code=201)
def create_upload(
    file: UploadFile,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Upload a file in one request. For large files, prefer the resumable sessions below."""
    extension, kind = _check_extension(file.filename or "")
    upload_id = new_id()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"{upload_id}{extension}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(_CHUNK):
            size += len(chunk)
            if size > limit:
                break
            out.write(chunk)
    if size > limit or size == 0:
        dest.unlink(missing_ok=True)
        if size == 0:
            raise HTTPException(400, "Fichier vide")
        raise _too_big(settings)
    upload = _register_upload(session, settings, upload_id, dest, file.filename, kind, owner_id)
    return _upload_fields(upload)


@router.post("/uploads/sessions", response_model=UploadSessionOut, status_code=201)
def create_upload_session(
    body: UploadSessionIn,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Start a resumable upload: the file is then sent chunk by chunk.

    A visitor has one upload in progress at a time: starting a new one drops
    their unfinished ones.
    """
    _check_extension(body.filename)
    if body.size_bytes > settings.max_upload_mb * 1024 * 1024:
        raise _too_big(settings)
    for previous in session.scalars(select(UploadSession).where(UploadSession.owner_id == owner_id)):
        retention.drop_upload_session(session, previous, settings)
    upload_session = UploadSession(
        id=new_id(), owner_id=owner_id, filename=Path(body.filename).name,
        size_bytes=body.size_bytes,
    )
    session.add(upload_session)
    session.commit()
    return _session_fields(upload_session, settings)


@router.get("/uploads/sessions/{session_id}", response_model=UploadSessionOut)
def get_upload_session(
    session_id: str,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """How much has been received: where to resume after an interruption."""
    return _session_fields(_own_session(session, session_id, owner_id), settings)


@router.put("/uploads/sessions/{session_id}", response_model=UploadSessionOut)
def append_chunk(
    session_id: str,
    chunk: UploadFile,
    offset: int = Form(),
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Append the bytes starting at `offset`.

    If `offset` is not where the server stands (chunk already received, or one
    lost), nothing is written and the answer is 409 with the real position.
    """
    upload_session = _own_session(session, session_id, owner_id)
    data = chunk.file.read(2 * settings.upload_chunk_mb * 1024 * 1024 + 1)
    if len(data) > 2 * settings.upload_chunk_mb * 1024 * 1024:
        raise HTTPException(413, "Morceau trop volumineux")
    settings.partial_dir.mkdir(parents=True, exist_ok=True)
    path = settings.partial_dir / f"{upload_session.id}.part"
    with _append_lock:
        received = path.stat().st_size if path.exists() else 0
        if offset != received:
            return JSONResponse(_session_fields(upload_session, settings), status_code=409)
        if received + len(data) > upload_session.size_bytes:
            raise HTTPException(413, "Plus de données que la taille annoncée")
        with path.open("ab") as out:
            out.write(data)
    return _session_fields(upload_session, settings)


@router.post("/uploads/sessions/{session_id}/complete", response_model=UploadOut, status_code=201)
def complete_upload_session(
    session_id: str,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    upload_session = _own_session(session, session_id, owner_id)
    state = _session_fields(upload_session, settings)
    if state["received_bytes"] != upload_session.size_bytes:
        return JSONResponse(state, status_code=409)

    extension, kind = _check_extension(upload_session.filename)
    upload_id = new_id()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.uploads_dir / f"{upload_id}{extension}"
    (settings.partial_dir / f"{upload_session.id}.part").replace(dest)
    filename = upload_session.filename
    session.delete(upload_session)
    session.commit()
    upload = _register_upload(session, settings, upload_id, dest, filename, kind, owner_id)
    return _upload_fields(upload)


@router.get("/uploads/last")
def last_upload(owner_id: str = Depends(current_user_id), session: Session = Depends(get_session)) -> dict:
    """The visitor's latest file still on the server, with its jobs (newest first)."""
    upload = session.scalar(
        select(Upload)
        .where(
            Upload.owner_id == owner_id,
            Upload.purged_at.is_(None),
            Upload.delete_requested_at.is_(None),
        )
        .order_by(Upload.created_at.desc())
        .limit(1)
    )
    if upload is None:
        return {"upload": None, "jobs": []}
    history = session.scalars(
        select(Job).where(Job.upload_id == upload.id).order_by(Job.created_at.desc())
    )
    return {
        "upload": _upload_fields(upload),
        "jobs": [JobOut(**job_fields(session, job)) for job in history],
    }


@router.post("/jobs", response_model=JobOut, status_code=201)
def create_job(
    body: JobIn,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    upload = _own_upload(session, body.upload_id, owner_id)
    if upload.purged_at is not None or upload.delete_requested_at is not None:
        raise HTTPException(410, "Ce fichier a été supprimé du serveur : déposez-le à nouveau")
    if body.output_type not in ALLOWED_OUTPUTS[MediaKind(upload.kind)]:
        raise HTTPException(422, "Ce type de résultat n'est pas disponible pour un fichier audio")
    model = body.model or settings.effective_default_model
    if model not in settings.model_names or model not in registered_transcribers():
        raise HTTPException(422, f"Modèle inconnu : {model}")
    if body.translate_to and body.translate_to not in available_targets():
        raise HTTPException(422, f"Traduction indisponible vers : {body.translate_to}")

    if jobs.pending_count(session, owner_id) >= settings.max_pending_jobs_per_visitor:
        raise HTTPException(
            429,
            f"Vous avez déjà {settings.max_pending_jobs_per_visitor} traitements en attente ou en "
            "cours : attendez la fin de l'un d'eux ou annulez-le",
        )
    # An empty queue always accepts, so a single long file is never refused.
    pending = jobs.pending_media_s(session)
    if pending > 0 and pending + (upload.duration_s or 0) > settings.max_pending_media_s:
        log.warning("job refused: queue full (%.0fs of media pending)", pending)
        raise HTTPException(
            503, "Le service est saturé : réessayez dans quelques minutes",
            headers={"Retry-After": "60"},
        )

    options = None
    if body.subtitle_style and body.output_type is OutputType.VIDEO_EMBEDDED:
        options = {"subtitle_style": body.subtitle_style.model_dump()}
    job = jobs.create_job(session, upload, body.output_type, model, body.translate_to, options)
    session.commit()
    log.info("job %s queued (upload %s, %s)", job.id, upload.id, body.output_type.value)
    return job_fields(session, job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str, owner_id: str = Depends(current_user_id), session: Session = Depends(get_session)
):
    return job_fields(session, _own_job(session, job_id, owner_id))


@router.get("/jobs/{job_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    job_id: str, owner_id: str = Depends(current_user_id), session: Session = Depends(get_session)
):
    """Machine-readable result, e.g. to feed a translation service."""
    job = _own_done_job(session, job_id, owner_id)
    return {
        "job_id": job.id,
        "language": delivered_language(job.target_language, job.language),
        "source_language": job.language,
        "text": job.text,
        "segments": _delivered_segments(job),
    }


@router.put("/jobs/{job_id}/segments", response_model=JobOut)
def correct_segments(
    job_id: str,
    body: SegmentsIn,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    """Replace the text of the subtitles and rebuild the result files from it.

    The job goes back to the queue; only the file generation is redone, not
    the transcription. An empty text removes the subtitle.
    """
    job = _own_done_job(session, job_id, owner_id)
    if job.upload.purged_at is not None or job.upload.delete_requested_at is not None:
        raise HTTPException(410, "Ce fichier a été supprimé du serveur : déposez-le à nouveau")
    current = _delivered_segments(job)
    if len(body.texts) != len(current):
        raise HTTPException(422, f"{len(current)} sous-titres attendus, {len(body.texts)} reçus")
    edited = [
        {**segment, "text": " ".join(text.split())}
        for segment, text in zip(current, body.texts, strict=True)
    ]
    jobs.requeue_with_edits(session, job, edited)
    session.commit()
    log.info("job %s requeued with corrected subtitles", job.id)
    return job_fields(session, job)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str, owner_id: str = Depends(current_user_id), session: Session = Depends(get_session)
):
    job = _own_job(session, job_id, owner_id)
    if not jobs.cancel(session, job.id):
        raise HTTPException(409, f"Ce traitement n'est plus en cours (statut : {job.status})")
    session.commit()
    session.refresh(job)
    log.info("job %s cancelled by its owner", job.id)
    return job_fields(session, job)


@router.delete("/uploads/{upload_id}", status_code=204)
def delete_upload(
    upload_id: str,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete a file and its results now; its running jobs are cancelled."""
    upload = _own_upload(session, upload_id, owner_id)
    for job in session.scalars(select(Job).where(Job.upload_id == upload.id)):
        jobs.cancel(session, job.id)
    upload.delete_requested_at = utcnow()
    # If a worker still holds a file, the periodic purge finishes the job.
    retention.delete_files(session, upload, settings)
    session.commit()
    log.info("upload %s deleted by its owner", upload.id)


@router.get("/jobs/{job_id}/download")
def download(
    job_id: str,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    job = _own_done_job(session, job_id, owner_id)
    primary = next((a for a in job.artifacts if a["primary"]), None)
    if primary is None:
        raise HTTPException(410, "Fichier résultat supprimé")
    return _artifact_response(job, primary, settings, inline=False)


@router.get("/jobs/{job_id}/files/{name}")
def get_file(
    job_id: str,
    name: str,
    owner_id: str = Depends(current_user_id),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Individual result file, served inline for the preview."""
    job = _own_done_job(session, job_id, owner_id)
    artifact = next((a for a in job.artifacts if a["name"] == name), None)
    if artifact is None:
        raise HTTPException(404, "Fichier introuvable")
    return _artifact_response(job, artifact, settings, inline=True)


def create_app() -> FastAPI:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    setup_logging("api", settings)
    init_db(settings.database_url)
    auth.registration_limiter.limit = settings.max_registrations_per_hour

    app = FastAPI(title="Subtitle application", version="1.3.0")
    app.include_router(router)
    app.mount("/shared", StaticFiles(directory=WEB_DIR / "shared"), name="shared")
    app.mount("/", StaticFiles(directory=WEB_DIR / "user", html=True), name="web")
    log.info("api ready")
    return app
