import requests
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

log = get_logger("apollo")
_limiter = RateLimiter(config.APOLLO_MIN_SPACING_S)


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": config.APOLLO_API_KEY,
    }


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _post(endpoint: str, payload: dict) -> dict:
    _limiter.wait()
    url = f"{config.APOLLO_BASE_URL}{endpoint}"
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _get(endpoint: str, params: dict) -> dict:
    _limiter.wait()
    url = f"{config.APOLLO_BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def health_check() -> bool:
    try:
        result = _get("/auth/health", {"api_key": config.APOLLO_API_KEY})
        return result.get("is_logged_in", False)
    except Exception as e:
        log.error("Apollo health check failed: %s", e)
        return False


def search_people(
    industries: List[str],
    keywords: List[str],
    titles: List[str],
    page: int = 1,
    per_page: int = 25,
) -> Dict[str, Any]:
    payload = {
        "page": page,
        "per_page": per_page,
        "person_titles": titles,
        "organization_locations": ["Canada"],
        "organization_industry_tag_values": industries,
        "q_keywords": " OR ".join(keywords) if keywords else "",
        "organization_num_employees_ranges": ["10,50", "51,200", "201,500"],
        "contact_email_status": ["verified", "likely to engage", "guessed"],
    }
    try:
        return _post("/people/search", payload)
    except Exception as e:
        log.error("Apollo people/search failed (page %d): %s", page, e)
        return {}


def enrich_organization(domain: str) -> Optional[Dict[str, Any]]:
    if not domain:
        return None
    try:
        result = _post("/organizations/enrich", {"domain": domain})
        return result.get("organization")
    except Exception as e:
        log.warning("Apollo org enrich failed for %s: %s", domain, e)
        return None
