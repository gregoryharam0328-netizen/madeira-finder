import re

from bs4 import BeautifulSoup
from curl_cffi import requests as r


def main():
    u = "https://www.pinkrealestate.pt/all-properties/buy-apartments-madeira-island-portugal"
    html = r.get(u, impersonate="chrome124", timeout=30.0).text
    soup = BeautifulSoup(html, "html.parser")
    a = soup.select_one('a[href^="/properties/details/property/"]')
    if not a:
        print("no link")
        return
    print("href", a.get("href"))
    cur = a
    for depth in range(1, 8):
        if not cur:
            break
        print("\nDEPTH", depth, cur.name, cur.get("class"))
        print(cur.get_text(" ", strip=True)[:350])
        cur = cur.parent


if __name__ == "__main__":
    main()
