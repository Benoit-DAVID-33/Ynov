"""Load test: N users submit the same file at the same time.

    python scripts/benchmark.py input.mp4 --users 10 --output-type video_embedded

Requirement: every job must finish in less time than the duration of the media,
i.e. the "x durée" column must stay below 1.

Each simulated user creates its own account (bench-<run>-<n>), so the server must allow
that many registrations from this address: MAX_REGISTRATIONS_PER_HOUR >= --users.
"""

import argparse
import secrets
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx


def run_user(base_url: str, path: Path, output_type: str, model: str | None, username: str) -> dict:
    with httpx.Client(base_url=base_url, timeout=600) as client:
        account = client.post(
            "/api/auth/register", json={"username": username, "password": secrets.token_urlsafe(16)}
        )
        account.raise_for_status()
        started = time.perf_counter()
        with path.open("rb") as stream:
            upload = client.post("/api/uploads", files={"file": (path.name, stream)})
        upload.raise_for_status()
        body = {"upload_id": upload.json()["id"], "output_type": output_type, "model": model}
        job = client.post("/api/jobs", json=body)
        job.raise_for_status()
        job = job.json()
        while job["status"] in ("queued", "processing"):
            time.sleep(1)
            job = client.get(f"/api/jobs/{job['id']}").json()
        job["wall_s"] = time.perf_counter() - started
        return job


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--output-type", default="video_embedded")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    run = secrets.token_hex(3)
    with ThreadPoolExecutor(args.users) as pool:
        futures = [
            pool.submit(run_user, args.url, args.file, args.output_type, args.model, f"bench-{run}-{n}")
            for n in range(args.users)
        ]
        results = [f.result() for f in futures]

    ok = True
    print(f"{'statut':<8} {'attente+calcul (s)':>19} {'calcul (s)':>11} {'x durée':>8}")
    for job in sorted(results, key=lambda j: j["wall_s"]):
        duration = job["duration_s"]
        ratio = job["wall_s"] / duration if duration else float("nan")
        ok = ok and job["status"] == "done" and ratio < 1
        print(f"{job['status']:<8} {job['wall_s']:>19.1f} {job['compute_s'] or 0:>11.1f} {ratio:>8.2f}")
    print("OBJECTIF ATTEINT" if ok else "OBJECTIF NON ATTEINT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
