from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from openai import OpenAI
import os
from fastapi.responses import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is missing. Check your .env file.")

# client = OpenAI(api_key=api_key)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:8000",  # facultatif
        "X-Title": "FastAPI Market Analyzer"       # facultatif
    }
)
def call_llm(prompt: str) -> str:
    """
    Envoie un prompt à GPT (via l'API OpenAI) et renvoie la réponse.
    """
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # ou "gpt-4o", selon ton plan
        messages=[
            {"role": "system", "content": "Tu es un expert en études de marché."},
            {"role": "user", "content": prompt}
        ]
    )
    return completion.choices[0].message.content

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyse_market", response_class=HTMLResponse)
def analyse_market(request: Request, produits: str = Form(...), secteur: str = Form(...)):    
    prompt = (
        f"Tu es un expert en études de marché. Compare les produits suivants dans le secteur {secteur} : {produits}. "
        f"Présente les concurrents, les tendances, les points forts/faibles. "
        f"Génère un tableau comparatif au format texte avec des colonnes : Produit | Avantages | Inconvénients. "
        f"Utilise des lignes séparées par des retours à la ligne et des barres verticales pour les colonnes."
    )
    texte = call_llm(prompt)
    return templates.TemplateResponse("result.html", {"request": request, "contenu": texte})




from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from reportlab.platypus import Image

def generate_pdf(content: str, filename: str = "rapport.pdf") -> str:

    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Étude de marché automatisée", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Analyse générée :", styles["Heading2"]))
    for line in content.split('\n'):
        if "|" not in line:
            elements.append(Paragraph(line.strip(), styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Tableau
    data = [["Produit", "Avantages", "Inconvénients"]]
    for line in content.split('\n'):
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                data.append(parts)

    if len(data) > 1:
        table = Table(data, colWidths=[150, 200, 200])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4B8BBE")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(Paragraph("Tableau comparatif :", styles["Heading2"]))
        elements.append(table)
        elements.append(Spacer(1, 12))

    # Graphiques
    elements.append(Paragraph("Graphiques :", styles["Heading2"]))
    for img_path in ["graph_attractivite.png", "graph_tendance.png", "graph_parts.png"]:
        elements.append(Image(img_path, width=400, height=250))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return filename


@app.get("/download_pdf/{produits}/{secteur}")
def download_pdf(produits: str, secteur: str):
    prompt = (
        f"Tu es un expert en études de marché. Compare les produits suivants dans le secteur {secteur} : {produits}. "
        f"Pour chaque produit, donne :\n"
        f"- Une ligne au format : Produit | Avantages | Inconvénients | Score : XX | Part de marché : XX%\n"
        f"- Ne fais aucun commentaire en dehors du tableau.\n"
        f"- Commence directement par les lignes du tableau, une par ligne.\n"
        f"Exemple : Renault | Fiabilité reconnue | Prix élevé | Score : 82 | Part de marché : 35%"
    )
    texte = call_llm(prompt)

    print("Texte brut du LLM :\n", texte)

    # Extraction des données depuis le texte du LLM
    scores = []
    parts = []
    produits_list = []

    for line in texte.split('\n'):
        if "|" in line and "Score" in line and "Part" in line:
            segments = line.split("|")
            if len(segments) >= 5:
                try:
                    produit = segments[0].strip()
                    score = int(segments[3].split(":")[1].strip())
                    part = int(segments[4].split(":")[1].strip().replace("%", ""))
                    produits_list.append(produit)
                    scores.append(score)
                    parts.append(part)
                except Exception as e:
                    print("Erreur de parsing sur la ligne :", line)
                    continue

    # Génération des graphiques avec les vraies données
    create_graphs(produits_list, scores, parts)

    filename = generate_pdf(texte)
    return FileResponse(filename, media_type="application/pdf", filename="rapport.pdf")



import matplotlib.pyplot as plt


def create_graphs(produits, scores, parts):
    # Vérification de cohérence des données
    if not (len(produits) == len(scores) == len(parts)) or len(produits) == 0:
        print("⚠️ Données invalides ou incomplètes pour générer les graphiques.")
        return

    # Histogramme d'attractivité
    try:
        plt.figure(figsize=(5, 3))
        plt.bar(produits, scores, color="#4B8BBE")
        plt.title("Attractivité des produits")
        plt.xlabel("Produits")
        plt.ylabel("Score")
        plt.tight_layout()
        plt.savefig("graph_attractivite.png")
        plt.close()
    except Exception as e:
        print("Erreur lors de la génération de l'histogramme :", e)

    # Camembert des parts de marché
    try:
        plt.figure(figsize=(4, 4))
        plt.pie(parts, labels=produits, autopct="%1.1f%%", colors=["#4B8BBE", "#306998", "#DBEB30"])
        plt.title("Parts de marché simulées")
        plt.tight_layout()
        plt.savefig("graph_parts.png")
        plt.close()
    except Exception as e:
        print("Erreur lors de la génération du camembert :", e)

    # Courbe de tendance (simulée)
    try:
        mois = ["Jan", "Fév", "Mar", "Avr", "Mai"]
        demande = [120, 150, 180, 160, 200]
        plt.figure(figsize=(5, 3))
        plt.plot(mois, demande, marker="o", color="green")
        plt.title("Évolution de la demande")
        plt.xlabel("Mois")
        plt.ylabel("Demande")
        plt.tight_layout()
        plt.savefig("graph_tendance.png")
        plt.close()
    except Exception as e:
        print("Erreur lors de la génération de la courbe de tendance :", e)