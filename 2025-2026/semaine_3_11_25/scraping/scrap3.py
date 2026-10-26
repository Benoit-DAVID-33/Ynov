import requests
from bs4 import BeautifulSoup
import pandas as pd
import argparse
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "https://realpython.github.io/fake-jobs/"
response = requests.get(BASE_URL)
soup = BeautifulSoup(response.content, "html.parser")

jobs = []

for job_card in soup.select(".card-content"):
    title = job_card.h2.text.strip()
    if "python" not in title.lower():
        continue

    company = job_card.select_one("h3").text.strip()
    location = job_card.select_one(".location").text.strip()
    date_raw = job_card.select_one("time")["datetime"]
    date = datetime.strptime(date_raw, "%Y-%m-%d").date()

    apply_link = job_card.select_one("a.card-footer-item")["href"]
    apply_url = urljoin(BASE_URL, apply_link)

    contract_type = "Full-time" if "Full" in title else "Other"

    jobs.append({
        "title": title,
        "company": company,
        "location": location,
        "date": date.isoformat(),
        "contract": contract_type,
        "apply_url": apply_url
    })

# 🔍 Détection de doublons
df = pd.DataFrame(jobs)
df.drop_duplicates(subset=["title", "company", "location"], inplace=True)

# 📊 Statistiques
stats_by_city = df["location"].value_counts()
stats_by_contract = df["contract"].value_counts()

print("\n📍 Offres par ville :")
print(stats_by_city)

print("\n📄 Offres par type de contrat :")
print(stats_by_contract)

# 🧪 Filtres dynamiques CLI
parser = argparse.ArgumentParser()
parser.add_argument("--city", help="Filtrer par ville")
parser.add_argument("--contract", help="Filtrer par type de contrat")
args = parser.parse_args()

if args.city:
    df = df[df["location"].str.contains(args.city, case=False)]

if args.contract:
    df = df[df["contract"].str.contains(args.contract, case=False)]

# 💾 Sauvegarde CSV UTF-8
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"fake_jobs_{timestamp}.csv"
df.to_csv(filename, index=False, encoding="utf-8")

print(f"\n✅ Sauvegarde terminée : {filename}")