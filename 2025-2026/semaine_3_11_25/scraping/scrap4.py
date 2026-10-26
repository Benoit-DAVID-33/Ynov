import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
from fpdf import FPDF
import glob
import os

# 📂 Chargement du fichier JSON le plus récent
try:
    latest_file = max(glob.glob("books_*.json"), key=os.path.getctime)
    df = pd.read_json(latest_file)
    print(f"✅ Fichier chargé : {latest_file}")
except ValueError:
    print("❌ Aucun fichier JSON trouvé.")
    exit()

# 🔍 Nettoyage
df["rating"] = df["rating"].fillna(0).astype(int)
df["price"] = df["price"].fillna(0).astype(float)
df["stock"] = df["stock"].fillna(0).astype(int)
df["category_main"] = df["category"].apply(lambda x: x.get("main", "") if isinstance(x, dict) else "")
df["category_sub"] = df["category"].apply(lambda x: x.get("sub", "") if isinstance(x, dict) else "")

# 📊 Prix moyen par note
price_by_rating = df.groupby("rating")["price"].mean().reset_index()

# 📊 Prix moyen par catégorie
price_by_category = df.groupby("category_main")["price"].mean().reset_index()

# 🚨 Livres en rupture de stock
out_of_stock = df[df["stock"] == 0]

# 📉 Distribution des notes
rating_dist = df["rating"].value_counts().sort_index()

# 📐 Corrélation note/prix
correlation = df["rating"].corr(df["price"])

# 🔔 Alerte prix : seuil personnalisable
PRICE_ALERT_THRESHOLD = 55
alerts = df[df["price"] > PRICE_ALERT_THRESHOLD]

# 📈 Visualisation interactive
fig = px.scatter(df, x="rating", y="price", color="category_main", hover_data=["title"])
fig.write_html("interactive_price_rating.html")

from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)

# Titre principal
pdf.set_font("Arial", style="B", size=14)
pdf.cell(0, 10, "Analyse de marché livresque", ln=True, align="C")

pdf.set_font("Arial", size=12)
pdf.ln(10)
pdf.cell(0, 10, f"Corrélation note/prix : {correlation:.2f}", ln=True)

pdf.ln(10)
pdf.cell(0, 10, "Livres en rupture de stock :", ln=True)

# Affichage des titres
for title in out_of_stock["title"].head(5):
    pdf.multi_cell(0, 10, f"- {title}")

pdf.ln(10)
pdf.cell(0, 10, "Prix moyen par note :", ln=True)
for _, row in price_by_rating.iterrows():
    pdf.cell(0, 10, f"Note {row['rating']} : {row['price']:.2f} £", ln=True)

pdf.ln(10)
pdf.cell(0, 10, "Prix moyen par catégorie :", ln=True)
for _, row in price_by_category.iterrows():
    pdf.multi_cell(0, 10, f"{row['category_main']} : {row['price']:.2f} £")

pdf.output("rapport_books.pdf")
print("📄 Rapport PDF généré : rapport_books.pdf")