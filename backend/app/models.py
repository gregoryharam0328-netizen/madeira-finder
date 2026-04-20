import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

def utcnow():
    return datetime.utcnow()

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="portal")
    country_code: Mapped[str] = mapped_column(Text, default="PT")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class ScrapeRun(Base):
    __tablename__ = "scrape_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=True)
    run_type: Mapped[str] = mapped_column(Text, default="scheduled")
    status: Mapped[str] = mapped_column(Text, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pages_scanned: Mapped[int] = mapped_column(Integer, default=0)
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_inserted: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    listings_filtered: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class ListingRaw(Base):
    __tablename__ = "listings_raw"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scrape_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("scrape_runs.id"), nullable=True)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    source_listing_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("source_id", "canonical_url", name="uq_listing_source_url"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    raw_listing_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("listings_raw.id"), nullable=True)
    source_listing_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, default="EUR")
    location_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    municipality: Mapped[str | None] = mapped_column(Text, nullable=True)
    island: Mapped[str | None] = mapped_column(Text, default="Madeira")
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    bedrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    property_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_type: Mapped[str] = mapped_column(Text, default="sale")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eligibility_status: Mapped[str] = mapped_column(Text, default="eligible")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class ListingGroup(Base):
    __tablename__ = "listing_groups"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    group_status: Mapped[str] = mapped_column(Text, default="active")
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class ListingGroupMember(Base):
    __tablename__ = "listing_group_members"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_group_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listing_groups.id"), nullable=False)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listings.id"), nullable=False, unique=True)
    match_method: Mapped[str] = mapped_column(Text, nullable=False)
    match_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class ListingEvent(Base):
    __tablename__ = "listing_events"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listings.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

class UserListingState(Base):
    __tablename__ = "user_listing_state"
    __table_args__ = (UniqueConstraint("user_id", "listing_group_id", name="uq_user_group_state"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    listing_group_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("listing_groups.id"), nullable=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    workflow_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

class DigestRun(Base):
    __tablename__ = "digest_runs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Nullable: digest emails can be sent to configured addresses without being tied to a user row.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    listing_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="pending")
    digest_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
