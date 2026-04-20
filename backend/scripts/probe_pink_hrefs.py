import re
from collections import Counter

from curl_cffi import requests as r


def main():
    html = r.get("https://www.pinkrealestate.pt/", impersonate="chrome124", timeout=30.0).text
    hrefs = re.findall(r'href="([^"]+)"', html)
    rels = [h for h in hrefs if h.startswith("/")]
    c = Counter()
    for h in rels:
        parts = h.split("/")
        prefix = "/".join(parts[:3]) if len(parts) >= 3 else h
        c[prefix] += 1
    print("top href prefixes:")
    for k, v in c.most_common(25):
        print(v, k)


if __name__ == "__main__":
    main()
