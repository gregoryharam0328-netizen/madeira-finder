from __future__ import annotations

from app.scrapers.sources.portal_generic import PortalSearchScraper, PortalSelectors
from app.scrapers.urls import imovirtual_default_search_url


class ImovirtualApartmentsScraper(PortalSearchScraper):
    name = "Imovirtual"
    base_domain = "imovirtual.com"
    listing_href_regex = r"/pt/anuncio/"
    selectors = PortalSelectors(
        card='a[data-cy="listing-item-link"][href^="/pt/anuncio/"]',
        title='[data-cy="listing-item-title"], [data-cy="ad-title"]',
        price='[data-cy="ad-price"], [data-cy="listing-item-price"], [data-cy="price"]',
        location='[data-cy="listing-item-location"], [data-cy="ad-location"], [data-cy="location"]',
    )

    def build_search_url(self) -> str:
        return imovirtual_default_search_url()


class ImovirtualHousesScraper(PortalSearchScraper):
    name = "Imovirtual (houses)"
    base_domain = "imovirtual.com"
    listing_href_regex = r"/pt/anuncio/"
    selectors = PortalSelectors(
        card='a[data-cy="listing-item-link"][href^="/pt/anuncio/"]',
        title='[data-cy="listing-item-title"], [data-cy="ad-title"]',
        price='[data-cy="ad-price"], [data-cy="listing-item-price"], [data-cy="price"]',
        location='[data-cy="listing-item-location"], [data-cy="ad-location"], [data-cy="location"]',
    )

    def build_search_url(self) -> str:
        return "https://www.imovirtual.com/pt/resultados/comprar/moradia/ilha-da-madeira"
