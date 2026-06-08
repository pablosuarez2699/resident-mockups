import requests
from typing import List, Dict, Any

from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

log = get_logger("osm")

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_limiter = RateLimiter(2.5)  # Overpass fair-use: be gentle

# OSM tag filters that capture B2B businesses per sector.
# Coverage is sparse vs Google Places but entirely free.
_SECTOR_FILTERS: Dict[str, List[str]] = {
    "retail": [
        '["office"~"company|retail|wholesale"]',
        '["shop"="wholesale"]',
    ],
    "healthcare": [
        '["office"~"pharmaceutical|medical|healthcare"]',
        '["healthcare"~"laboratory|pharmacy|clinic"]',
    ],
    "tech": [
        '["office"~"engineering|technology|electronics"]',
        '["craft"~"electronics|manufacturing"]',
    ],
    "industrial": [
        '["office"~"logistics|distribution|manufacturing|company"]',
        '["industrial"~"manufacturer|warehouse|distribution"]',
        '["shop"="wholesale"]',
    ],
}


def search_businesses(sector_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Return Canadian businesses from OSM for the given sector (free fallback)."""
    filters = _SECTOR_FILTERS.get(sector_name, _SECTOR_FILTERS["industrial"])
    results: List[Dict[str, Any]] = []

    for tag_filter in filters:
        if len(results) >= limit:
            break
        query = _build_query(tag_filter, limit - len(results))
        raw = _run_query(query)
        for element in raw.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", "")
            if not name:
                continue
            results.append({
                "name": name,
                "city": tags.get("addr:city", ""),
                "province": tags.get("addr:province") or tags.get("addr:state", ""),
                "phone": tags.get("phone") or tags.get("contact:phone", ""),
                "website": tags.get("website") or tags.get("contact:website", ""),
                "email": tags.get("email") or tags.get("contact:email", ""),
                "osm_id": str(element.get("id", "")),
            })

    return results[:limit]


def _build_query(tag_filter: str, limit: int) -> str:
    return (
        f'[out:json][timeout:30];'
        f'area["ISO3166-1"="CA"]["admin_level"="2"]->.ca;'
        f'('
        f'  node{tag_filter}(area.ca);'
        f'  way{tag_filter}(area.ca);'
        f');'
        f'out body {limit};'
    )


def _run_query(query: str) -> Dict[str, Any]:
    _limiter.wait()
    try:
        resp = requests.post(
            _OVERPASS_URL,
            data={"data": query},
            timeout=40,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning("Overpass query failed: %s", e)
        return {}
