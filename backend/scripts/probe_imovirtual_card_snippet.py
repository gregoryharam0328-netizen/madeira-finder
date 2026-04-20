from curl_cffi import requests as r
from bs4 import BeautifulSoup


def main():
    html = r.get(
        "https://www.imovirtual.com/pt/resultados/comprar/apartamento/ilha-da-madeira",
        impersonate="chrome124",
        timeout=30.0,
    ).text
    soup = BeautifulSoup(html, "html.parser")
    a = soup.select_one('a[data-cy="listing-item-link"][href^="/pt/anuncio/"]')
    if not a:
        print("no listing link found")
        return
    card = a.find_parent()
    print("anchor:", a.get("href"))
    for depth in range(1, 7):
        cur = a
        for _ in range(depth):
            if not cur.parent:
                break
            cur = cur.parent
        print("\n--- depth", depth, "tag", cur.name, "classes", cur.get("class"))
        snippet = cur.get_text(" ", strip=True)
        print(snippet[:400])


if __name__ == "__main__":
    main()
