import re
from collections import Counter

from curl_cffi import requests as r


def main():
    url = "https://www.imovirtual.com/pt/resultados/comprar/apartamento/ilha-da-madeira"
    html = r.get(url, impersonate="chrome124", timeout=30.0).text
    hrefs = re.findall(r'href="([^"]+)"', html)
    rels = [h for h in hrefs if h.startswith("/pt/")]
    c = Counter()
    for h in rels:
        prefix = "/".join(h.split("/")[:4])
        c[prefix] += 1
    print("top href prefixes:")
    for k, v in c.most_common(15):
        print(v, k)


if __name__ == "__main__":
    main()
