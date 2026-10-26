from serpapi import GoogleSearch

params = {
    "engine": "google_play",
    "apps_category": "EDUCATION",  # ou autre catégorie
    "gl": "fr",
    "hl": "fr",
    "api_key": ""
}

search = GoogleSearch(params)
results = search.get_dict()

print("Message d'erreur :", results.get("error"))
print("Clés disponibles dans results :", results.keys())

# Vérifie que la structure contient bien des résultats
organic_results = results.get("organic_results", [])
if not organic_results or "items" not in organic_results[0]:
    print("❌ Aucun résultat trouvé dans 'organic_results'")
else:
    apps = organic_results[0]["items"]
    print(f"✅ Nombre d'apps trouvées : {len(apps)}")

    for app in apps:
        title = app.get("title", "N/A")
        developer = app.get("author", "N/A")
        score = app.get("rating", "N/A")
        installs = app.get("downloads", "N/A")
        category = app.get("category", "N/A")
        description = app.get("description", "N/A")

        print(f"Title: {title}")
        print(f"Developer: {developer}")
        print(f"Note Moyenne: {score}")
        print(f"Téléchargements: {installs}")
        print(f"Catégorie: {category}")
        print(f"Description: {description[:200]}...")
        print("-" * 40)


import pandas as pd
import re
import sqlite3

# 1. Fonctions de nettoyage
def parse_downloads(text):
    text = text.replace("+", "").replace(" ", "")
    match = re.match(r"([\d.,]+)([KMB]?)", text)
    if not match:
        return 0
    number, suffix = match.groups()
    number = float(number.replace(",", "."))
    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return int(number * multiplier.get(suffix, 1))

def clean_text(text):
    return re.sub(r"[^\w\sÀ-ÿ.,!?]", "", text).strip()

# 2. Structuration des données
data = []
for app in apps:
    data.append({
        "Titre": clean_text(app.get("title", "N/A")),
        "Développeur": clean_text(app.get("author", "N/A")),
        "Note": app.get("rating", None),
        "Téléchargements": parse_downloads(app.get("downloads", "0")),
        "Catégorie": clean_text(app.get("category", "N/A")),
        "Description": clean_text(app.get("description", ""))
    })

# 3. Création du DataFrame
df = pd.DataFrame(data)

# 4. Suppression des doublons
df.drop_duplicates(subset=["Titre", "Développeur"], inplace=True)

# 5. Export CSV
df.to_csv("apps_education.csv", index=False, encoding="utf-8")

# 6. Export SQLite
conn = sqlite3.connect("apps_education.db")
df.to_sql("apps", conn, if_exists="replace", index=False)
conn.close()

print("✅ Données nettoyées et exportées dans apps_education.csv et apps_education.db")
