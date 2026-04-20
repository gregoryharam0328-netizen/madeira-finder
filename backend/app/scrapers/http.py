from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from playwright.sync_api import sync_playwright

from app.config import settings
from app.win_asyncio import apply_windows_proactor_policy

log = logging.getLogger(__name__)

apply_windows_proactor_policy()

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9,pt;q=0.8",
}


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    html: str


def _looks_like_bot_wall(html: str) -> bool:
    h = html.lower()
    needles = [
        "please enable javascript",
        "cf-browser-verification",
        "captcha",
        "access denied",
        "request blocked",
        "attention required",
    ]
    return any(n in h for n in needles)


def fetch_html_playwright(url: str) -> FetchResult:
    apply_windows_proactor_policy()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(locale="en-GB", user_agent=DEFAULT_HEADERS["User-Agent"])
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=int(settings.scrape_timeout_seconds * 1000))
                # Many SPAs never reach "networkidle" due to analytics/long-polling; give the UI a moment to hydrate.
                page.wait_for_timeout(3500)
                html = page.content()
                return FetchResult(url=page.url, status_code=200, html=html)
            finally:
                browser.close()
    except NotImplementedError as exc:
        log.warning(
            "Playwright skipped: asyncio cannot spawn a subprocess on this Windows event loop (%s). "
            "HTML scrapers may return fewer results; use APIFY_TOKEN for Idealista.",
            exc,
        )
        return FetchResult(url=url, status_code=503, html="")


def fetch_html(url: str, *, force_playwright: bool = False) -> FetchResult:
    """
    Fetch HTML for scraping.

    Strategy:
    - Try curl-cffi (browser-like TLS)
    - If blocked / bot wall / empty shell, fall back to Playwright (real browser)
    """
    if force_playwright:
        return fetch_html_playwright(url)

    resp = curl_requests.get(
        url,
        headers=DEFAULT_HEADERS,
        impersonate="chrome124",
        timeout=settings.scrape_timeout_seconds,
        allow_redirects=True,
    )
    html = str(resp.text)
    status = int(resp.status_code)

    if status >= 400 or _looks_like_bot_wall(html) or len(html) < 5000:
        try:
            pw = fetch_html_playwright(url)
            if pw.status_code == 503 or not pw.html:
                pass
            elif len(pw.html) > len(html):
                return pw
        except Exception as exc:
            # Playwright requires `playwright install chromium` on the machine.
            log.debug("Playwright fallback failed for %s: %s", url, exc)

    return FetchResult(url=url, status_code=status, html=html)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# Ignore per-m² lines and breadcrumb digits when picking a list price from noisy HTML.
_MIN_PLAUSIBLE_LISTING_EUR = 3_000.0
_MAX_PLAUSIBLE_LISTING_EUR = 50_000_000.0


def _parse_single_price_token(raw: str) -> float | None:
    """Parse one PT/EU-style price token into a float, or None."""
    raw = raw.strip().replace("\xa0", " ").replace(" ", "")
    if not raw or not re.search(r"\d", raw):
        return None

    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
        raw = raw.replace(",", "")

    if raw.count(",") == 1 and raw.count(".") == 0 and re.search(r",\d{1,2}$", raw):
        raw = raw.replace(",", ".")

    try:
        v = float(raw)
    except ValueError:
        return None
    if not (_MIN_PLAUSIBLE_LISTING_EUR <= v <= _MAX_PLAUSIBLE_LISTING_EUR):
        return None
    return v


def parse_eur_price(text: str | None) -> float | None:
    """
    Extract a plausible total asking price from noisy card HTML.

    Search-result cards often contain small integers (ids, counts); the old regex
    returned the first ``\\d+`` (e.g. 1–9). We collect several PT-style patterns and
    pick the largest value in a realistic sale range, and skip fragments near m².
    """
    if not text:
        return None
    t = text.replace("\xa0", " ")
    candidates: list[float] = []

    def add_if_plausible(raw: str) -> None:
        v = _parse_single_price_token(raw)
        if v is not None:
            candidates.append(v)

    # Strong signals: amount next to € (PT often "242 500 €" or "€ 242 500")
    for m in re.finditer(r"€\s*([\d\s.\u00a0]{4,22})", t):
        add_if_plausible(m.group(1))
    for m in re.finditer(r"([\d\s.\u00a0]{4,22})\s*€", t):
        add_if_plausible(m.group(1))

    # Grouped thousands with spaces: 242 500
    for m in re.finditer(r"\b\d{1,3}(?:\s+\d{3})+(?:,\d{2})?\b", t):
        span = m.group(0)
        end = m.end()
        tail = t[end : end + 12].lower()
        if "m²" in tail or "/m" in tail or "m2" in tail or "eur/m" in tail:
            continue
        add_if_plausible(span)

    # Dotted thousands: 242.500
    for m in re.finditer(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b", t):
        add_if_plausible(m.group(0))

    # Plain large integers (Idealista-style)
    for m in re.finditer(r"\b(\d{5,8})\b", t):
        add_if_plausible(m.group(1))

    if not candidates:
        return None
    return max(candidates)


def guess_bedrooms_from_text(text: str | None) -> int | None:
    if not text:
        return None
    t = text.lower()
    # PT: T2, T3, Tipologia T2; EN: 3 bed
    m = (
        re.search(r"\bt\s*(\d)\b", t)
        or re.search(r"tipologia\s*t\s*(\d)\b", t)
        or re.search(r"\b(\d)\s*(?:quartos?|dormitorios?|dormitórios?)\b", t)
        or re.search(r"\b(\d)\s*bed(?:room)?s?\b", t)
    )
    return int(m.group(1)) if m else None


def guess_property_type_from_text(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower()
    if "apartamento" in t or "apartment" in t or "flat" in t or "penthouse" in t:
        return "apartment"
    if (
        t.startswith("terra ")
        or "terreno" in t
        or "terrenos" in t
        or "lote " in t
        or t.startswith("lote ")
        or " plot " in t
        or t.startswith("plot ")
        or " land " in t
        or "rustica" in t
        or "rústica" in t
        or "rustico" in t
        or "rústico" in t
    ):
        return "land"
    if "moradia" in t or "villa" in t or "house" in t:
        return "house"
    return None
