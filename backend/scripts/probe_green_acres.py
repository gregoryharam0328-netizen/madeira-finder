import re

from curl_cffi import requests as r


def main():
    t = r.get("https://www.green-acres.pt/apartament/madeira", impersonate="chrome124", timeout=30.0).text
    abs_urls = sorted(set(re.findall(r"https://www\.green-acres\.pt/[^\"'<> ]+\.htm", t)))
    rel_urls = sorted(set(re.findall(r"/(?:en/)?properties/[^\"'<> ]+\.htm", t)))
    weird = sorted(set(re.findall(r"/[A-Za-z0-9_-]{8,20}\.htm", t)))
    print("absolute .htm urls:", len(abs_urls))
    print("sample:", abs_urls[:10])
    print("relative .htm urls:", len(rel_urls))
    print("sample:", rel_urls[:10])
    print("weird *.htm paths:", len(weird))
    print("sample:", weird[:20])

    apiish = sorted(
        {
            u
            for u in re.findall(r"https?://[^\"'<> ]+", t)
            if any(x in u.lower() for x in ["/api", "api.", "graphql", "algolia", "elastic", "search?"])
        }
    )
    print("api-ish absolute urls:", len(apiish))
    for u in apiish[:30]:
        print("-", u)

    jsonish = sorted(set(re.findall(r"/[^\"'<> ]+\.json[^\"'<> ]*", t)))
    print("json-ish paths:", len(jsonish))
    for p in jsonish[:40]:
        print("-", p)


if __name__ == "__main__":
    main()
