import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from curl_cffi import requests as r


def main():
    min_eur = int(250000 * 1.17)
    max_eur = int(350000 * 1.17)
    base = "https://www.kyero.com/pt/ilha-da-madeira-imóvel-para-vender-0l57483"
    url = base + "?" + urlencode({"min_price": str(min_eur), "max_price": str(max_eur), "min_bed": "2"})
    html = r.get(url, impersonate="chrome124", timeout=30.0).text
    soup = BeautifulSoup(html, "html.parser")
    a = soup.select_one('a[href^="/pt/property/"]')
    if not a:
        print("no property link")
        return
    print("href", a.get("href"))
    cur = a
    for depth in range(1, 8):
        if not cur:
            break
        print("\nDEPTH", depth, cur.name, cur.get("class"))
        txt = cur.get_text(" ", strip=True)
        print(txt[:350])


if __name__ == "__main__":
    main()
