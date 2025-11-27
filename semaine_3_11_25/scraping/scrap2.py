import requests
from bs4 import BeautifulSoup
import networkx as nx
import re
from collections import defaultdict
from datetime import datetime

BASE_URL = "http://quotes.toscrape.com"
G = nx.DiGraph()
author_cache = {}

def get_soup(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return BeautifulSoup(response.content, "html.parser")
        else:
            print(f"Erreur {response.status_code} : {url}")
            return None
    except Exception as e:
        print(f"Exception : {e}")
        return None

def extract_author_details(author_url):
    if author_url in author_cache:
        return author_cache[author_url]

    soup = get_soup(author_url)
    if not soup:
        return {}

    born_date = soup.select_one(".author-born-date").text.strip()
    born_location = soup.select_one(".author-born-location").text.strip()
    bio = soup.select_one(".author-description").text.strip()
    death_match = re.search(r"Died\s*[:\-]?\s*(.*)", bio)
    death_date = death_match.group(1).strip() if death_match else None

    author_data = {
        "born_date": born_date,
        "born_location": born_location,
        "death_date": death_date,
        "bio": bio
    }
    author_cache[author_url] = author_data
    return author_data

def scrape_quotes():
    page = 1
    while True:
        soup = get_soup(f"{BASE_URL}/page/{page}/")
        if not soup:
            break

        quotes = soup.select(".quote")
        if not quotes:
            break

        for quote in quotes:
            text = quote.select_one(".text").text.strip()
            author = quote.select_one(".author").text.strip()
            tags = [tag.text.strip() for tag in quote.select(".tags .tag")]
            author_rel_url = quote.select_one("span a")["href"]
            author_url = BASE_URL + author_rel_url
            author_data = extract_author_details(author_url)

            # Ajouter les nœuds
            G.add_node(text, type="quote")
            G.add_node(author, type="author", **author_data)
            for tag in tags:
                G.add_node(tag, type="tag")

            # Ajouter les relations
            G.add_edge(text, author, relation="written_by")
            for tag in tags:
                G.add_edge(text, tag, relation="has_tag")

        page += 1

scrape_quotes()

def clean_graphml_attributes(graph):
    for node, attrs in graph.nodes(data=True):
        for key in list(attrs):
            if attrs[key] is None:
                del attrs[key]
    for u, v, attrs in graph.edges(data=True):
        for key in list(attrs):
            if attrs[key] is None:
                del attrs[key]

# 📤 Export
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
clean_graphml_attributes(G)
nx.write_graphml(G, f"quotes_graph_{timestamp}.graphml")
nx.write_gexf(G, f"quotes_graph_{timestamp}.gexf")

# 📊 Auteurs les plus cités
author_counts = defaultdict(int)
for u, v, d in G.edges(data=True):
    if d.get("relation") == "written_by":
        author_counts[v] += 1

top_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
print("\n📚 Auteurs les plus cités :")
for author, count in top_authors[:5]:
    print(f"{author} : {count} citations")