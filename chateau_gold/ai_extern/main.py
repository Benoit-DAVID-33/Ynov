import fal_client
import os

# ---------------------------------------------------------
# REMPLACE CECI PAR TA VRAIE CLÉ (ne partage pas ce code sur internet après)
os.environ["FAL_KEY"] = "a99102f5-dff2-4133-a614-0cf7dece192a:689cae7db1be6fa5b45f9fbdd8283c74"
# ---------------------------------------------------------

def on_queue_update(update):
    if isinstance(update, fal_client.InProgress):
        if update.logs:
            for log in update.logs:
                print(f"Log: {log['message']}")

def generate():
    print("Envoi de la demande à Fal.ai (Kling)...")
    
    try:
        result = fal_client.subscribe(
            "fal-ai/kling-video/v2.6/pro/image-to-video",
            arguments={
                "prompt": "Cinematic wide shot. Daytime. In the far distance, the base of the Rocky Mountains explodes outwards as a colossal mechanical titan erupts from underground, throwing massive clouds of dust, dirt, and rock debris into the air. The giant mech rises, stabilizes, and launches a barrage of glowing missiles straight towards the camera. Smoke trails streak across the sky as projectiles rapidly approach the foreground frame. High budget Sci-Fi VFX, 8k, highly detailed, photorealistic.",
                "image_url": "https://images.pexels.com/photos/1461027/pexels-photo-1461027.jpeg",
                "duration": "5" # Durée en secondes
            },
            on_queue_update=on_queue_update,
        )
        print("VIDÉO GÉNÉRÉE AVEC SUCCÈS !")
        print(result) # L'URL de ta vidéo sera ici
        
        # Petit bonus : ça télécharge la vidéo automatiquement
        if 'video' in result and 'url' in result['video']:
             import urllib.request
             urllib.request.urlretrieve(result['video']['url'], "ma_video_2.mp4")
             print("Vidéo sauvegardée sous 'ma_video_finale.mp4'")
             
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    generate()