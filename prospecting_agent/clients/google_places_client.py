import requests
from typing import Dict, Any, Optional

import config
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

log = get_logger("google_places")

_BASE = "https://places.googleapis.com/v1/places"
# 2-second spacing: Google requires a wait between paginated Text Search calls
_limiter = RateLimiter(2.0)

# Set once the project's daily quota is exhausted — further calls this run are
# pointless (every one returns 429/403), so we short-circuit instead of
# burning ~20 minutes sweeping grid zones that can never return results.
_quota_exhausted = [False]


def quota_exhausted() -> bool:
    return _quota_exhausted[0]


def reset_quota_flag() -> None:
    _quota_exhausted[0] = False

# Requesting phone + website puts us in the Advanced tier ($0.032/req).
# At ~80 calls/month that's ~$2.56 — still under the $200/mo free credit.
_FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,"
    "places.types,places.businessStatus,nextPageToken"
)


def _headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
    }


def text_search(
    query: str,
    page_token: Optional[str] = None,
    location_bias: Optional[Any] = None,
) -> Dict[str, Any]:
    """Text search for Canadian businesses. Returns {places: [...], nextPageToken: str}.

    location_bias: optional GeoZone (models.geo_grid) — biases results into that
    circle so low-prominence businesses invisible at city level surface.
    """
    if not config.GOOGLE_PLACES_API_KEY:
        log.warning("GOOGLE_PLACES_API_KEY not set — skipping Google Places call")
        return {}
    if _quota_exhausted[0]:
        return {}

    _limiter.wait()
    payload: dict = {
        "textQuery": query,
        "regionCode": "CA",
        "pageSize": 20,
    }
    if location_bias is not None:
        payload["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": location_bias.lat,
                    "longitude": location_bias.lng,
                },
                # Places API caps circle radius at 50 km
                "radius": min(location_bias.radius_m, 50_000),
            }
        }
    if page_token:
        payload["pageToken"] = page_token

    try:
        resp = requests.post(
            f"{_BASE}:searchText",
            json=payload,
            headers=_headers(),
            timeout=20,
        )
        if resp.status_code in (403, 429) and (
            "RESOURCE_EXHAUSTED" in resp.text
            or "Quota exceeded" in resp.text
            or "PERMISSION_DENIED" in resp.text
        ):
            _quota_exhausted[0] = True
            log.error(
                "GOOGLE PLACES DAILY QUOTA EXHAUSTED — aborting all further "
                "searches this run. Raise the 'Text Search requests per day' "
                "quota in Google Cloud Console (APIs & Services > Quotas), or "
                "wait for the reset at midnight Pacific. Detail: %s",
                resp.text[:300],
            )
            return {}
        if not resp.ok:
            log.error("Google Places text_search %s — %s: %s", query[:60], resp.status_code, resp.text[:400])
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error("Google Places text_search failed (%s): %s", query[:60], e)
        return {}


def place_details(place_id: str) -> Dict[str, Any]:
    """Fetch phone + website for a place when text_search omitted them."""
    if not config.GOOGLE_PLACES_API_KEY or not place_id:
        return {}

    _limiter.wait()
    try:
        resp = requests.get(
            f"{_BASE}/{place_id}",
            headers={
                "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": "nationalPhoneNumber,websiteUri",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning("Google Places place_details failed (%s): %s", place_id, e)
        return {}


def health_check() -> bool:
    """Quick validation that the key works (1 credit)."""
    result = text_search("industrial distributor Toronto Canada")
    return bool(result.get("places"))
