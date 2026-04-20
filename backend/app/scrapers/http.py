from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
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
# Typical residential ask; used to prefer the real ask when the card text also contains spurious huge numbers.
_DEFAULT_SOFT_CAP_EUR = 2_500_000.0
# PT cards sometimes concatenate a small prefix (e.g. gallery "(15)") before "275 000 €", yielding "15 275 000 €".
_DEJUNK_PREFIX_MIN_PARSED_EUR = 12_000_000.0


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


def _variants_space_grouped_pt_price(
    raw: str,
    *,
    soft_cap_eur: float | None = _DEFAULT_SOFT_CAP_EUR,
    min_tail_eur: float = 50_000.0,
    glue_ratio: float = 25.0,
) -> list[float]:
    """
    Parse a PT-style space-grouped amount and, when the full span looks **inflated** past
    ``soft_cap_eur``, add **tail** candidates (e.g. gallery ``36`` + ``495 000`` → ``36 495 000``).

    Tails are only added when ``whole / tail > glue_ratio`` so real asks like ``8 500 000`` €
    (8.5M) are not split into a bogus ``500 000`` tail.
    """
    raw = (raw or "").strip().replace("\xa0", " ")
    if not raw:
        return []
    seen: set[float] = set()
    out: list[float] = []

    def push(v: float | None) -> None:
        if v is None or v in seen:
            return
        seen.add(v)
        out.append(v)

    parts = raw.split()
    if len(parts) >= 2 and all(re.fullmatch(r"\d{1,3}", p) for p in parts):
        whole_raw = " ".join(parts)
        v_whole = _parse_single_price_token(whole_raw)
        for k in range(0, len(parts)):
            tail = " ".join(parts[k:])
            if not re.fullmatch(r"\d{1,3}(?:\s+\d{3})+", tail):
                continue
            vt = _parse_single_price_token(tail)
            if vt is None:
                continue
            if k == 0:
                push(vt)
                continue
            if soft_cap_eur is None:
                push(vt)
                continue
            if v_whole is None or v_whole <= soft_cap_eur:
                continue
            if vt < min_tail_eur or vt > soft_cap_eur:
                continue
            if v_whole / vt <= glue_ratio:
                continue
            push(vt)
        return out
    push(_parse_single_price_token(raw))
    return out


def _drop_subsumed_currency_group_matches(matches: list[re.Match[str]], *, group: int = 1) -> list[re.Match[str]]:
    """Remove shorter ``N NN NNN`` spans that are strictly inside another match (avoids ``500 000`` inside ``12 500 000``)."""
    if len(matches) <= 1:
        return matches
    spans = [(m.start(group), m.end(group)) for m in matches]
    out: list[re.Match[str]] = []
    for i, m in enumerate(matches):
        a, b = spans[i]
        subsumed = False
        for j in range(len(matches)):
            if i == j:
                continue
            sa, sb = spans[j]
            if sa <= a and b <= sb and (sa < a or sb > b):
                subsumed = True
                break
        if not subsumed:
            out.append(m)
    return out


def _choose_price_candidate(values: list[float], *, soft_cap_eur: float | None) -> float | None:
    if not values:
        return None
    if soft_cap_eur is not None:
        under = [v for v in values if v <= soft_cap_eur]
        if under:
            return max(under)
    return max(values)


def parse_price_per_sqm_eur(text: str | None) -> float | None:
    """
    Parse a portal's ``€/m²`` figure from the price tile (e.g. ``1 719 €/m²`` next to ``275 000 €``).

    Uses a looser numeric range than total-ask parsing (per-m² is usually hundreds–low thousands).
    """
    if not text:
        return None
    t = text.replace("\xa0", " ")
    m = re.search(
        r"(\d{1,3}(?:\s+\d{3})*(?:[.,]\d{1,2})?|\d{3,5})\s*(?:€|eur)?\s*/\s*m\s*[²2]\b",
        t,
        re.I,
    )
    if not m:
        return None
    raw = m.group(1).strip()
    compact = raw.replace(" ", "").replace("\u00a0", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", compact):
        compact = compact.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", compact):
        compact = compact.replace(",", "")
    if compact.count(",") == 1 and compact.count(".") == 0 and re.search(r",\d{1,2}$", compact):
        compact = compact.replace(",", ".")
    try:
        v = float(compact)
    except ValueError:
        return None
    if not (120.0 <= v <= 35_000.0):
        return None
    return v


def strip_price_per_sqm_suffix(text: str) -> str:
    """Drop a trailing ``… 1 719 €/m²`` fragment so list-price parsing does not see two € amounts."""
    if not text:
        return text
    parts = re.split(
        r"\s+(?:\d[\d\s.\u00a0]{0,14}\s*(?:€\s*)?/\s*m\s*²|\d[\d\s.\u00a0]{0,14}\s*(?:€\s*)?/\s*m2\b)",
        text,
        maxsplit=1,
        flags=re.I,
    )
    return parts[0].strip()


def strip_price_element_decorations(price_el: Tag | None) -> None:
    """
    Remove gallery / photo-count chips portals embed inside the price container so
    ``get_text`` does not prepend ``30`` to ``360 000 €`` (in-place on the tag tree).
    """
    if price_el is None or not isinstance(price_el, Tag):
        return
    gallery_tokens = (
        "photo",
        "picture",
        "gallery",
        "image-count",
        "image_count",
        "imagens",
        "fotos",
        "swiper",
        "carousel",
    )
    protected = ("ad-price", "listing-item-price", "offer-price", "listing-price", "price-value")

    for tag in list(price_el.find_all(attrs={"data-cy": True})):
        if tag is price_el:
            continue
        cy = str(tag.get("data-cy") or "").lower()
        if any(p in cy for p in protected) and not any(g in cy for g in gallery_tokens):
            continue
        if any(g in cy for g in gallery_tokens):
            tag.decompose()
            continue

    for tag in list(price_el.find_all(True)):
        if tag is price_el:
            continue
        cls = " ".join(tag.get("class") or []).lower()
        if not cls:
            continue
        if any(g in cls for g in ("photocount", "photo-count", "gallery-count", "image-count", "picture-count")):
            tag.decompose()


def dejunk_concatenated_listing_price(
    text: str,
    *,
    soft_cap_eur: float = _DEFAULT_SOFT_CAP_EUR,
) -> str:
    """
    Repair price lines where a small integer was merged before a PT-grouped ask (e.g. ``15`` + ``275 000 €``).
    Only rewrites matches that parse as very large (see threshold) so genuine ~12M asks stay intact.
    """
    if not text:
        return text
    out: list[str] = []
    last = 0
    for m in re.finditer(r"(\d{1,3}(?:\s+\d{3})+)\s*(?:€|eur)\b", text, re.I):
        raw = m.group(1)
        v = _parse_single_price_token(raw)
        repl_body = raw
        if (
            v is not None
            and v >= _DEJUNK_PREFIX_MIN_PARSED_EUR
            and soft_cap_eur is not None
            and v > soft_cap_eur
        ):
            parts = raw.split()
            if len(parts) >= 3 and all(re.fullmatch(r"\d{1,3}", p) for p in parts):
                alt = " ".join(parts[1:])
                v2 = _parse_single_price_token(alt)
                # Require the tail to be a small fraction of the inflated parse so we do not turn
                # a real ``12 500 000`` € ask into ``500 000`` (12 was millions, not a photo count).
                if (
                    v2 is not None
                    and v is not None
                    and v > 0
                    and 50_000 <= v2 <= soft_cap_eur
                    and (v2 / v) < 0.03
                ):
                    repl_body = alt
        out.append(text[last : m.start(1)])
        out.append(repl_body)
        last = m.end(1)
    out.append(text[last:])
    return "".join(out)


def parse_eur_price(
    text: str | None,
    *,
    soft_cap_eur: float | None = _DEFAULT_SOFT_CAP_EUR,
) -> float | None:
    """
    Extract a plausible total asking price from noisy card HTML.

    Search-result cards often contain small integers (ids, counts); the old regex
    returned the first ``\\d+`` (e.g. 1–9). We collect several PT-style patterns and
    pick the largest value in a realistic sale range, and skip fragments near m².
    """
    if not text:
        return None
    t = dejunk_concatenated_listing_price(strip_price_per_sqm_suffix(text.replace("\xa0", " ")))
    euro_vals: list[float] = []
    other_vals: list[float] = []

    def add_euro_raw(raw: str) -> None:
        v = _parse_single_price_token(raw)
        if v is not None:
            euro_vals.append(v)

    def extend_euro_from_grouped(raw: str) -> None:
        for v in _variants_space_grouped_pt_price(raw, soft_cap_eur=soft_cap_eur):
            euro_vals.append(v)

    def add_other_val(v: float) -> None:
        other_vals.append(v)

    # Prefer PT space-grouped amounts next to € / EUR so "T3 275 000 €" is not read as "3 275 000 €".
    _ccy = r"(?:€|eur)"
    _eur_grouped = r"\d{1,3}(?:\s+\d{3})+(?:,\d{2})?"
    for m in re.finditer(rf"{_ccy}\s*({_eur_grouped})", t, re.I):
        extend_euro_from_grouped(m.group(1))
    trail_ccy = list(re.finditer(rf"(?:^|[^\w])({_eur_grouped})\s*{_ccy}\b", t, re.I))
    for m in _drop_subsumed_currency_group_matches(trail_ccy):
        extend_euro_from_grouped(m.group(1))

    if not euro_vals:
        # Fallback for portals that omit thousand spaces (e.g. "€242500")
        for m in re.finditer(rf"{_ccy}\s*([\d\s.\u00a0]{{4,22}})", t, re.I):
            inner = m.group(1).strip().replace("\xa0", " ")
            if re.fullmatch(r"\d{1,3}(?:\s+\d{3})+", inner):
                extend_euro_from_grouped(inner)
            else:
                add_euro_raw(inner)
        trail_loose = list(re.finditer(rf"([\d\s.\u00a0]{{4,22}})\s*{_ccy}\b", t, re.I))
        for m in _drop_subsumed_currency_group_matches(trail_loose):
            inner = m.group(1).strip().replace("\xa0", " ")
            if re.fullmatch(r"\d{1,3}(?:\s+\d{3})+", inner):
                extend_euro_from_grouped(inner)
            else:
                add_euro_raw(inner)

    # Weaker patterns often glue unrelated digits (e.g. image count "15" + "275 000"); only use them if € did not match.
    if not euro_vals:
        # Grouped thousands with spaces: 242 500
        for m in re.finditer(r"\b\d{1,3}(?:\s+\d{3})+(?:,\d{2})?\b", t):
            span = m.group(0)
            end = m.end()
            tail = t[end : end + 12].lower()
            if "m²" in tail or "/m" in tail or "m2" in tail or "eur/m" in tail:
                continue
            for v in _variants_space_grouped_pt_price(span, soft_cap_eur=soft_cap_eur):
                other_vals.append(v)

        # Dotted thousands: 242.500
        for m in re.finditer(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b", t):
            v = _parse_single_price_token(m.group(0))
            if v is not None:
                other_vals.append(v)

        # Plain large integers (Idealista-style) — skip huge unformatted values (often analytics / listing ids).
        for m in re.finditer(r"\b(\d{5,8})\b", t):
            token = m.group(1)
            if len(token) >= 7:
                try:
                    if int(token) >= 10_000_000:
                        continue
                except ValueError:
                    pass
            v = _parse_single_price_token(token)
            if v is not None:
                other_vals.append(v)

    pool = euro_vals if euro_vals else other_vals
    return _choose_price_candidate(pool, soft_cap_eur=soft_cap_eur)


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
