from __future__ import annotations

from urllib.parse import urlencode

from app.config import settings


def _eur_bounds() -> tuple[int, int]:
    min_eur = int(float(settings.min_price_gbp) * float(settings.gbp_to_eur_rate))
    max_eur = int(float(settings.max_price_gbp) * float(settings.gbp_to_eur_rate))
    return min_eur, max_eur


def idealista_default_search_url() -> str:
    if settings.idealista_search_url:
        return settings.idealista_search_url

    min_eur, max_eur = _eur_bounds()
    # Client-provided geo code for Madeira on Idealista.
    # Note: Idealista may still require residential IP / anti-bot measures in production.
    params = {
        "ordenado-por": "fecha-publicacion-desc",
        "tipoOrdenacion": "0",
        "precioMin": str(min_eur),
        "precioMax": str(max_eur),
        "habitacionMinima": str(int(settings.min_bedrooms)),
    }
    return f"https://www.idealista.pt/geo/venta-viviendas/madeira-municipio/{settings.idealista_location_code}/?" + urlencode(params)


def imovirtual_default_search_url() -> str:
    if settings.imovirtual_search_url:
        return settings.imovirtual_search_url

    min_eur, max_eur = _eur_bounds()
    # Imovirtual uses `/pt/resultados/...` listing pages for districts like Madeira.
    base = "https://www.imovirtual.com/pt/resultados/comprar/apartamento/ilha-da-madeira"
    params = {
        "price[from]": str(min_eur),
        "price[to]": str(max_eur),
        "rooms[from]": str(int(settings.min_bedrooms)),
    }
    return base + "?" + urlencode(params)


def supercasa_default_search_url() -> str:
    if settings.supercasa_search_url:
        return settings.supercasa_search_url

    min_eur, max_eur = _eur_bounds()
    # Supercasa uses `comprar-casas/<distrito>` paths; `madeira-distrito` is the island-wide district page.
    base = "https://supercasa.pt/comprar-casas/madeira-distrito"
    params = {
        "preco-min": str(min_eur),
        "preco-max": str(max_eur),
        "quartos-min": str(int(settings.min_bedrooms)),
    }
    return base + "?" + urlencode(params)


def kyero_default_search_url() -> str:
    if settings.kyero_search_url:
        return settings.kyero_search_url

    min_eur, max_eur = _eur_bounds()
    base = "https://www.kyero.com/pt/ilha-da-madeira-imóvel-para-vender-0l57483"
    params = {
        "min_price": str(min_eur),
        "max_price": str(max_eur),
        "min_bed": str(int(settings.min_bedrooms)),
    }
    return base + "?" + urlencode(params)


def green_acres_default_search_url() -> str:
    if settings.green_acres_search_url:
        return settings.green_acres_search_url

    # Green-Acres exposes multiple localized paths; this is a stable PT-ish landing for Madeira apartments.
    # We combine apartment + house pages in the scraper factory by registering two sources if needed later.
    return "https://www.green-acres.pt/apartament/madeira"


def remax_default_search_url() -> str:
    if settings.remax_search_url:
        return settings.remax_search_url
    # RE/MAX listing pages are client-rendered; agency/office pages expose concrete `/pt/venda-...` links.
    # Default: RE/MAX Elite (Madeira) office listings (large Madeira coverage).
    return "https://www.remax.pt/agencia/remax-elite/12351"


def century21_default_search_url() -> str:
    if settings.century21_search_url:
        return settings.century21_search_url
    return "https://www.century21.pt/comprar"


def pink_real_estate_default_search_url() -> str:
    if settings.pink_real_estate_search_url:
        return settings.pink_real_estate_search_url
    return "https://www.pinkrealestate.pt/all-properties/buy-apartments-madeira-island-portugal"


def pink_real_estate_houses_default_search_url() -> str:
    return "https://www.pinkrealestate.pt/all-properties/buy-houses-madeira-island-portugal"
