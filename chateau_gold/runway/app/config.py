import os

# Runway API
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY", "votre_clef_runway")
RUNWAY_ENDPOINT = os.getenv(
    "RUNWAY_ENDPOINT",
    "https://api.runwayml.com/v1/video-to-video"
)

# Stockage vidéos (ex: S3 ou R2)
STORAGE_PATH = os.getenv("STORAGE_PATH", "./videos/")

# Limites
MAX_DURATION = 10  # secondes
