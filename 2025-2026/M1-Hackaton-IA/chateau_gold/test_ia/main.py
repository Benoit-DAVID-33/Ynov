import websocket # pip install websocket-client
import uuid
import json
import urllib.request
import urllib.parse
import requests
import os

# CONFIGURATION
SERVER_ADDRESS = "127.0.0.1:8188"
CLIENT_ID = str(uuid.uuid4())
WORKFLOW_FILE = "workflow_api.json"
INPUT_FOLDER = "inputs" # Dossier local de votre projet
COMFY_INPUT_PATH = "C:/Chemin/Vers/ComfyUI/input" # Chemin ABSOLU vers le dossier input de ComfyUI

def queue_prompt(prompt_workflow):
    """Envoie le JSON au serveur ComfyUI pour exécution."""
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://{}/prompt".format(SERVER_ADDRESS), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    """Récupère les infos une fois le calcul fini."""
    with urllib.request.urlopen("http://{}/history/{}".format(SERVER_ADDRESS, prompt_id)) as response:
        return json.loads(response.read())

def upload_video(file_path):
    """Upload la vidéo vers ComfyUI (si pas en local direct)."""
    # Si vous êtes sur le même PC, une simple copie de fichier suffit
    # Mais voici la méthode API pour être propre
    filename = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        files = {'image': f} # Comfy appelle tout 'image' même les vidéos dans l'upload
        response = requests.post(
            "http://{}/upload/image".format(SERVER_ADDRESS), 
            files=files, 
            data={'subfolder': '', 'type': 'input'}
        )
    return filename

def load_workflow():
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_project(video_path, user_prompt):
    # 1. Charger le Workflow template
    prompt_workflow = load_workflow()
    
    # 2. Uploader la vidéo
    print(f"Uploading {video_path}...")
    video_filename = upload_video(video_path)
    
    # 3. MODIFIER LE JSON DYNAMIQUEMENT
    # C'est ici la partie délicate : il faut trouver l'ID des noeuds dans votre JSON.
    # Ouvrez le json et cherchez le "class_type" correspondant.
    
    # Exemple : Trouver le noeud qui charge la vidéo (VHS_LoadVideo)
    # Note: Les IDs ("10", "15" etc.) dépendent de VOTRE fichier json exporté.
    # Il faudra que l'étudiant IA vous donne les IDs fixes.
    
    # Hypothetical Node IDs (A adapter selon votre JSON réel !!!)
    node_loader_video = "10" 
    node_text_prompt = "3"   # Le noeud CLIP Text Encode (Positive)
    node_sampler = "5"       # Le KSampler (pour le seed)

    # Injection de la vidéo
    prompt_workflow[node_loader_video]["inputs"]["video"] = video_filename
    
    # Injection du prompt utilisateur
    prompt_workflow[node_text_prompt]["inputs"]["text"] = user_prompt
    
    # Changer le seed pour avoir un résultat unique à chaque fois
    import random
    prompt_workflow[node_sampler]["inputs"]["seed"] = random.randint(1, 1000000000)

    # 4. Connecter le WebSocket pour écouter la fin
    ws = websocket.WebSocket()
    ws.connect("ws://{}/ws?clientId={}".format(SERVER_ADDRESS, CLIENT_ID))
    
    # 5. Lancer le job
    print("Envoi du job à ComfyUI...")
    response = queue_prompt(prompt_workflow)
    prompt_id = response['prompt_id']
    
    # 6. Attendre la fin
    print("Calcul en cours (c'est le moment de chauffer le GPU)...")
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    print("Génération terminée !")
                    break
            elif message['type'] == 'progress':
                # Optionnel : Afficher la barre de progression
                data = message['data']
                print(f"Progress: {data['value']}/{data['max']}")

    # 7. Récupérer le nom du fichier de sortie
    history = get_history(prompt_id)[prompt_id]
    outputs = history['outputs']
    
    # On cherche le noeud de sauvegarde vidéo (VHS_VideoCombine)
    for node_id in outputs:
        node_output = outputs[node_id]
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                print(f"Vidéo générée : {video['filename']}")
                # Ici vous pouvez déplacer le fichier du dossier output de Comfy vers votre dossier projet
                return video['filename']

# --- EXECUTION TEST ---
if __name__ == "__main__":
    # Assurez-vous d'avoir une vidéo test dans le dossier inputs
    video_source = "inputs/test_etudiant.mp4"
    prompt = "cyberpunk style, neon lights, highly detailed, 8k"
    
    if os.path.exists(video_source):
        result = run_project(video_source, prompt)
        print(f"Succès ! Vidéo dispo dans ComfyUI/output/{result}")
    else:
        print("Erreur: Vidéo source introuvable.")