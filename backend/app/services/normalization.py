import hashlib, re, unicodedata
from urllib.parse import urlparse, urlunparse

from app.config import settings

PROPERTY_MAP = {
    "moradia": "house",
    "villa": "villa",
    "house": "house",
    "terreno": "land",
    "terrenos": "land",
    "lote": "land",
    "plot": "land",
    "land": "land",
    "quinta": "house",
    "penthouse": "apartment",
    "apartamento": "apartment",
    "apartment": "apartment",
    # igolaizola/idealista-scraper uses Idealista typology strings
    "flat": "apartment",
    "duplex": "apartment",
    "loft": "apartment",
    "detachedhouse": "house",
    "semidetachedhouse": "house",
    "terracedhouse": "house",
    "countryhouse": "house",
}

HARD_ALLOWED_PROPERTY_TYPES = {"house", "villa", "apartment"}


def _client_property_types() -> set[str]:
    return {p.strip().lower() for p in settings.allowed_property_types_csv.split(",") if p.strip()}


def _client_price_bounds_eur() -> tuple[float, float]:
    return (float(settings.client_budget_min_eur), float(settings.client_budget_max_eur))
def normalize_text(value: str | None) -> str | None:
    if not value: return None
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower().strip()
    return re.sub(r"\s+", " ", value)
def canonicalize_url(url: str) -> str:
    p = urlparse(url); return urlunparse((p.scheme, p.netloc, p.path.rstrip("/"), "", "", ""))
def normalize_property_type(value: str | None) -> str:
    n = normalize_text(value or "") or "other"
    return PROPERTY_MAP.get(n, "other")


def passes_hard_property_type_floor(raw: dict) -> tuple[bool, str]:
    """
    Hard ingestion gate for residential-only inventory.
    Allows only house / villa / apartment; blocks land/plot/terrain and unknown types.
    """
    normalized_type = normalize_property_type(raw.get("property_type"))
    return normalized_type in HARD_ALLOWED_PROPERTY_TYPES, normalized_type
def parse_bedrooms(title: str | None, explicit: int | None) -> int | None:
    if explicit is not None: return explicit
    t = normalize_text(title or "") or ""
    # Common patterns: "T2", "T3", "3 bed", "3 bedrooms"
    m = re.search(r"\bt\s*(\d)\b", t) or re.search(r"\b(\d)\s*bed(?:room)?s?\b", t)
    return int(m.group(1)) if m else None


def passes_hard_bedroom_floor(raw: dict, *, min_bedrooms: int | None = None) -> tuple[bool, int | None]:
    """
    Hard ingestion gate: only allow rows with bedrooms >= configured minimum.
    Returns (allowed, resolved_bedrooms).
    """
    floor = int(settings.min_bedrooms if min_bedrooms is None else min_bedrooms)
    beds = parse_bedrooms(raw.get("title"), raw.get("bedrooms"))
    if beds is None:
        return False, None
    return beds >= floor, beds
def build_fingerprint(title, price, location, bedrooms, property_type):
    bucket = int(price // 5000) if price else 0
    payload = "|".join([normalize_text(title or "") or "", str(bucket), normalize_text(location or "") or "", str(bedrooms or ""), normalize_text(property_type or "") or ""])
    return hashlib.sha256(payload.encode()).hexdigest()
def is_eligible(listing: dict) -> bool:
    price, bedrooms, property_type = listing.get("price"), listing.get("bedrooms"), listing.get("property_type")
    listing_type = normalize_text(listing.get("listing_type")) or "sale"
    location = normalize_text(listing.get("location")) or ""
    url = normalize_text(listing.get("url") or listing.get("source_url") or "") or ""

    min_eur, max_eur = _client_price_bounds_eur()
    if price is None or float(price) < min_eur or float(price) > max_eur:
        return False
    # Plots / land rarely expose bedroom counts on portals; do not apply bedroom floor.
    if property_type != "land":
        if bedrooms is None or int(bedrooms) < int(settings.min_bedrooms):
            return False
    if property_type not in _client_property_types():
        return False
    if listing_type != "sale":
        return False

    # Madeira-wide: accept explicit mentions OR common Madeira-ish URL tokens.
    haystack = f"{location} {url}"
    return any(
        x in haystack
        for x in [
            "madeira",
            "funchal",
            "camara-de-lobos",
            "câmara de lobos",
            "machico",
            "santa cruz",
            "calheta",
            "ribeira brava",
            "santana",
            "sao vicente",
            "porto moniz",
            "ponta do sol",
        ]
    )
def normalize_listing(raw: dict) -> dict:
    title = raw.get("title", "").strip(); property_type = normalize_property_type(raw.get("property_type")); bedrooms = parse_bedrooms(title, raw.get("bedrooms")); location = raw.get("location"); canonical_url = canonicalize_url(raw["url"])
    normalized = {"source_listing_id": raw.get("source_listing_id"), "canonical_url": canonical_url, "source_url": raw["url"], "title": title, "normalized_title": normalize_text(title), "description": raw.get("description"), "normalized_description": normalize_text(raw.get("description")), "price": raw.get("price"), "currency": raw.get("currency", "EUR"), "location_text": location, "normalized_location": normalize_text(location), "area_name": raw.get("area_name"), "municipality": raw.get("municipality"), "bedrooms": bedrooms, "bathrooms": raw.get("bathrooms"), "property_type": property_type, "listing_type": normalize_text(raw.get("listing_type")) or "sale", "image_url": raw.get("image_url"), "published_at": raw.get("published_at")}
    normalized["fingerprint"] = build_fingerprint(normalized["title"], normalized["price"], normalized["location_text"], normalized["bedrooms"], normalized["property_type"])
    normalized["eligibility_status"] = "eligible" if is_eligible({"price": normalized["price"], "bedrooms": normalized["bedrooms"], "property_type": normalized["property_type"], "listing_type": normalized["listing_type"], "location": normalized["location_text"], "url": normalized["source_url"]}) else "filtered_out"
    return normalized
