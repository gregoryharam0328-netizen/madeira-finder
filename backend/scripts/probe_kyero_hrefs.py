import re
from collections import Counter

from curl_cffi import requests as r


def main():
    url = "https://www.kyero.com/pt/ilha-da-madeira-terrenos-para-vender-0l57483g5"
    html = r.get(url, impersonate="chrome124", timeout=30.0).text
    hrefs = re.findall(r'href="([^"]+)"', html)
    c = Counter()
    for h in hrefs:
        if "kyero" in h:
            continue
        if h.startswith("/pt/"):
            parts = h.split("/")
            prefix = "/".join(parts[:4]) if len(parts) >= 4 else h
            c[prefix] += 1
    print("top /pt/ href prefixes:")
    for k, v in c.most_common(25):
        print(v, k)


if __name__ == "__main__":
    main()
