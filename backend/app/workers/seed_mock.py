import uuid
from datetime import datetime

from app.database import Base, SessionLocal, engine
from app.models import ListingRaw, ScrapeRun, Source
from app.services.dedup import upsert_listing
from app.services.normalization import normalize_listing


def seed_mock(*, n: int = 12) -> int:
    """
    Insert mock listings for local CLI testing only (no external sites).

    Mock rows are removed automatically at the start of each dashboard
    "Fetch listings now" / daily ingestion run, and via POST /dashboard/remove-mock-listings.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    inserted = 0
    try:
        source = db.query(Source).filter(Source.name == "MockSource").first()
        if not source:
            source = Source(name="MockSource", base_url="https://example.com", source_type="portal", priority=0)
            db.add(source)
            db.commit()
            db.refresh(source)

        run = ScrapeRun(source_id=source.id, run_type="manual", status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

        for i in range(n):
            url = f"https://example.com/listing/{uuid.uuid4()}"
            raw_item = {
                "url": url,
                "title": f"Mock Property #{i + 1} (Funchal)",
                "description": "Mock listing for UI testing.",
                "price": 300000 + i * 5000,
                "currency": "EUR",
                "bedrooms": (i % 3) + 2,
                "bathrooms": (i % 3) + 1,
                "property_type": ["apartment", "house", "apartment"][i % 3],
                "listing_type": "sale",
                "location": "Funchal, Madeira",
                "image_url": f"https://picsum.photos/seed/madeira-{i}/900/700",
                "source_listing_id": f"mock-{i + 1}",
                "published_at": datetime.utcnow().isoformat(),
            }

            raw = ListingRaw(
                scrape_run_id=run.id,
                source_id=source.id,
                source_listing_id=raw_item["source_listing_id"],
                source_url=url,
                raw_payload_json=raw_item,
            )
            db.add(raw)
            db.flush()

            payload = normalize_listing(raw_item)
            _listing, created = upsert_listing(db, source_id=source.id, payload=payload, raw_listing_id=raw.id)
            inserted += int(created)

        run.status = "success"
        run.finished_at = datetime.utcnow()
        run.listings_found = n
        run.listings_inserted = inserted
        db.commit()
        return inserted
    finally:
        db.close()


def main() -> None:
    n = seed_mock()
    print(f"Mock seed complete ({n} new rows).")


if __name__ == "__main__":
    main()
