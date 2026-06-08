from typing import List
from urllib.parse import urlparse

from clients import hunter_client
from models.lead import Lead
from utils.logger import get_logger

log = get_logger("enricher")


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def enrich_emails(leads: List[Lead], hunter_budget: int) -> List[Lead]:
    """Fill missing emails via Hunter.io, respecting the per-run budget."""
    used = 0
    for lead in leads:
        if lead.email and lead.email_verified:
            continue
        if used >= hunter_budget:
            log.info("Hunter budget exhausted (%d calls used)", used)
            break
        if lead.rule_score < 7 and not lead.email:
            continue

        domain = _domain_from_url(lead.website)
        if not domain:
            continue

        email, score = hunter_client.find_email(domain, lead.first_name, lead.last_name)
        used += 1

        if email and score >= 50:
            verified = hunter_client.verify_email(email)
            used += 1
            lead.email = email
            lead.email_verified = verified
            log.debug("Hunter found email for %s: %s (score %d, verified=%s)", lead.company_name, email, score, verified)

    log.info("Hunter enrichment complete: %d API calls used", used)
    return leads
