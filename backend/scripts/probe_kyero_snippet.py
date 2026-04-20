from curl_cffi import requests as r


def main():
    url = "https://www.kyero.com/pt/portugal/area?g%5B%5D=5&location_id=57483&payment_scheme_id=0"
    html = r.get(url, impersonate="chrome124", timeout=30.0).text
    idx = html.lower().find("min_price")
    print("idx", idx)
    print(html[idx - 200 : idx + 400])


if __name__ == "__main__":
    main()
