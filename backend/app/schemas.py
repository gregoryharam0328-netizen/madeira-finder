from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: str
    class Config:
        from_attributes = True

class DashboardSummary(BaseModel):
    new_today: int
    saved: int
    hidden: int
    seen: int
    total: int
    price_changes: int = Field(0, description="Groups with a price_changed event (GET /listings/price-changes).")
    need_to_call: int = 0
    viewing_arranged: int = 0
    last_scan_at: str | None = None


class IdealistaCsvImportRequest(BaseModel):
    """Optional body for POST /dashboard/import-idealista-csv; falls back to IDEALISTA_CSV_IMPORT_URL."""

    url: str | None = None


class PortalLinkOut(BaseModel):
    """Same property on another portal (dedup group member)."""

    source_name: str
    url: str


class ListingCardOut(BaseModel):
    listing_group_id: str
    title: str
    description: str | None = None
    price: float | None = None
    currency: str = "EUR"
    location_text: str | None = None
    area_name: str | None = None
    municipality: str | None = None
    bedrooms: int | None = None
    property_type: str | None = None
    image_url: str | None = None
    # Exact URL from the portal (preferred for "View listing"); canonical_url stays for dedup.
    source_url: str
    canonical_url: str
    portal_links: list[PortalLinkOut] = Field(default_factory=list)
    primary_source: str | None = None
    eligibility_status: str = "eligible"
    group_status: str
    workflow_status: str = "new"
    note: str | None = None
    price_reduced: bool = False
    is_saved: bool = False
    is_seen: bool = False
    is_hidden: bool = False
    first_seen_at: str | None = None
    last_seen_at: str | None = None


class ListingStatePatch(BaseModel):
    workflow_status: str | None = None
    note: str | None = None
