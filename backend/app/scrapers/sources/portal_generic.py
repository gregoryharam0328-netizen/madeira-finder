from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from app.config import settings
from app.scrapers.base import BaseScraper
from app.scrapers.http import (
    fetch_html,
    guess_bedrooms_from_text,
    guess_property_type_from_text,
    parse_eur_price,
    parse_price_per_sqm_eur,
    soup,
    strip_price_element_decorations,
)


@dataclass(frozen=True)
class PortalSelectors:
    # Optional CSS selectors (site-specific tuning goes here)
    card: str | None = None
    title: str | None = None
    price: str | None = None
    location: str | None = None


class PortalSearchScraper(BaseScraper):
    """
    Best-effort HTML scraper for portal search result pages.

    This is intentionally pragmatic: portals change markup frequently, so each adapter
    should provide a stable search URL + selectors where possible.
    """

    base_domain: str
    listing_href_regex: str
    selectors: PortalSelectors = PortalSelectors()
    requires_js: bool = False

    def build_search_url(self) -> str:  # pragma: no cover
        raise NotImplementedError

    @property
    def max_listings(self) -> int:
        return int(settings.scrape_max_listings_per_source)

    def _within_domain(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host.endswith(self.base_domain)

    def _listing_card_root(self, card) -> object:
        """
        Many portals wrap the hit target <a> in a tile; title/price/image live in siblings/parent.
        Prefer a parent article/li so selectors and get_text see the full listing.
        """
        if getattr(card, "name", None) != "a":
            return card
        for tag_name in ("article", "li", "section"):
            p = card.find_parent(tag_name)
            if p is not None:
                return p
        return card.parent or card

    def _image_from_card(self, card, base_url: str) -> str | None:
        """Best-effort cover image from a result card (selectors vary by portal)."""
        for sel in (
            "img[data-cy='listing-card-image']",
            "img[data-cy='listing-item-image']",
            "img[data-cy='ad-image']",
            "img[data-cy='picture-url']",
            "picture source[srcset]",
            "picture img",
            "img[srcset]",
            "img[src]",
        ):
            el = card.select_one(sel)
            if not el:
                continue
            src = (el.get("src") or el.get("data-src") or el.get("data-lazy") or "").strip()
            if not src and el.get("srcset"):
                # "url 1x, url2 2x" — take first URL
                piece = el["srcset"].split(",")[0].strip().split()[0]
                src = piece.strip()
            if not src or src.startswith("data:"):
                continue
            if "placeholder" in src.lower() and "1x1" in src:
                continue
            return urljoin(base_url, src)
        return None

    def _extract_from_card(self, card) -> dict[str, object | None]:
        title_el = card.select_one(self.selectors.title) if self.selectors.title else None
        price_el = card.select_one(self.selectors.price) if self.selectors.price else None
        loc_el = card.select_one(self.selectors.location) if self.selectors.location else None

        if price_el is not None:
            strip_price_element_decorations(price_el)

        title = (title_el.get_text(" ", strip=True) if title_el else None) or None
        price_txt = price_el.get_text(" ", strip=True) if price_el else None
        blob = card.get_text(" ", strip=True)
        price = parse_eur_price(price_txt) or parse_eur_price(blob)
        location = (loc_el.get_text(" ", strip=True) if loc_el else None) or None
        price_per_sqm = parse_price_per_sqm_eur(price_txt) or parse_price_per_sqm_eur(blob)

        hint = " ".join(x for x in (title, location, blob[:800]) if x)
        bedrooms = guess_bedrooms_from_text(hint)
        prop_type = guess_property_type_from_text(hint)
        return {
            "title": title,
            "price": price,
            "price_per_sqm_eur": price_per_sqm,
            "location": location,
            "bedrooms": bedrooms,
            "property_type": prop_type,
        }

    def _enrich_meta_from_blob(self, card, meta: dict[str, object | None]) -> dict[str, object | None]:
        blob = card.get_text(" ", strip=True)
        if meta.get("price") is None:
            meta["price"] = parse_eur_price(blob)
        if meta.get("title") is None:
            # Often the first sentence chunk before a location list.
            meta["title"] = blob.split("€")[0].strip() if "€" in blob else blob[:120].strip()
        if meta.get("bedrooms") is None:
            meta["bedrooms"] = guess_bedrooms_from_text(blob)
        if meta.get("property_type") is None:
            meta["property_type"] = guess_property_type_from_text(blob)
        if meta.get("location") is None:
            m = re.search(r"(Funchal|Câmara de Lobos|Camara de Lobos|Santa Cruz|Calheta|Machico|Ponta do Sol|Ribeira Brava|Santana|São Vicente|Sao Vicente|Porto Moniz|Caniço|Canico).*?(Madeira|Ilha da Madeira)", blob, flags=re.IGNORECASE)
            if m:
                meta["location"] = m.group(0)
        return meta

    def fetch_listings(self) -> list[dict]:
        search_url = self.build_search_url()
        fetched = fetch_html(search_url, force_playwright=bool(getattr(self, "requires_js", False)))
        if fetched.status_code >= 400:
            return []

        doc = soup(fetched.html)
        items: list[dict] = []

        if self.selectors.card:
            cards = doc.select(self.selectors.card)
            for card in cards:
                a = card if card.name == "a" else card.select_one("a[href]")
                if not a:
                    continue
                href = a.get("href")
                if not href or not re.search(self.listing_href_regex, href):
                    continue
                listing_url = urljoin(search_url, href)
                if not self._within_domain(listing_url):
                    continue

                meta_card = self._listing_card_root(a)

                meta = self._extract_from_card(meta_card)
                meta = self._enrich_meta_from_blob(meta_card, meta)

                if meta.get("price") is None:
                    continue

                title_el = meta_card.select_one(self.selectors.title) if self.selectors.title else None
                title_from_selector = title_el.get_text(" ", strip=True) if title_el else None
                title = meta.get("title") or title_from_selector or (a.get_text(" ", strip=True) or "Listing")
                image_url = self._image_from_card(meta_card, search_url)
                pps = meta.get("price_per_sqm_eur")
                row: dict = {
                    "source_listing_id": None,
                    "url": listing_url,
                    "title": str(title),
                    "price": float(meta["price"]),
                    "currency": "EUR",
                    "location": meta.get("location"),
                    "bedrooms": meta.get("bedrooms"),
                    "property_type": meta.get("property_type") or "other",
                    "listing_type": "sale",
                    "description": None,
                    "image_url": image_url,
                }
                if pps is not None:
                    row["price_per_sqm_eur"] = float(pps)
                items.append(row)

                if len(items) >= self.max_listings:
                    return items

            return items

        # Fallback: scan anchors (less reliable, but works on simpler templates)
        for a in doc.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            if not re.search(self.listing_href_regex, href):
                continue
            listing_url = urljoin(search_url, href)
            if not self._within_domain(listing_url):
                continue

            title = a.get_text(" ", strip=True) or "Listing"
            root = self._listing_card_root(a)
            parent_text = root.get_text(" ", strip=True) if root is not None else ""

            price = parse_eur_price(parent_text)
            if price is None:
                continue

            bedrooms = guess_bedrooms_from_text(f"{title} {parent_text}")
            prop_type = guess_property_type_from_text(f"{title} {parent_text}")
            pps = parse_price_per_sqm_eur(parent_text)

            image_url = self._image_from_card(root, search_url)
            row_fb: dict = {
                "source_listing_id": None,
                "url": listing_url,
                "title": title,
                "price": float(price),
                "currency": "EUR",
                "location": None,
                "bedrooms": bedrooms,
                "property_type": prop_type or "other",
                "listing_type": "sale",
                "description": None,
                "image_url": image_url,
            }
            if pps is not None:
                row_fb["price_per_sqm_eur"] = float(pps)
            items.append(row_fb)

            if len(items) >= self.max_listings:
                break

        return items
