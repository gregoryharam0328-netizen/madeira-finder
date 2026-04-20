import re

from bs4 import BeautifulSoup
from curl_cffi import requests as r


def main():
    html = r.get("https://supercasa.pt/comprar-casas/madeira-distrito", impersonate="chrome124", timeout=30.0).text
    soup = BeautifulSoup(html, "html.parser")
    a = soup.find("a", href=re.compile(r"^/venda-[^/]+/i\d+$"))
    if not a:
        print("no venda link found")
        return
    print("href", a.get("href"))
    cur = a
    for depth in range(1, 10):
        if not cur:
            break
        print("\nDEPTH", depth, cur.name, cur.get("class"))
        print(cur.get_text(" ", strip=True)[:400])
        cur = cur.parent


if __name__ == "__main__":
    main()
