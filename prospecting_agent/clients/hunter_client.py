import requests
from typing import Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import config
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

log = get_logger("hunter")
_limiter = RateLimiter(config.HUNTER_MIN_SPACING_S)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _get(endpoint: str, params: dict) -> dict:
    _limiter.wait()
    params["api_key"] = config.HUNTER_API_KEY
    url = f"{config.HUNTER_BASE_URL}{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def find_email(domain: str, first_name: str, last_name: str) -> Tuple[Optional[str], int]:
    """Returns (email, confidence_score). Score 0 if not found."""
    if not config.HUNTER_API_KEY:
        return None, 0
    try:
        data = _get("/email-finder", {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
        })
        email_data = data.get("data", {})
        email = email_data.get("email")
        score = email_data.get("score", 0)
        return email, score
    except Exception as e:
        log.warning("Hunter find_email failed for %s %s @ %s: %s", first_name, last_name, domain, e)
        return None, 0


def verify_email(email: str) -> bool:
    """Returns True if Hunter considers the email deliverable."""
    if not config.HUNTER_API_KEY or not email:
        return False
    try:
        data = _get("/email-verifier", {"email": email})
        result = data.get("data", {})
        return result.get("result") in ("deliverable", "risky")
    except Exception as e:
        log.warning("Hunter verify_email failed for %s: %s", email, e)
        return False
