import os
from .config import STORAGE_PATH

os.makedirs(STORAGE_PATH, exist_ok=True)

def save_video(file, filename):
    path = os.path.join(STORAGE_PATH, filename)
    with open(path, "wb") as f:
        f.write(file)
    return path
