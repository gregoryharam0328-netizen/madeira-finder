import re
from collections import Counter

from curl_cffi import requests as r


def main():
    html = r.get(
        "https://www.imovirtual.com/pt/resultados/comprar/apartamento/ilha-da-madeira",
        impersonate="chrome124",
        timeout=30.0,
    ).text
    vals = re.findall(r'data-cy="([^"]+)"', html)
    c = Counter(vals)
    print("top data-cy values:")
    for k, v in c.most_common(25):
        print(v, k)


if __name__ == "__main__":
    main()
