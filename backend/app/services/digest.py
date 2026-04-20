from datetime import datetime, timedelta

import httpx
from sqlalchemy import String, Uuid, cast, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DigestRun, Listing, ListingGroup, ListingGroupMember
def build_digest_html(rows: list[dict]) -> str:
    cards = []
    for item in rows:
        open_url = item.get("source_url") or item.get("canonical_url") or "#"
        cards.append(f"<tr><td style='padding:16px;border-bottom:1px solid #e5e7eb;'><div style='font-weight:600;font-size:16px;margin-bottom:6px;'>{item['title']}</div><div style='margin-bottom:6px;'>€{item['price'] or 'N/A'} · {item.get('bedrooms') or '?'} beds · {item.get('location_text') or ''}</div><a href='{open_url}' style='color:#0f766e;text-decoration:none;'>Open listing</a></td></tr>")
    empty = "<tr><td style='padding:20px;'>No new listings today.</td></tr>"
    body = "".join(cards) if cards else empty
    return (
        "<html><body style='font-family:Arial,sans-serif;background:#f8fafc;padding:24px;'>"
        "<table style='max-width:680px;margin:0 auto;background:white;border-collapse:collapse;width:100%;border:1px solid #e5e7eb;'>"
        "<tr><td style='padding:20px;font-size:22px;font-weight:700;'>New Madeira properties today</td></tr>"
        f"{body}"
        "</table></body></html>"
    )


def collect_new_listing_cards(db: Session) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=1)
    disp = (
        select(
            ListingGroupMember.listing_group_id,
            cast(func.min(cast(ListingGroupMember.listing_id, String)), Uuid).label("display_listing_id"),
        )
        .group_by(ListingGroupMember.listing_group_id)
        .subquery()
    )
    rows = (
        db.query(Listing)
        .join(disp, disp.c.display_listing_id == Listing.id)
        .join(ListingGroup, ListingGroup.id == disp.c.listing_group_id)
        .filter(
            Listing.first_seen_at >= since,
            Listing.eligibility_status == "eligible",
            Listing.is_active.is_(True),
        )
        .order_by(Listing.first_seen_at.desc())
        .all()
    )
    return [
        {
            "title": l.title,
            "price": float(l.price) if l.price is not None else None,
            "bedrooms": l.bedrooms,
            "location_text": l.location_text,
            "source_url": l.source_url or l.canonical_url,
            "canonical_url": l.canonical_url,
        }
        for l in rows
    ]


def _send_resend_email(*, to_email: str, subject: str, html: str) -> tuple[bool, str | None]:
    if not settings.resend_api_key:
        return False, "Missing RESEND_API_KEY"
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}", "Content-Type": "application/json"},
            json={"from": settings.digest_from_email, "to": [to_email], "subject": subject, "html": html},
            timeout=30,
        )
        if r.status_code >= 400:
            return False, f"Resend error {r.status_code}: {r.text}"
        return True, None
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def create_and_send_digests(db: Session):
    cards = collect_new_listing_cards(db)
    payload_html = build_digest_html(cards)
    payload = {"html": payload_html, "cards": cards, "generated_at": datetime.utcnow().isoformat()}

    results = []
    recipients = [e.strip() for e in settings.digest_to_emails.split(",") if e.strip()]
    for to_email in recipients:
        digest = DigestRun(user_id=None, listing_count=len(cards), status="pending", digest_payload_json=payload)
        db.add(digest)
        db.flush()

        if not cards:
            digest.status = "skipped"
            results.append({"email": to_email, "status": "skipped"})
            continue

        ok, err = _send_resend_email(to_email=to_email, subject="New Madeira properties today", html=payload_html)
        digest.status = "sent" if ok else "failed"
        digest.error_log = err
        results.append({"email": to_email, "status": digest.status, "error": err})

    db.commit()
    return {"status": "ok", "recipients": results, "count": len(cards)}
