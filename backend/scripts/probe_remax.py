import json
import re
from collections import deque

from bs4 import BeautifulSoup
from curl_cffi import requests as r


def walk_keys(obj, max_hits: int = 40):
    hits = []
    q = deque([("root", obj)])
    while q and len(hits) < max_hits:
        path, cur = q.popleft()
        if isinstance(cur, dict):
            for k, v in cur.items():
                lk = str(k).lower()
                if any(x in lk for x in ["listing", "property", "imovel", "imóvel", "result", "search"]):
                    hits.append((f"{path}.{k}", type(v).__name__))
                q.append((f"{path}.{k}", v))
        elif isinstance(cur, list):
            for i, v in enumerate(cur[:50]):
                q.append((f"{path}[{i}]", v))
    return hits


def main():
    t = r.get("https://www.remax.pt/pt/comprar", impersonate="chrome124", timeout=20.0).text
    soup = BeautifulSoup(t, "html.parser")
    nd = soup.select_one("script#__NEXT_DATA__")
    if nd and nd.string:
        data = json.loads(nd.string)
        print("has __NEXT_DATA__", True)
        info = data.get("props", {}).get("pageProps", {}).get("initialSearchResultsInfo")
        print("initialSearchResultsInfo type:", type(info).__name__, "repr:", repr(info)[:500])
        if isinstance(info, dict):
            print("initialSearchResultsInfo keys:", sorted(info.keys())[:80])
            for k in ["listings", "results", "items", "properties", "searchResults"]:
                if k in info and isinstance(info[k], list):
                    print(k, "len", len(info[k]))
                    if info[k]:
                        print("first item keys:", sorted(info[k][0].keys())[:40])
        print("interesting keys (sample):")
        for p, typ in walk_keys(data, max_hits=60):
            print(f"- {p}: {typ}")
        return

    urls = re.findall(r"https?://[^\"'<> ]+", t)
    hits = sorted({u for u in urls if "api" in u.lower()})
    print("__NEXT_DATA__ missing")
    print("\n".join(hits[:50]) if hits else "no api urls")


if __name__ == "__main__":
    main()
