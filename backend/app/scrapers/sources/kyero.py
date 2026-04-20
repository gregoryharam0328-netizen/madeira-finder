from __future__ import annotations

import json
import logging
from typing import Any

from app.scrapers.http import fetch_html, parse_eur_price, soup
from app.scrapers.sources.portal_generic import PortalSearchScraper, PortalSelectors
from app.scrapers.urls import kyero_default_search_url

log = logging.getLogger(__name__)


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return x if 3_000 <= x <= 50_000_000 else None
    if isinstance(v, str):
        p = parse_eur_price(v)
        return p
    return None


def _price_from_json_ld(obj: Any, depth: int = 0) -> float | None:
    if depth > 14 or obj is None:
        return None
    if isinstance(obj, dict):
        for key in ("price", "lowPrice", "highPrice"):
            if key in obj:
                p = _float_or_none(obj.get(key))
                if p:
                    return p
        for v in obj.values():
            p = _price_from_json_ld(v, depth + 1)
            if p:
                return p
    if isinstance(obj, list):
        for it in obj:
            p = _price_from_json_ld(it, depth + 1)
            if p:
                return p
    return None


def kyero_detail_price_image(url: str) -> dict[str, Any]:
    """
    Kyero SERP tiles are often link-only shells: wrong tiny prices and no cover image.
    The property page exposes og:image and structured prices reliably.
    """
    out: dict[str, Any] = {}
    fr = fetch_html(url, force_playwright=False)
    html = fr.html or ""
    if fr.status_code >= 400 or len(html) < 12_000 or "og:image" not in html.lower():
        fr = fetch_html(url, force_playwright=True)
        html = fr.html or ""
    if not html or fr.status_code >= 400:
        return out

    doc = soup(html)
    for sel in ('meta[property="og:image"]', 'meta[property="og:image:url"]'):
        el = doc.select_one(sel)
        if el and (el.get("content") or "").strip():
            out["image_url"] = el["content"].strip()
            break
    if not out.get("image_url"):
        tw = doc.select_one('meta[name="twitter:image"]')
        if tw and (tw.get("content") or "").strip():
            out["image_url"] = tw["content"].strip()

    for script in doc.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            block = json.loads(raw)
        except json.JSONDecodeError:
            continue
        p = _price_from_json_ld(block)
        if p:
            out["price"] = p
            break

    if not out.get("price"):
        main = doc.select_one("main")
        blob = (main.get_text(" ", strip=True) if main else "") or doc.get_text(" ", strip=True)
        p = parse_eur_price(blob[:40_000])
        if p:
            out["price"] = p
    return out


class KyeroScraper(PortalSearchScraper):
    name = "Kyero"
    base_domain = "kyero.com"
    listing_href_regex = r"^/pt/property/"
    selectors = PortalSelectors(card='a[href^="/pt/property/"]')
    requires_js = True

    def build_search_url(self) -> str:
        return kyero_default_search_url()

    def fetch_listings(self) -> list[dict]:
        base = super().fetch_listings()
        seen: set[str] = set()
        out: list[dict] = []
        for item in base:
            url = (item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            try:
                ex = kyero_detail_price_image(url)
            except Exception:
                log.debug("Kyero detail scrape failed for %s", url, exc_info=True)
                ex = {}
            if ex.get("price") is not None:
                item["price"] = float(ex["price"])
            if ex.get("image_url"):
                item["image_url"] = ex["image_url"]
            out.append(item)
        return out
