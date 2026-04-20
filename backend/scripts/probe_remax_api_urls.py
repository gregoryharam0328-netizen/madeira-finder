import re
import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.remax.pt/pt/comprar").html
    urls = sorted(set(re.findall(r"https://api\.[^\"'<> ]+", html)))
    print("https://api.* hits:", len(urls))
    for u in urls[:50]:
        print("-", u)


if __name__ == "__main__":
    main()
