import pandas as pd
import numpy as np
import json
import unicodedata
from datetime import datetime

# 📂 Chargement du fichier JSON
df = pd.read_json("books_2025-11-06_11-28-49.json")

# 🔍 Nettoyage et standardisation
def normalize_text(text):
    return unicodedata.normalize("NFKD", str(text)).strip()

df["title"] = df["title"].apply(normalize_text)
df["description"] = df["description"].apply(normalize_text)
df["category_main"] = df["category"].apply(lambda x: normalize_text(x.get("main", "")) if isinstance(x, dict) else "")
df["category_sub"] = df["category"].apply(lambda x: normalize_text(x.get("sub", "")) if isinstance(x, dict) else "")
df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
df["stock"] = pd.to_numeric(df["stock"], errors="coerce")

# 🧠 Imputation des valeurs manquantes
df["price"].fillna(df["price"].median(), inplace=True)
df["rating"].fillna(0, inplace=True)
df["stock"].fillna(0, inplace=True)

# ✅ Validation croisée
df["valid_url"] = df["url"].apply(lambda x: str(x).startswith("http"))
df["valid_image"] = df["image_url"].apply(lambda x: str(x).endswith(".jpg"))

# ⚠️ Détection d’anomalies
anomalies = df[
    (df["price"] < 1) |
    (df["price"] > 100) |
    (df["rating"] > 5) |
    (df["stock"] < 0)
]

# 📊 Métriques de qualité
report = {
    "total_books": len(df),
    "missing_titles": int(df["title"].isna().sum()),
    "missing_descriptions": int(df["description"].isna().sum()),
    "invalid_urls": int(~df["valid_url"].sum()),
    "invalid_images": int(~df["valid_image"].sum()),
    "anomalies_detected": len(anomalies),
    "price_range": [float(df["price"].min()), float(df["price"].max())],
    "rating_distribution": df["rating"].value_counts().to_dict(),
    "stock_range": [int(df["stock"].min()), int(df["stock"].max())]
}

# 🧾 Sauvegarde du rapport
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
with open(f"quality_report_{timestamp}.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n✅ Pipeline terminé. Rapport qualité : quality_report_{timestamp}.json")
print(f"📉 Anomalies détectées : {len(anomalies)}")