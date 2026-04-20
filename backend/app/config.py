from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Madeira Property Finder"
    app_env: str = "development"
    # "New today" listing window uses local calendar midnight in this timezone.
    # Madeira uses the same timezone rules as Lisbon.
    app_timezone: str = "Europe/Lisbon"
    # Automatic daily scrape runs at this local wall time (APP_TIMEZONE).
    daily_ingestion_local_hour: int = 5
    daily_ingestion_local_minute: int = 0
    database_url: str = "sqlite:///./madeira.db"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    backend_cors_origins: str = "https://madeira-frontend.onrender.com"
    # Optional regex for dynamic frontend hosts (e.g. Render preview domains).
    backend_cors_origin_regex: str | None = None

    resend_api_key: str | None = None
    digest_from_email: str = "info@exploringmadeira.com"
    digest_to_emails: str = "info@exploringmadeira.com"

    next_public_api_url: str | None = None

    # Client filters (see client brief + screenshots)
    # Budget is specified in GBP; listings are typically scraped in EUR.
    min_price_gbp: float = 250_000
    max_price_gbp: float = 350_000
    gbp_to_eur_rate: float = 1.17
    min_bedrooms: int = 2
    allowed_property_types_csv: str = "house,apartment,villa,land"

    idealista_location_code: str = "0-EU-PT-31"

    scrape_max_pages_per_source: int = 1
    scrape_max_listings_per_source: int = 40
    scrape_timeout_seconds: float = 25.0

    # Optional overrides (full search URLs). If unset, defaults are used.
    idealista_search_url: str | None = None
    imovirtual_search_url: str | None = None
    supercasa_search_url: str | None = None
    kyero_search_url: str | None = None
    green_acres_search_url: str | None = None
    remax_search_url: str | None = None
    century21_search_url: str | None = None
    pink_real_estate_search_url: str | None = None

    # Optional: paid ingestion for sources that are hard to scrape directly (client previously used Apify).
    apify_token: str | None = None
    # Apify REST expects `username~actor-name`, e.g. `igolaizola~idealista-scraper`
    idealista_apify_actor_id: str | None = None
    # https://apify.com/igolaizola/idealista-scraper — slow & costly; optional extra tabs in dataset
    idealista_apify_fetch_details: bool = False
    idealista_apify_fetch_stats: bool = False
    apify_actor_timeout_seconds: int = 300

    # On API startup: if today's scheduled scrape has not succeeded yet (e.g. server started after the daily slot), run daily_runner once.
    enable_startup_daily_catchup: bool = True
    # While the API process is running, wake each day at daily_ingestion_local_hour:minute (APP_TIMEZONE) and run daily_runner.
    # Disable if you use an external cron instead.
    enable_daily_scheduler: bool = True

    # Optional: import Idealista rows from a public CSV/JSONL URL (e.g. Apify export on Google Drive:
    # https://drive.google.com/uc?export=download&id=... — share links /file/d/.../view are rewritten automatically).
    idealista_csv_import_url: str | None = None
    idealista_csv_import_max_rows: int = 5000
    # If true, fetch and import the CSV once when the API process starts (in addition to the daily job when URL is set).
    idealista_csv_import_on_startup: bool = False

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
