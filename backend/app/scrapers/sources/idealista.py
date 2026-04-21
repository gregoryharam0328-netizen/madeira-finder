from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.services.normalization import _client_price_bounds_eur
from app.scrapers.apify_client import ApifyError, run_actor_sync
from app.scrapers.base import BaseScraper

_log = logging.getLogger(__name__)

# Community actor: https://apify.com/igolaizola/idealista-scraper
DEFAULT_IDEALISTA_ACTOR = "igolaizola~idealista-scraper"


def _idealista_location_id() -> str:
    """Idealista location ID (e.g. Madeira municipal) or parsed from an override search URL."""
    url = (settings.idealista_search_url or "").strip()
    if url:
        m = re.search(r"(0-EU-[A-Z]{2}-[\w-]+)", url)
        if m:
            return m.group(1)
    return settings.idealista_location_code


def _bedrooms_filter() -> list[str]:
    """Actor expects e.g. ['2','3','4']; enforce minimum bedrooms from settings."""
    lo = max(0, int(settings.min_bedrooms))
    if lo <= 0:
        return []
    out: list[str] = []
    if lo == 1:
        out.append("1")
    for n in range(max(2, lo), 6):
        out.append(str(n))
    return out


def _home_type_filter() -> list[str]:
    """Map client CSV types to igolaizola/idealista-scraper `homeType` enum values."""
    allowed = {p.strip().lower() for p in settings.allowed_property_types_csv.split(",") if p.strip()}
    mapping: dict[str, list[str]] = {
        "house": ["detachedHouse", "semiDetachedHouse", "terracedHouse", "countryHouse"],
        "apartment": ["flat", "penthouse", "duplex", "apartment", "loft"],
        "villa": ["villa"],
    }
    out: list[str] = []
    for key in allowed:
        out.extend(mapping.get(key, []))
    return list(dict.fromkeys(out))


def _map_apify_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """
    Map igolaizola/idealista-scraper dataset rows into our normalize_listing() shape.
    See actor README sample + optional `_details` / `_stats` when enabled.
    """
    url = item.get("url")
    if not url:
        return None

    title = item.get("title")
    if not title and isinstance(item.get("suggestedTexts"), dict):
        title = item["suggestedTexts"].get("title")
    title = title or "Listing"

    price = item.get("price")
    if price is None and isinstance(item.get("priceInfo"), dict):
        inner = item["priceInfo"].get("price")
        if isinstance(inner, dict):
            price = inner.get("amount")

    rooms = item.get("rooms") if item.get("rooms") is not None else item.get("bedrooms")
    if rooms is None and isinstance(item.get("_details"), dict):
        rooms = item["_details"].get("rooms")

    prop = item.get("propertyType")
    if isinstance(item.get("detailedType"), dict) and item["detailedType"].get("typology"):
        prop = item["detailedType"]["typology"]

    image_url = item.get("thumbnail")
    if not image_url and isinstance(item.get("multimedia"), dict):
        imgs = item["multimedia"].get("images") or []
        if imgs and isinstance(imgs[0], dict):
            image_url = imgs[0].get("url")

    loc_parts = [item.get("municipality"), item.get("province"), item.get("district")]
    location = ", ".join(str(p) for p in loc_parts if p)

    desc = item.get("description")
    if not desc and isinstance(item.get("_details"), dict):
        desc = item["_details"].get("description")

    published = item.get("publicationDate") or item.get("date")

    bedrooms: int | None = None
    if rooms is not None and rooms != "":
        try:
            bedrooms = int(float(str(rooms).strip().replace(",", ".")))
        except (TypeError, ValueError):
            bedrooms = None

    price_f: float | None = None
    if price is not None and price != "":
        try:
            price_f = float(str(price).strip().replace(",", ".").replace(" ", "").replace("€", ""))
        except (TypeError, ValueError):
            price_f = None

    return {
        "source_listing_id": str(item.get("propertyCode") or item.get("id") or "") or None,
        "url": str(url),
        "title": str(title),
        "price": price_f,
        "currency": "EUR",
        "location": location or None,
        "bedrooms": bedrooms,
        "bathrooms": int(item["bathrooms"]) if item.get("bathrooms") is not None else None,
        "property_type": str(prop).lower() if prop else None,
        "listing_type": "sale",
        "description": desc,
        "image_url": str(image_url) if image_url else None,
        "published_at": published,
        "area_name": item.get("district"),
        "municipality": item.get("municipality"),
    }


class IdealistaScraper(BaseScraper):
    name = "Idealista"

    def fetch_listings(self) -> list[dict]:
        if not settings.apify_token:
            _log.warning(
                "Idealista skipped: APIFY_TOKEN is not set in the backend environment "
                "(add it to backend/.env — without it this source contributes no rows)."
            )
            return []

        actor_id = (settings.idealista_apify_actor_id or DEFAULT_IDEALISTA_ACTOR).strip()
        min_eur, max_eur = _client_price_bounds_eur()
        min_eur = int(min_eur)
        max_eur = int(max_eur)

        run_input: dict[str, Any] = {
            "operation": "sale",
            "propertyType": "homes",
            "country": "pt",
            "location": _idealista_location_id(),
            "maxItems": int(settings.scrape_max_listings_per_source),
            "sortBy": "mostRecent",
            "minPrice": str(min_eur),
            "maxPrice": str(max_eur),
            "fetchDetails": bool(settings.idealista_apify_fetch_details),
            "fetchStats": bool(settings.idealista_apify_fetch_stats),
            "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        }

        beds = _bedrooms_filter()
        if beds:
            run_input["bedrooms"] = beds

        home_types = _home_type_filter()
        if home_types:
            run_input["homeType"] = home_types

        try:
            items = run_actor_sync(
                actor_id=actor_id,
                run_input=run_input,
                timeout_seconds=int(settings.apify_actor_timeout_seconds),
            )
        except ApifyError:
            return []

        out: list[dict] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            mapped = _map_apify_item(it)
            if mapped:
                out.append(mapped)
        return out
