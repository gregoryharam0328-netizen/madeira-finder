import re
import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.century21.pt/comprar", force_playwright=True).html
    refs = sorted(set(re.findall(r'href="(/ref/[^"]+)"', html)))
    print("len", len(html))
    print("/ref links", len(refs))
    print("sample:", refs[:10])


if __name__ == "__main__":
    main()
