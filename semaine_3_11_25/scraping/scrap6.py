import requests
from bs4 import BeautifulSoup
import json
import time
import logging
import os
from datetime import datetime

BASE_URL = "http://books.toscrape.com/catalogue/"
START_PAGE = 1
MAX_RETRIES = 5
TIMEOUT = 5
DELAY = 1.5
CHECKPOINT_FILE = "checkpoint.json"
LOG_FILE = "scraper.log"
DATA_FILE = "books_resilient.json"

# 📋 Logger
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 💾 Chargement de la progression
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        checkpoint = json.load(f)
        current_page = checkpoint.get("page", START_PAGE)
        books = checkpoint.get("books", [])
else:
    current_page = START_PAGE
    books = []

def get_soup(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            if response.status_code == 200:
                if "Access denied" in response.text or "403 Forbidden" in response.text:
                    logging.warning(f"Blocage IP détecté sur {url}")
                    return None
                return BeautifulSoup(response.content, "html.parser")
            elif response.status_code == 403:
                logging.warning(f"403 Forbidden sur {url}")
                return None
            else:
                logging.warning(f"Erreur {response.status_code} sur {url}")
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout sur {url}, tentative {attempt+1}")
            time.sleep(DELAY * (attempt + 1))
        except Exception as e:
            logging.error(f"Exception sur {url} : {e}")
            time.sleep(DELAY * (attempt + 1))
    return None

def extract_books_from_page(page_num):
    url = f"{BASE_URL}page-{page_num}.html"
    soup = get_soup(url)
    if not soup:
        return None

    articles = soup.select("article.product_pod")
    if not articles:
        return None

    page_books = []
    for article in articles:
        title = article.h3.a["title"]
        price = float(article.select_one(".price_color").text.lstrip("£"))
        rating_class = article.select_one(".star-rating")["class"][1]
        rating = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}.get(rating_class, 0)
        page_books.append({
            "title": title,
            "price": price,
            "rating": rating
        })
    return page_books

# 🚀 Scraping avec reprise
while True:
    logging.info(f"Scraping page {current_page}")
    result = extract_books_from_page(current_page)
    if result is None:
        logging.info(f"Aucune donnée sur la page {current_page}. Fin.")
        break

    books.extend(result)
    logging.info(f"{len(result)} livres extraits de la page {current_page}")

    # 💾 Sauvegarde de la progression
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"page": current_page + 1, "books": books}, f, ensure_ascii=False)

    current_page += 1
    time.sleep(DELAY)

# 🧾 Sauvegarde finale
with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(books, f, ensure_ascii=False, indent=2)

logging.info(f"Scraping terminé. {len(books)} livres extraits.")
print(f"\n✅ Scraping terminé. {len(books)} livres extraits.")