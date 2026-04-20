from __future__ import annotations

import re
from urllib.parse import urljoin

from app.scrapers.base import BaseScraper
from app.scrapers.http import fetch_html, guess_bedrooms_from_text, guess_property_type_from_text, parse_eur_price, soup


_REF_RE = re.compile(r"^/comprar/(?:C\d{4}-\d{5}|\d{4}-\d{5})$")


class Century21BuyScraper(BaseScraper):
    name = "Century 21 Portugal"

    def build_search_url(self) -> str:
        return "https://www.century21.pt/comprar"

    @staticmethod
    def _mentions_madeira(blob: str) -> bool:
        b = blob.lower()
        return any(
            x in b
            for x in [
                "madeira",
                "ilha da madeira",
                "funchal",
                "câmara de lobos",
                "camara de lobos",
                "santa cruz",
                "machico",
                "calheta",
                "ponta do sol",
                "ribeira brava",
                "santana",
                "são vicente",
                "sao vicente",
                "porto moniz",
                "caniço",
                "canico",
            ]
        )

    def fetch_listings(self) -> list[dict]:
        search_url = self.build_search_url()
        html = fetch_html(search_url, force_playwright=True).html
        doc = soup(html)
        items: list[dict] = []

        for a in doc.select("a[href]"):
            href = a.get("href") or ""
            if not _REF_RE.match(href):
                continue

            listing_url = urljoin(search_url, href)
            # Pull a slightly wider card text (title often in heading near the link)
            card = a.find_parent("article") or a.find_parent("li") or a.find_parent("div") or a
            blob = card.get_text(" ", strip=True)
            if not self._mentions_madeira(blob):
                continue

            price = parse_eur_price(blob)
            if price is None:
                continue

            title = a.get_text(" ", strip=True) or blob[:120]
            bedrooms = guess_bedrooms_from_text(blob)
            prop_type = guess_property_type_from_text(blob) or "other"

            ref = href.split("/")[-1]
            items.append(
                {
                    "source_listing_id": ref,
                    "url": listing_url,
                    "title": title,
                    "price": float(price),
                    "currency": "EUR",
                    "location": None,
                    "bedrooms": bedrooms,
                    "property_type": prop_type,
                    "listing_type": "sale",
                    "description": None,
                    "image_url": None,
                }
            )

            if len(items) >= 40:
                break

        return items
