import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = BASE_URL + "catalogue/"
books = []

def get_soup(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BeautifulSoup(response.content, "html.parser")
        elif response.status_code == 404:
            print(f"404 Not Found : {url}")
            return None
        else:
            print(f"Erreur {response.status_code} : {url}")
            return None
    except Exception as e:
        print(f"Exception : {e}")
        return None

def rating_to_int(rating_str):
    return {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}.get(rating_str, 0)

def extract_book_details(book_url):
    soup = get_soup(book_url)
    if not soup:
        return None

    title = soup.h1.text.strip()
    price = float(soup.select_one(".price_color").text.strip().lstrip("£"))
    rating_class = soup.select_one(".star-rating")["class"][1]
    rating = rating_to_int(rating_class)

    description_tag = soup.select_one("#product_description ~ p")
    description = description_tag.text.strip() if description_tag else ""

    stock_text = soup.select_one(".availability").text
    stock_match = re.search(r"(\d+) available", stock_text)
    stock = int(stock_match.group(1)) if stock_match else 0

    image_rel_url = soup.select_one(".item img")["src"].replace("../../", "")
    image_url = BASE_URL + image_rel_url

    breadcrumb = soup.select(".breadcrumb li a")
    category_main = breadcrumb[1].text.strip() if len(breadcrumb) > 1 else ""
    category_sub = breadcrumb[2].text.strip() if len(breadcrumb) > 2 else ""

    return {
        "title": title,
        "url": book_url,
        "price": price,
        "rating": rating,
        "category": {
            "main": category_main,
            "sub": category_sub
        },
        "description": description,
        "stock": stock,
        "image_url": image_url
    }

def scrape_all_books(max_pages=5, max_books=5):
    page = 1
    total_scraped = 0

    while page <= max_pages:
        soup = get_soup(f"{CATALOGUE_URL}page-{page}.html")
        if not soup:
            break

        book_links = soup.select("h3 a")
        if not book_links:
            break

        for link in book_links:
            if max_books and total_scraped >= max_books:
                return

            rel_url = link["href"].replace("../../../", "")
            book_url = CATALOGUE_URL + rel_url
            book_data = extract_book_details(book_url)
            if book_data:
                books.append(book_data)
                total_scraped += 1
                print(f"Scrapé : {book_data['title']}")

        page += 1

scrape_all_books()

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"books_{timestamp}.json"

with open(filename, "w", encoding="utf-8") as f:
    json.dump(books, f, ensure_ascii=False, indent=2)

print(f"\n✅ Sauvegarde terminée : {filename}")