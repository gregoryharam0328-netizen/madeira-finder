import re
from urllib.parse import urlencode

from curl_cffi import requests as r


def main():
    params = {"cn": "pt", "lg": "ro", "search": "True", "region": "madeira"}
    u = "https://www.green-acres.pt/ro/show_properties.htm?" + urlencode(params)
    html = r.get(u, impersonate="chrome124", timeout=30.0).text
    print("len", len(html))
    print(".htm count", html.count(".htm"))

    abs_urls = sorted(set(re.findall(r"https://www\.green-acres\.pt/[^\"'<> ]+\.htm", html)))
    rel_urls = sorted(set(re.findall(r"/[a-z]{2}/[^\"'<> ]+\.htm", html)))
    print("abs .htm", len(abs_urls))
    print("rel .htm", len(rel_urls))
    print("sample rel", rel_urls[:15])

    propish = [u for u in rel_urls if "property" in u or "propriet" in u or "anuncio" in u or "advert" in u]
    print("propish rel", len(propish))
    print("sample propish", propish[:20])


if __name__ == "__main__":
    main()
