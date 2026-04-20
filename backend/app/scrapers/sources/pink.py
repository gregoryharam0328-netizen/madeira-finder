from __future__ import annotations

from app.scrapers.sources.portal_generic import PortalSearchScraper, PortalSelectors
from app.scrapers.urls import pink_real_estate_default_search_url, pink_real_estate_houses_default_search_url


class PinkRealEstateApartmentsScraper(PortalSearchScraper):
    name = "Pink Real Estate"
    base_domain = "pinkrealestate.pt"
    listing_href_regex = r"^/properties/details/property/"
    selectors = PortalSelectors(
        card="div.uk-card.uk-card-body",
        title="h3",
    )

    def build_search_url(self) -> str:
        return pink_real_estate_default_search_url()


class PinkRealEstateHousesScraper(PortalSearchScraper):
    name = "Pink Real Estate (houses)"
    base_domain = "pinkrealestate.pt"
    listing_href_regex = r"^/properties/details/property/"
    selectors = PortalSelectors(
        card="div.uk-card.uk-card-body",
        title="h3",
    )

    def build_search_url(self) -> str:
        return pink_real_estate_houses_default_search_url()
