import hmac
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.config import Settings
from app.formats import ALLOWED_OUTPUTS, INPUT_EXTENSIONS, RESULT_FILES, OutputFormat
from app.pipeline import JobRunner, Pipeline
from app.store import DONE, FAILED, JobStore, UPLOADED
from app.transcription import get_transcriber
from app.transcription.base import Transcriber

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"


class ProcessRequest(BaseModel):
    output_format: OutputFormat


def _public(job: dict) -> dict:
    keys = ("id", "filename", "input_kind", "output_format", "status", "error",
            "created_at", "finished_at")
    return {k: job[k] for k in keys}


def create_app(settings: Settings | None = None,
               transcriber_factory: Callable[[], Transcriber] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    store = JobStore(settings.db_path)
    pipeline = Pipeline(store, transcriber_factory or (lambda: get_transcriber(settings)))
    runner = JobRunner(pipeline, settings.workers)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Crash recovery: resume jobs that were queued or running when the service stopped.
        for job in store.list_unfinished():
            runner.submit(job["id"])
        yield
        runner.shutdown()

    app = FastAPI(title="Subtitle application", lifespan=lifespan)

    def require_admin(x_admin_token: str = Header(default="")) -> None:
        if settings.admin_token and not hmac.compare_digest(x_admin_token, settings.admin_token):
            raise HTTPException(401, "Invalid admin token")

    def get_job(job_id: str) -> dict:
        job = store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/jobs", status_code=201)
    async def upload(file: UploadFile):
        ext = Path(file.filename or "").suffix.lower()
        kind = INPUT_EXTENSIONS.get(ext)
        if kind is None:
            raise HTTPException(415, f"Unsupported file type. Allowed: {sorted(INPUT_EXTENSIONS)}")

        job_id = uuid.uuid4().hex
        job_dir = settings.jobs_dir / job_id
        job_dir.mkdir(parents=True)
        input_path = job_dir / f"input{ext}"
        max_bytes, size = settings.max_upload_mb * 1024 * 1024, 0
        with input_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    out.close()
                    input_path.unlink()
                    job_dir.rmdir()
                    raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")
                out.write(chunk)

        store.create(job_id, Path(file.filename).name, kind.value, input_path)
        return {"id": job_id, "input_kind": kind.value,
                "allowed_outputs": sorted(o.value for o in ALLOWED_OUTPUTS[kind])}

    @app.post("/jobs/{job_id}/process", status_code=202)
    def process(job_id: str, request: ProcessRequest):
        job = get_job(job_id)
        kind = INPUT_KIND_BY_VALUE[job["input_kind"]]
        if request.output_format not in ALLOWED_OUTPUTS[kind]:
            raise HTTPException(422, f"'{request.output_format.value}' is not available for {kind.value} input")
        if job["status"] not in (UPLOADED, FAILED):
            raise HTTPException(409, f"Job is already {job['status']}")
        store.queue(job_id, request.output_format.value)
        runner.submit(job_id)
        return _public(store.get(job_id))

    @app.get("/jobs/{job_id}")
    def status(job_id: str):
        return _public(get_job(job_id))

    @app.get("/jobs/{job_id}/result")
    def download(job_id: str):
        job = get_job(job_id)
        if job["status"] != DONE:
            raise HTTPException(409, f"Job is {job['status']}")
        result_path = Path(job["result_path"])
        media_type = RESULT_FILES[OutputFormat(job["output_format"])][1]
        name = f"{Path(job['filename']).stem}{result_path.suffix}"
        return FileResponse(result_path, media_type=media_type, filename=name)

    @app.get("/jobs/{job_id}/preview", response_class=PlainTextResponse)
    def preview(job_id: str):
        """Result as text, to read it in the UI without downloading (subtitles / text only)."""
        job = get_job(job_id)
        if job["status"] != DONE:
            raise HTTPException(409, f"Job is {job['status']}")
        if OutputFormat(job["output_format"]) not in (OutputFormat.SUBTITLES, OutputFormat.TEXT):
            raise HTTPException(422, "Preview is only available for text and subtitle results")
        return Path(job["result_path"]).read_text(encoding="utf-8")

    @app.get("/admin/metrics", dependencies=[Depends(require_admin)])
    def metrics():
        return store.stats()

    @app.get("/admin/responses", dependencies=[Depends(require_admin)])
    def responses(limit: int = 50):
        return store.list_responses(min(max(limit, 1), 500))

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


INPUT_KIND_BY_VALUE = {k.value: k for k in set(INPUT_EXTENSIONS.values())}
