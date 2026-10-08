import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(service: str, settings: Settings) -> None:
    """Log to the console and to <storage>/logs/<service>.log.

    The files are what the admin console shows, including when the service
    that wrote them is down.
    """
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.logs_dir / f"{service}.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO, format=_FORMAT, handlers=[logging.StreamHandler(), file_handler],
        force=True,
    )
    # One line per HTTP request of the model downloads would drown everything else.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # uvicorn does not propagate to the root logger: attach its errors
    # (startup, crashes, unhandled exceptions) to the file as well.
    logging.getLogger("uvicorn.error").addHandler(file_handler)
