import requests
from bs4 import BeautifulSoup
import json
from collections import defaultdict
from statistics import mean
from urllib.parse import urljoin

BASE_URL = "https://books.toscrape.com/"
CATEGORY_URL = urljoin(BASE_URL, "catalogue/category/books/")
CATEGORY_TREE = defaultdict(dict)

def get_soup(url):
    response = requests.get(url)
    return BeautifulSoup(response.content, "html.parser") if response.status_code == 200 else None

def get_categories():
    soup = get_soup(BASE_URL)
    categories = soup.select(".side_categories ul li ul li a")
    return {
        cat.text.strip(): urljoin(BASE_URL, cat["href"])
        for cat in categories
        if "Add a comment" not in cat.text
    }

def extract_books_from_category(cat_name, cat_url):
    books = []
    page = 1
    while True:
        paged_url = cat_url.replace("index.html", f"page-{page}.html")
        soup = get_soup(paged_url)
        if not soup:
            break

        articles = soup.select("article.product_pod")
        if not articles:
            break

        for article in articles:
            title = article.h3.a["title"]
            price = float(article.select_one(".price_color").text.lstrip("£"))
            rating_class = article.select_one(".star-rating")["class"][1]
            rating = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}.get(rating_class, 0)
            books.append({"title": title, "price": price, "rating": rating})

        page += 1
    return books

def build_category_tree():
    categories = get_categories()
    for name, url in categories.items():
        books = extract_books_from_category(name, url)
        if books:
            prices = [b["price"] for b in books]
            ratings = [b["rating"] for b in books]
            weighted_avg = round(sum(p * r for p, r in zip(prices, ratings)) / sum(ratings), 2) if sum(ratings) else 0
            CATEGORY_TREE[name] = {
                "url": url,
                "total_books": len(books),
                "price": {
                    "average": round(mean(prices), 2),
                    "min": round(min(prices), 2),
                    "max": round(max(prices), 2),
                    "weighted_average": weighted_avg
                },
                "books": books
            }

def detect_underrepresented(threshold=10):
    return [cat for cat, data in CATEGORY_TREE.items() if data["total_books"] < threshold]

def full_text_search(query):
    results = []
    for cat, data in CATEGORY_TREE.items():
        for book in data["books"]:
            if query.lower() in book["title"].lower():
                results.append({"category": cat, "title": book["title"], "price": book["price"], "rating": book["rating"]})
    return results

def export_nested_json():
    with open("category_tree.json", "w", encoding="utf-8") as f:
        json.dump(CATEGORY_TREE, f, ensure_ascii=False, indent=2)

# 🧠 Exécution
build_category_tree()
underrepresented = detect_underrepresented()
search_results = full_text_search("history")
export_nested_json()

# 🏆 Classement des catégories par prix moyen
ranking = sorted(CATEGORY_TREE.items(), key=lambda x: x[1]["price"]["average"], reverse=True)
print("\n🏆 Classement des catégories par prix moyen :")
for cat, data in ranking[:5]:
    print(f"{cat} → {data['price']['average']} £")

print("\n📉 Catégories sous-représentées (<10 livres) :", underrepresented)
print(f"\n🔍 Résultats de recherche 'history' : {len(search_results)} livres trouvés")
print("📁 Export JSON terminé : category_tree.json")