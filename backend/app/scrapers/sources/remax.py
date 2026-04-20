from __future__ import annotations

from app.scrapers.sources.portal_generic import PortalSearchScraper, PortalSelectors
from app.scrapers.urls import remax_default_search_url


class RemaxMadeiraScraper(PortalSearchScraper):
    name = "RE/MAX Portugal"
    base_domain = "remax.pt"
    requires_js = True
    # Sale listings use `/pt/venda-...` slugs (Madeira municipalities appear in the slug).
    listing_href_regex = r"^/pt/(?!arrendamento)venda-"
    selectors = PortalSelectors(
        card='a[href^="/pt/venda-"]',
    )

    def build_search_url(self) -> str:
        return remax_default_search_url()
