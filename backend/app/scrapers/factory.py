from app.scrapers.sources.century21 import Century21BuyScraper
from app.scrapers.sources.idealista import IdealistaScraper
from app.scrapers.sources.imovirtual import ImovirtualApartmentsScraper, ImovirtualHousesScraper
from app.scrapers.sources.kyero import KyeroScraper
from app.scrapers.sources.pink import PinkRealEstateApartmentsScraper, PinkRealEstateHousesScraper
from app.scrapers.sources.remax import RemaxMadeiraScraper
from app.scrapers.sources.supercasa import SupercasaScraper


def build_scrapers():
    # Mirrors the client's priority list (Idealista via Apify; others via HTML scraping).
    return [
        IdealistaScraper(),
        ImovirtualApartmentsScraper(),
        ImovirtualHousesScraper(),
        SupercasaScraper(),
        KyeroScraper(),
        RemaxMadeiraScraper(),
        Century21BuyScraper(),
        PinkRealEstateApartmentsScraper(),
        PinkRealEstateHousesScraper(),
    ]
