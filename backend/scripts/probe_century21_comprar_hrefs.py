import re
import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.century21.pt/comprar", force_playwright=True).html
    hrefs = re.findall(r"href=\"([^\"]+)\"", html)
    comprar = [h for h in hrefs if "/comprar/" in h and "http" not in h]
    print("comprar hrefs", len(comprar))
    for h in comprar[:40]:
        print("-", h)


if __name__ == "__main__":
    main()
