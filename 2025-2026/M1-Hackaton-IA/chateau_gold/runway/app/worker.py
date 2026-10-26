import time
from .job_queue import pop
from .models import get_job
from .runway import generate

def run_worker():
    print("Worker démarré...")
    while True:
        job_id = pop()
        if job_id:
            job = get_job(job_id)
            if job:
                job.status = "processing"
                try:
                    output_url = generate(job.input_url, job.prompt)
                    job.output_url = output_url
                    job.status = "done"
                    print(f"Job {job_id} terminé")
                except Exception as e:
                    job.status = "error"
                    print(f"Erreur job {job_id}: {e}")
        else:
            time.sleep(1)

if __name__ == "__main__":
    run_worker()
