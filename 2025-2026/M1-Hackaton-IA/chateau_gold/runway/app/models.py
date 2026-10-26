from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Job:
    id: str
    prompt: str
    input_url: str
    output_url: Optional[str] = None
    status: str = "queued"

# stockage en mémoire pour simplicité
JOBS = {}

def create_job(job_id, prompt, input_url):
    job = Job(id=job_id, prompt=prompt, input_url=input_url)
    JOBS[job_id] = job
    return job

def get_job(job_id):
    return JOBS.get(job_id)
