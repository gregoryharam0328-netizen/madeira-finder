import re
from collections import Counter

from curl_cffi import requests as r
from urllib.parse import urlencode


def main():
    min_eur = int(250000 * 1.17)
    max_eur = int(350000 * 1.17)
    base = "https://www.kyero.com/pt/ilha-da-madeira-imóvel-para-vender-0l57483"
    url = base + "?" + urlencode({"min_price": str(min_eur), "max_price": str(max_eur), "min_bed": "2"})
    html = r.get(url, impersonate="chrome124", timeout=30.0).text
    hrefs = re.findall(r'href="([^"]+)"', html)
    rels = [h for h in hrefs if h.startswith("/pt/")]
    c = Counter()
    for h in rels:
        parts = h.split("/")
        prefix = "/".join(parts[:3])
        c[prefix] += 1
    print("top /pt/*/ prefixes:")
    for k, v in c.most_common(20):
        print(v, k)


if __name__ == "__main__":
    main()
