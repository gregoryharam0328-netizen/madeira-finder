import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html
from app.scrapers.urls import idealista_default_search_url


def main():
    url = idealista_default_search_url()
    html = fetch_html(url, force_playwright=True).html
    print("url", url)
    print("len", len(html))
    print(html[:200].replace("\n", " "))
    for needle in ["idealista", "item-info-container", "article", "listing", "map"]:
        print(needle, html.lower().count(needle))


if __name__ == "__main__":
    main()
