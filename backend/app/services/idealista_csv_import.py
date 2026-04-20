"""
Import Idealista rows from an Apify dataset CSV (or JSONL) URL into listings / listings_raw.

Strict validation: every stored row must have a plausible EUR price, https image URL,
and a resolved bedroom count (CSV column or Tn in title). Rows that fail are skipped with a log line.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import ListingRaw, ScrapeRun, Source
from app.scrapers.http import DEFAULT_HEADERS
from app.scrapers.sources.idealista import _map_apify_item
from app.services.dedup import upsert_listing
from app.services.normalization import (
    normalize_listing,
    parse_bedrooms,
    passes_hard_bedroom_floor,
    passes_hard_property_type_floor,
)

log = logging.getLogger(__name__)

_MIN_EUR = 5_000.0
_MAX_EUR = 50_000_000.0


def normalize_google_drive_dataset_url(url: str) -> str:
    """
    Turn a Drive file share link into a direct download URL (CSV/JSONL).
    Example: .../file/d/<id>/view -> uc?export=download&id=<id>
    """
    u = (url or "").strip()
    if not u:
        return u
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", u)
    if m and "drive.google.com" in u:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return u


def _ensure_idealista_source(db) -> Source:
    s = db.query(Source).filter(Source.name == "Idealista").first()
    if s:
        return s
    s = Source(name="Idealista", base_url="https://www.idealista.pt", source_type="portal", priority=1)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def fetch_dataset_bytes(url: str) -> bytes:
    """Follow redirects; handle Google Drive virus-scan interstitial HTML."""
    headers = {"User-Agent": DEFAULT_HEADERS["User-Agent"]}
    current = url.strip()
    for _attempt in range(8):
        with httpx.Client(timeout=180.0, follow_redirects=False, headers=headers) as client:
            r = client.get(current)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            current = r.headers["location"]
            continue
        r.raise_for_status()
        body = r.content
        ct = (r.headers.get("content-type") or "").lower()
        if "text/html" in ct and len(body) < 2_000_000:
            text = body.decode("utf-8", errors="ignore")
            m = re.search(r'href="(https://drive\.google\.com/[^"]+confirm=[^"&]+[^"]*)"', text)
            if m:
                current = m.group(1).replace("&amp;", "&")
                continue
            if "text/csv" not in ct and "<html" in text.lower()[:2000]:
                raise RuntimeError(
                    "Download returned HTML instead of CSV — check that the URL is a direct export "
                    "(e.g. https://drive.google.com/uc?export=download&id=FILE_ID) and file is shared."
                )
        return body
    raise RuntimeError("Too many redirects while fetching CSV")


def _norm_keys(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = str(k).strip().lower().replace("\ufeff", "").replace(" ", "").replace("-", "_")
        if isinstance(v, str):
            out[key] = v.strip()
        elif v is None:
            out[key] = ""
        else:
            out[key] = str(v).strip()
    return out


def _pick(n: dict[str, str], *candidates: str) -> str:
    for c in candidates:
        c0 = c.lower().replace(" ", "").replace("-", "_")
        if c0 in n and n[c0]:
            return n[c0]
    for k, v in n.items():
        if not v:
            continue
        k0 = k.lower().replace(" ", "").replace("-", "_")
        for c in candidates:
            c0 = c.lower().replace(" ", "").replace("-", "_")
            if k0 == c0 or k0.endswith("_" + c0):
                return v
    return ""


def _pick_image(n: dict[str, str]) -> str:
    for key in ("thumbnail", "imageurl", "image_url", "mainimage", "coverimage"):
        u = _pick(n, key)
        if u.startswith("http"):
            return u
    for k, v in n.items():
        if not v or not v.startswith("http"):
            continue
        lk = k.lower()
        if "image" in lk or "thumb" in lk or "photo" in lk or lk.endswith("_url"):
            if "idealista" in v or "img" in v or "cdn" in v or "picture" in v:
                return v
    raw = _pick(n, "multimedia", "images", "pictures")
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list) and arr:
                first = arr[0]
                if isinstance(first, dict) and first.get("url"):
                    return str(first["url"]).strip()
                if isinstance(first, str) and first.startswith("http"):
                    return first
        except json.JSONDecodeError:
            pass
    return ""


def _pick_price(n: dict[str, str]) -> float | None:
    for key in ("price", "askingprice", "asking_price", "pricevalue"):
        s = _pick(n, key)
        if not s:
            continue
        try:
            p = float(s.replace(",", ".").replace(" ", "").replace("€", ""))
            if _MIN_EUR <= p <= _MAX_EUR:
                return p
        except ValueError:
            continue
    inner = _pick(n, "priceinfo.price.amount", "priceinfo_price_amount", "priceinfo_price")
    if not inner:
        for k, v in n.items():
            lk = k.lower()
            if "price" in lk and "amount" in lk and v:
                inner = v
                break
    if inner:
        try:
            p = float(inner.replace(",", ".").replace(" ", ""))
            if _MIN_EUR <= p <= _MAX_EUR:
                return p
        except ValueError:
            pass
    return None


def _csv_row_to_apify_item(n: dict[str, str]) -> dict[str, Any] | None:
    url = _pick(n, "url", "link", "propertyurl", "property_url", "listingurl")
    if not url.startswith("http"):
        return None
    title = _pick(n, "title", "name", "suggestedtexts.title")
    price = _pick_price(n)
    rooms_s = _pick(n, "rooms", "bedrooms", "bedroom", "roomnumber")
    rooms: int | None = None
    if rooms_s:
        try:
            rooms = int(float(rooms_s))
        except ValueError:
            rooms = None
    thumb = _pick_image(n)
    prop = _pick(n, "propertytype", "property_type", "typology", "detailedtype", "homestype")
    pcode = _pick(n, "propertycode", "property_code", "id", "listingid", "code")
    municipality = _pick(n, "municipality", "town", "city", "districtname")
    desc = _pick(n, "description", "summary", "text")
    published = _pick(n, "publicationdate", "publication_date", "date", "publishedat")

    item: dict[str, Any] = {
        "url": url,
        "title": title or "Listing",
        "price": price,
        "rooms": rooms,
        "thumbnail": thumb or None,
        "propertyType": prop or None,
        "propertyCode": pcode or None,
        "municipality": municipality or None,
        "description": desc or None,
        "publicationDate": published or None,
    }
    return item


def _validate_mapped_strict(mapped: dict[str, Any]) -> tuple[bool, str]:
    if not mapped.get("url"):
        return False, "missing url"
    p = mapped.get("price")
    try:
        pf = float(p) if p is not None else None
    except (TypeError, ValueError):
        return False, "invalid price"
    if pf is None or not (_MIN_EUR <= pf <= _MAX_EUR):
        return False, f"price out of range ({p})"
    img = (mapped.get("image_url") or "").strip()
    if not img.startswith("https://") and not img.startswith("http://"):
        return False, "missing or non-http image_url"
    beds = mapped.get("bedrooms")
    if beds is None:
        beds = parse_bedrooms(str(mapped.get("title") or ""), None)
    if beds is None:
        return False, "missing bedrooms (no rooms column and no Tn in title)"
    try:
        bi = int(beds)
    except (TypeError, ValueError):
        return False, "invalid bedrooms"
    if bi < 0 or bi > 30:
        return False, "bedrooms implausible"
    if bi < int(settings.min_bedrooms):
        return False, f"bedrooms below minimum ({bi} < {int(settings.min_bedrooms)})"
    allowed_type, normalized_type = passes_hard_property_type_floor(mapped)
    if not allowed_type:
        return False, f"non-residential property_type ({normalized_type})"
    mapped["property_type"] = normalized_type
    mapped["bedrooms"] = bi
    return True, ""


def import_idealista_csv_from_url(db, url: str) -> dict[str, Any]:
    resolved = normalize_google_drive_dataset_url(url)
    raw_bytes = fetch_dataset_bytes(resolved)
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    source = _ensure_idealista_source(db)
    run = ScrapeRun(source_id=source.id, run_type="manual", status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    inserted = 0
    updated = 0
    skipped = 0
    max_rows = int(getattr(settings, "idealista_csv_import_max_rows", 5000) or 5000)

    def process_item_dict(item: dict[str, Any]) -> None:
        nonlocal inserted, updated, skipped
        mapped = _map_apify_item(item)
        if not mapped:
            skipped += 1
            return
        allowed_type, normalized_type = passes_hard_property_type_floor(mapped)
        if not allowed_type:
            skipped += 1
            return
        mapped["property_type"] = normalized_type
        allowed, resolved_beds = passes_hard_bedroom_floor(mapped)
        if not allowed:
            skipped += 1
            return
        mapped["bedrooms"] = resolved_beds
        ok, reason = _validate_mapped_strict(mapped)
        if not ok:
            log.warning("CSV row skipped (%s): %s", reason, mapped.get("url"))
            skipped += 1
            return
        raw_row = ListingRaw(
            scrape_run_id=run.id,
            source_id=source.id,
            source_listing_id=mapped.get("source_listing_id"),
            source_url=str(mapped["url"]),
            raw_payload_json=dict(mapped),
        )
        db.add(raw_row)
        db.flush()
        normalized = normalize_listing(mapped)
        _listing, created = upsert_listing(db, source_id=source.id, payload=normalized, raw_listing_id=raw_row.id)
        inserted += int(created)
        updated += int(not created)

    try:
        if stripped.startswith("["):
            try:
                arr = json.loads(text)
            except json.JSONDecodeError:
                arr = None
            if isinstance(arr, list):
                for i, obj in enumerate(arr):
                    if i >= max_rows:
                        break
                    if isinstance(obj, dict):
                        process_item_dict(obj)
                    else:
                        skipped += 1
            else:
                skipped += 1
        elif stripped.startswith("{"):
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                process_item_dict(obj)
            else:
                n_json = 0
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    n_json += 1
                    if n_json > max_rows:
                        break
                    try:
                        row_obj = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue
                    if isinstance(row_obj, dict):
                        process_item_dict(row_obj)
                    else:
                        skipped += 1
        else:
            reader = csv.DictReader(io.StringIO(text))
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                if not any((v or "").strip() for v in row.values() if v is not None):
                    continue
                n = _norm_keys(row)
                item = _csv_row_to_apify_item(n)
                if not item:
                    skipped += 1
                    continue
                process_item_dict(item)

        run.status = "success"
    except Exception as exc:
        run.status = "failed"
        run.error_log = str(exc)[:8000]
        log.exception("Idealista CSV import failed")
        raise
    finally:
        run.finished_at = datetime.utcnow()
        run.listings_found = inserted + updated + skipped
        run.listings_inserted = inserted
        run.listings_updated = updated
        db.commit()

    return {
        "ok": True,
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "resolved_url": resolved,
        "message": f"Idealista CSV import finished: {inserted} new, {updated} updated, {skipped} skipped (strict validation).",
    }


def import_idealista_csv_from_settings() -> dict[str, Any]:
    url = normalize_google_drive_dataset_url((getattr(settings, "idealista_csv_import_url", None) or "").strip())
    if not url:
        return {"ok": False, "message": "idealista_csv_import_url is not set."}
    db = SessionLocal()
    try:
        return import_idealista_csv_from_url(db, url)
    finally:
        db.close()


def run_idealista_csv_import_logged() -> None:
    try:
        out = import_idealista_csv_from_settings()
        log.info("%s", out.get("message", out))
    except Exception:
        log.exception("Idealista CSV import failed")
