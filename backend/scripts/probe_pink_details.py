import re

from curl_cffi import requests as r


def main():
    u = "https://www.pinkrealestate.pt/all-properties/buy-apartments-madeira-island-portugal"
    html = r.get(u, impersonate="chrome124", timeout=30.0).text
    hrefs = re.findall(r"href=\"([^\"]+)\"", html)
    hits = [h for h in hrefs if "/properties/details" in h]
    print("details links", len(hits))
    print("sample:", hits[:10])


if __name__ == "__main__":
    main()
