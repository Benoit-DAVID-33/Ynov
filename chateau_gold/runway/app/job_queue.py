# import redis

# r = redis.Redis(host='localhost', port=6379, db=0)

# def push(job_id: str):
#     r.lpush("video_jobs", job_id)

# def pop():
#     job = r.brpop("video_jobs", timeout=5)
#     if job:
#         return job[1].decode()
#     return None


# job_queue.py (simulation sans Redis)
JOBS_QUEUE = []

def push(job_id: str):
    JOBS_QUEUE.append(job_id)

def pop():
    if JOBS_QUEUE:
        return JOBS_QUEUE.pop(0)
    return None
