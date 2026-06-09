import os
from dotenv import load_dotenv

load_dotenv()


def require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
HUNTER_API_KEY: str = os.getenv("HUNTER_API_KEY", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# "free"  → org-search only, no person data (lookup-assist mode)
# "paid"  → mixed_people/search with emails + direct dials
APOLLO_PLAN: str = os.getenv("APOLLO_PLAN", "free")

# "google" → Google Places + Hunter domain-search + web scraping (free path, default)
# "apollo" → Apollo.io (original path, preserved for personal use)
LEAD_SOURCE: str = os.getenv("LEAD_SOURCE", "google")
GOOGLE_PLACES_API_KEY: str = os.getenv("GOOGLE_PLACES_API_KEY", "")
HUNTER_DOMAIN_SEARCH_BUDGET: int = int(os.getenv("HUNTER_DOMAIN_SEARCH_BUDGET", "25"))

# Shipping spend filter: companies must average MIN_DAILY_SHIPMENTS parcels per
# business day. Math: 5/day × 250 days × $20 avg B2B parcel = $25,000/year.
# Set MIN_DAILY_SHIPMENTS=0 to disable the filter.
MIN_DAILY_SHIPMENTS: int = int(os.getenv("MIN_DAILY_SHIPMENTS", "5"))

TARGET_LEADS: int = int(os.getenv("TARGET_LEADS", "100"))
HUNTER_BUDGET_PER_RUN: int = int(os.getenv("HUNTER_BUDGET_PER_RUN", "50"))
APOLLO_PAGES_PER_SECTOR: int = int(os.getenv("APOLLO_PAGES_PER_SECTOR", "5"))

REPORTS_DIR: str = os.path.join(os.path.dirname(__file__), "reports")
CACHE_FILE: str = os.path.join(os.path.dirname(__file__), ".lead_cache.json")
CACHE_MAX_ENTRIES: int = 10_000

APOLLO_BASE_URL: str = "https://api.apollo.io/v1"
APOLLO_MIN_SPACING_S: float = 1.3
HUNTER_BASE_URL: str = "https://api.hunter.io/v2"
HUNTER_MIN_SPACING_S: float = 0.5
