import sys

sys.path.append(r"d:\project\Daily Property Finder\backend")

from app.scrapers.http import fetch_html


def main():
    html = fetch_html("https://www.green-acres.pt/apartament/madeira").html
    idxs = []
    start = 0
    while True:
        i = html.find(".htm", start)
        if i == -1:
            break
        idxs.append(i)
        start = i + 4
    print("occurrences", len(idxs))
    for i in idxs[:10]:
        print("\n--- context ---")
        print(html[max(0, i - 120) : i + 120].replace("\n", " "))


if __name__ == "__main__":
    main()
