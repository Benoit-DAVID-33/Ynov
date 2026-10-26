import requests
from .config import RUNWAY_API_KEY, RUNWAY_ENDPOINT

def generate(video_url: str, prompt: str):
    headers = {"Authorization": f"Bearer {RUNWAY_API_KEY}"}
    payload = {
        "video_url": video_url,
        "prompt": prompt,
        "preserve_camera": True,
        "strength": 0.6
    }
    response = requests.post(RUNWAY_ENDPOINT, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("output_video_url")
    else:
        raise Exception(f"Erreur Runway: {response.text}")


