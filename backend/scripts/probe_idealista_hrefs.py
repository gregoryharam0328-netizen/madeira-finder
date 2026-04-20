import re
import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html
from app.scrapers.urls import idealista_default_search_url


def main():
    url = idealista_default_search_url()
    html = fetch_html(url, force_playwright=True).html.lower()
    print("len", len(html))
    for pat in [r'href="(/imovel/[^\"]+)"', r"href='(/imovel/[^']+)'", r'href="(/inmueble/[^\"]+)"']:
        hits = re.findall(pat, html)
        print(pat, len(hits))
        if hits:
            print("sample", hits[:5])


if __name__ == "__main__":
    main()
