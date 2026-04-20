import re
import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.century21.pt/comprar").html
    urls = sorted(set(re.findall(r"https?://[^\"'<> ]+", html)))
    hits = [u for u in urls if any(x in u.lower() for x in ["api", "svc", "graphql", "elastic", "algolia"])]
    print("hits", len(hits))
    for u in hits[:80]:
        print("-", u)


if __name__ == "__main__":
    main()
