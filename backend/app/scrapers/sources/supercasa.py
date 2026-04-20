from __future__ import annotations

from app.scrapers.sources.portal_generic import PortalSearchScraper, PortalSelectors
from app.scrapers.urls import supercasa_default_search_url


class SupercasaScraper(PortalSearchScraper):
    name = "Supercasa"
    base_domain = "supercasa.pt"
    listing_href_regex = r"^/venda-"
    selectors = PortalSelectors(card="div.property")

    def build_search_url(self) -> str:
        return supercasa_default_search_url()
