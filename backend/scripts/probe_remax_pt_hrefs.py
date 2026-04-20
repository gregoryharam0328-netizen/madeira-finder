import re
import sys
from collections import Counter

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.remax.pt/agencia/remax-elite/12351", force_playwright=True).html
    print("html len", len(html))
    print(html[:200].replace("\n", " "))
    hrefs = re.findall(r"href=\"(/pt/[^\"]+)\"", html)
    abs_hrefs = re.findall(r"href=\"(https://www\.remax\.pt/pt/[^\"]+)\"", html)
    print("/pt hrefs:", len(hrefs))
    print("abs /pt hrefs:", len(abs_hrefs))

    seg_counter: Counter[str] = Counter()
    for h in hrefs:
        parts = h.split("/")
        seg = parts[3] if len(parts) > 3 else ""
        seg_counter[seg] += 1

    print("top 3rd segments:")
    for seg, n in seg_counter.most_common(25):
        print(n, seg)


if __name__ == "__main__":
    main()
