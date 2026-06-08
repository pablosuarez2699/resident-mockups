import json
import re
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger

log = get_logger("scraper")

_CANDIDATE_PATHS = [
    "/team", "/about", "/about-us", "/leadership",
    "/our-team", "/staff", "/people", "/contact", "/contact-us",
]

_SKIP_PREFIXES = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "webmaster", "privacy", "legal", "abuse", "postmaster",
    "unsubscribe", "bounce",
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_DECISION_KEYWORDS = {
    "coo", "ceo", "cfo", "vp", "vice president", "director", "head of",
    "manager", "chief", "operations", "logistics", "supply chain",
    "procurement", "purchasing", "warehouse", "distribution",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}


def scrape_contacts(website_url: str) -> List[dict]:
    """Try common team/contact pages and return extracted contacts."""
    if not website_url:
        return []

    base = website_url.rstrip("/")
    parsed = urlparse(base)
    if not parsed.scheme:
        base = "https://" + base

    contacts: List[dict] = []
    seen_emails: set = set()

    for path in _CANDIDATE_PATHS:
        url = f"{base}{path}"
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=8, allow_redirects=True)
            content_type = resp.headers.get("content-type", "")
            if not resp.ok or "text/html" not in content_type:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 1. schema.org Person JSON-LD (highest quality)
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("@type") == "Person":
                            c = _from_jsonld(item)
                            if c and c.get("email") and c["email"] not in seen_emails:
                                seen_emails.add(c["email"])
                                contacts.append(c)
                except Exception:
                    pass

            # 2. Raw email scan
            for email in _EMAIL_RE.findall(resp.text):
                prefix = email.split("@")[0].lower()
                if prefix in _SKIP_PREFIXES:
                    continue
                if email in seen_emails:
                    continue
                seen_emails.add(email)
                contacts.append({"first_name": "", "last_name": "", "title": "", "email": email})

            if contacts:
                break  # Stop at first page that yielded results

        except Exception as e:
            log.debug("Scraper failed on %s: %s", url, e)

    return contacts


def pick_decision_maker(
    contacts: List[dict],
    target_titles: Optional[List[str]] = None,
) -> Optional[dict]:
    """Return the best decision-maker from a list of contacts."""
    if not contacts:
        return None

    target_lower = [t.lower() for t in (target_titles or [])]

    def score(c: dict) -> int:
        title = (c.get("title") or c.get("position") or "").lower()
        if not title:
            # Prefer contacts that have a name
            return 1 if (c.get("first_name") or c.get("last_name")) else 0
        # Exact match against target titles list
        for t in target_lower:
            if t in title or title in t:
                return 10
        # Partial keyword match
        return sum(2 for kw in _DECISION_KEYWORDS if kw in title)

    return max(contacts, key=score)


def _from_jsonld(item: dict) -> Optional[dict]:
    name = item.get("name", "")
    parts = name.split(" ", 1) if name else []
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    email = item.get("email", "")
    # Strip mailto: prefix if present
    if email.startswith("mailto:"):
        email = email[7:]
    return {
        "first_name": first,
        "last_name": last,
        "title": item.get("jobTitle", ""),
        "email": email,
    }
