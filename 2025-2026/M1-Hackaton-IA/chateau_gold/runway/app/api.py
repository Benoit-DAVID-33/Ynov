from fastapi import FastAPI, UploadFile, File
from uuid import uuid4
from .models import create_job, get_job
from .storage import save_video
from .job_queue import push

app = FastAPI()

@app.post("/generate")
async def generate_video(prompt: str, video: UploadFile = File(...)):
    job_id = str(uuid4())
    video_path = save_video(await video.read(), f"{job_id}_{video.filename}")
    job = create_job(job_id, prompt, video_path)
    push(job_id)
    return {"job_id": job_id, "status": job.status}

@app.get("/status/{job_id}")
def status(job_id: str):
    job = get_job(job_id)
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job.id,
        "status": job.status,
        "output_url": job.output_url
    }
