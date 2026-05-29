import re
from datetime import date
from typing import List, Optional
from urllib.parse import urlparse

import config
from clients import apollo_client
from clients import hunter_client
from clients import google_places_client
from clients import osm_client
from models.lead import Lead
from models.sector_config import SectorConfig
from pipeline.web_scraper import scrape_contacts, pick_decision_maker
from utils.cache import LeadCache
from utils.logger import get_logger

log = get_logger("fetcher")

CANADA_PROVINCES = {
    "ON", "QC", "BC", "AB", "SK", "MB", "NS", "NB", "NL", "PE", "NT", "NU", "YT",
    "Ontario", "Quebec", "British Columbia", "Alberta", "Saskatchewan", "Manitoba",
    "Nova Scotia", "New Brunswick", "Newfoundland", "Prince Edward Island",
}

DECISION_MAKER_TITLES = [
    "VP of Operations", "VP Operations", "Director of Operations",
    "Director of Logistics", "VP Supply Chain", "Director Supply Chain",
    "Head of Logistics", "Chief Operating Officer", "COO",
    "VP Logistics", "Director of Transportation", "Logistics Manager",
    "Supply Chain Manager", "Operations Manager",
]

# Google Places types that indicate consumer-facing businesses — skip these for B2B
_CONSUMER_TYPES = {
    "restaurant", "cafe", "bar", "night_club", "lodging", "hotel",
    "beauty_salon", "hair_care", "spa", "gym", "fitness_center",
    "grocery_or_supermarket", "supermarket", "convenience_store",
    "clothing_store", "shoe_store", "jewelry_store", "florist",
    "real_estate_agency", "dentist", "doctor", "hospital",
    "veterinary_care", "school", "university", "church", "place_of_worship",
    "movie_theater", "amusement_park", "zoo", "aquarium",
    "gas_station", "car_wash", "car_dealer", "car_repair",
    "laundry", "dry_cleaning", "bakery",
}

# Module-level shared Hunter domain-search budget for the current run.
# Reset by init_run() before each agent run.
_domain_budget: List[int] = [0]


def init_run() -> None:
    """Reset the Hunter domain-search budget counter for a fresh run."""
    _domain_budget[0] = config.HUNTER_DOMAIN_SEARCH_BUDGET
    log.info("Hunter domain-search budget reset to %d", _domain_budget[0])


def _extract_province(location_str: str) -> str:
    if not location_str:
        return ""
    for part in location_str.split(","):
        part = part.strip()
        if part in CANADA_PROVINCES:
            return part
        # Google often bundles the province with the postal code in one
        # segment, e.g. "QC H3A 3H3" — match a province token within the part.
        for token in part.split():
            if token in CANADA_PROVINCES:
                return token
    return ""


def _is_canadian(obj: dict) -> bool:
    country = (obj.get("country") or "").lower()
    if "canada" in country:
        return True
    raw_address = obj.get("raw_address") or ""
    return any(p in raw_address for p in CANADA_PROVINCES)


def _first_phone(phone_numbers: list) -> str:
    for p in (phone_numbers or []):
        number = p.get("sanitized_number") or p.get("raw_number") or ""
        if number:
            return number
    return ""


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else "https://" + url)
    return parsed.netloc.lstrip("www.") or ""


# ---------------------------------------------------------------------------
# Google Places path — free (within $200/mo credit)
# ---------------------------------------------------------------------------

def _is_b2b_place(place: dict) -> bool:
    types = set(place.get("types", []))
    return not types.intersection(_CONSUMER_TYPES)


def _parse_google_address(formatted_address: str) -> tuple:
    """Return (city, province) from a Google Places formattedAddress string."""
    province = _extract_province(formatted_address)
    parts = [p.strip() for p in formatted_address.split(",")]

    # Filter out: "Canada", province-containing parts, and postal codes
    postal_re = re.compile(r"[A-Z]\d[A-Z]")
    candidates = []
    for part in parts:
        if not part:
            continue
        if part.lower() == "canada":
            continue
        if any(prov in part for prov in CANADA_PROVINCES):
            continue
        if postal_re.search(part):
            continue
        if re.match(r"^\d", part):  # starts with digit = street address
            continue
        candidates.append(part)

    # After filtering, the first remaining element is usually the city
    city = candidates[0] if candidates else ""
    return city, province


def _enrich_contact_google_path(lead: Lead, sector: SectorConfig) -> Lead:
    """Attach a decision-maker contact to a Google-sourced company lead."""
    domain = _domain_from_url(lead.website)
    if not domain:
        return lead

    # 1. Hunter domain-search (spends 1 credit per call)
    if config.HUNTER_API_KEY and _domain_budget[0] > 0:
        people = hunter_client.domain_search(domain, limit=10)
        if people:
            _domain_budget[0] -= 1
            best = pick_decision_maker(people, sector.target_titles)
            if best:
                lead.first_name = best.get("first_name", "")
                lead.last_name = best.get("last_name", "")
                lead.title = best.get("position") or best.get("title") or ""
                lead.email = best.get("value", "")
                lead.email_verified = best.get("confidence", 0) >= 70
                lead.apollo_contact_id = f"hunter:{domain}:{lead.email}"
                log.debug("Hunter contact found: %s %s at %s", lead.first_name, lead.last_name, domain)
                return lead

    # 2. Website scraping fallback (free, always tried if Hunter missed)
    contacts = scrape_contacts(lead.website)
    if contacts:
        best = pick_decision_maker(contacts, sector.target_titles)
        if best:
            lead.first_name = best.get("first_name", "")
            lead.last_name = best.get("last_name", "")
            lead.title = best.get("title", "")
            lead.email = best.get("email", "")
            lead.apollo_contact_id = f"scraper:{domain}:{lead.email}"
            log.debug("Scraper contact found at %s", domain)
            return lead

    # No contact found — return as company-only lead
    log.debug("No contact found for %s (%s)", lead.company_name, domain)
    return lead


def _build_lead_from_place(place: dict, sector: SectorConfig) -> Optional[Lead]:
    """Build a Lead from a Google Places result object."""
    place_id = place.get("id", "")
    if not place_id:
        return None

    name = (place.get("displayName") or {}).get("text", "")
    if not name:
        return None

    formatted_address = place.get("formattedAddress", "")
    city, province = _parse_google_address(formatted_address)
    phone = place.get("nationalPhoneNumber", "")
    website = place.get("websiteUri", "")

    # If phone/website missing from text search, try place details
    if not phone or not website:
        details = google_places_client.place_details(place_id)
        phone = phone or details.get("nationalPhoneNumber", "")
        website = website or details.get("websiteUri", "")

    return Lead(
        company_name=name,
        industry=sector.display_name,
        website=website,
        city=city,
        province=province,
        phone=phone,
        apollo_org_id=f"gplaces:{place_id}",
        company_description="",
        first_name="",
        last_name="",
        title="Find via Sales Nav →",
        email="",
        apollo_contact_id="",
        linkedin_url="",
        sector=sector.name,
        date_generated=date.today().isoformat(),
    )


def _build_lead_from_osm(biz: dict, sector: SectorConfig) -> Optional[Lead]:
    """Build a Lead from an OSM Overpass result."""
    name = biz.get("name", "")
    if not name:
        return None
    return Lead(
        company_name=name,
        industry=sector.display_name,
        website=biz.get("website", ""),
        city=biz.get("city", ""),
        province=biz.get("province", ""),
        phone=biz.get("phone", ""),
        apollo_org_id=f"osm:{biz.get('osm_id', '')}",
        company_description="",
        first_name="",
        last_name="",
        title="Find via Sales Nav →",
        email=biz.get("email", ""),
        apollo_contact_id="",
        linkedin_url="",
        sector=sector.name,
        date_generated=date.today().isoformat(),
    )


def _fetch_sector_google(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    leads: List[Lead] = []
    search_terms = sector.google_search_terms or [f"{sector.display_name} company Canada"]
    log.info("[GOOGLE] Fetching sector: %s (%d search terms)", sector.display_name, len(search_terms))

    for term in search_terms:
        if len(leads) >= leads_needed:
            break
        page_token: Optional[str] = None

        for page_num in range(1, pages + 1):
            if len(leads) >= leads_needed:
                break

            result = google_places_client.text_search(term, page_token=page_token)
            places = result.get("places", [])
            if not places:
                log.info("No more places for '%s' at page %d", term[:50], page_num)
                break

            log.info("Page %d (%s): %d places returned", page_num, term[:40], len(places))

            for place in places:
                if len(leads) >= leads_needed:
                    break

                # Skip non-operational or consumer-facing
                if place.get("businessStatus") not in ("OPERATIONAL", None, ""):
                    continue
                if not _is_b2b_place(place):
                    continue

                place_id = place.get("id", "")
                if not place_id or cache.is_seen(place_id, place_id):
                    continue

                lead = _build_lead_from_place(place, sector)
                if lead is None:
                    continue

                # Must be Canadian (double-check province)
                if not lead.province and "canada" not in place.get("formattedAddress", "").lower():
                    continue

                # Enrich with contact data (Hunter → scraper)
                lead = _enrich_contact_google_path(lead, sector)

                cache.mark_seen(place_id, place_id)
                leads.append(lead)

            page_token = result.get("nextPageToken")
            if not page_token:
                break

    # OSM fallback if Google key missing or returned nothing
    if not leads and not config.GOOGLE_PLACES_API_KEY:
        log.info("[OSM] Falling back to OpenStreetMap for %s", sector.name)
        osm_results = osm_client.search_businesses(sector.name, limit=leads_needed * 2)
        for biz in osm_results:
            if len(leads) >= leads_needed:
                break
            osm_id = f"osm:{biz.get('osm_id', '')}"
            if cache.is_seen(osm_id, osm_id):
                continue
            lead = _build_lead_from_osm(biz, sector)
            if lead and lead.province:
                lead = _enrich_contact_google_path(lead, sector)
                cache.mark_seen(osm_id, osm_id)
                leads.append(lead)

    log.info("[GOOGLE] Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads


# ---------------------------------------------------------------------------
# Apollo paid path — mixed_people/search with emails + direct dials
# ---------------------------------------------------------------------------

def _build_lead_from_person(person: dict, sector: SectorConfig) -> Optional[Lead]:
    org = person.get("organization") or {}
    org_id = person.get("organization_id") or org.get("id") or ""

    if not _is_canadian(org):
        location = person.get("location", "") or ""
        if not any(p in location for p in CANADA_PROVINCES) and "canada" not in location.lower():
            return None

    raw_address = org.get("raw_address", "") or ""
    city = org.get("city") or person.get("city") or ""
    province = org.get("state") or person.get("state") or _extract_province(raw_address)
    technologies = [t.get("name", "") for t in (org.get("technologies") or []) if t.get("name")]

    return Lead(
        company_name=org.get("name") or person.get("organization_name", ""),
        industry=org.get("industry", sector.display_name),
        website=org.get("website_url", ""),
        employee_count=org.get("num_employees") or org.get("estimated_num_employees"),
        city=city,
        province=province,
        apollo_org_id=org_id,
        technologies=technologies,
        company_description=org.get("short_description") or org.get("seo_description") or "",
        annual_revenue_estimate=org.get("annual_revenue"),
        first_name=person.get("first_name", ""),
        last_name=person.get("last_name", ""),
        title=person.get("title", ""),
        email=person.get("email") or "",
        email_verified=person.get("email_status") in ("verified", "likely_to_engage"),
        phone=_first_phone(person.get("phone_numbers", [])),
        apollo_contact_id=person.get("id", ""),
        linkedin_url=person.get("linkedin_url") or org.get("linkedin_url") or "",
        sector=sector.name,
        date_generated=date.today().isoformat(),
    )


def _fetch_sector_paid(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    leads: List[Lead] = []
    log.info("[PAID] Fetching sector: %s (people search, up to %d pages)", sector.display_name, pages)

    for page in range(1, pages + 1):
        if len(leads) >= leads_needed:
            break

        raw = apollo_client.search_people(
            industries=sector.apollo_industries,
            keywords=sector.apollo_keywords,
            titles=DECISION_MAKER_TITLES,
            page=page,
            per_page=25,
        )

        people = raw.get("people", []) or raw.get("contacts", [])
        if not people:
            break

        log.info("Page %d: %d people returned for %s", page, len(people), sector.display_name)

        for person in people:
            if len(leads) >= leads_needed:
                break
            person_id = person.get("id", "")
            org_id = person.get("organization_id", "")
            if not person_id or cache.is_seen(org_id, person_id):
                continue
            lead = _build_lead_from_person(person, sector)
            if lead is None:
                continue
            cache.mark_seen(org_id, person_id)
            leads.append(lead)

    log.info("[PAID] Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads


# ---------------------------------------------------------------------------
# Apollo free path — org-search only, lookup-assist mode
# ---------------------------------------------------------------------------

def _build_company_lead(org: dict, sector: SectorConfig) -> Optional[Lead]:
    org_id = org.get("id", "")
    if not org_id or not _is_canadian(org):
        return None

    raw_address = org.get("raw_address", "") or ""
    city = org.get("city", "")
    province = org.get("state", "") or _extract_province(raw_address)
    technologies = [t.get("name", "") for t in (org.get("technologies") or []) if t.get("name")]

    return Lead(
        company_name=org.get("name", ""),
        industry=org.get("industry", sector.display_name),
        website=org.get("website_url", ""),
        employee_count=org.get("num_employees") or org.get("estimated_num_employees"),
        city=city,
        province=province,
        apollo_org_id=org_id,
        technologies=technologies,
        company_description=org.get("short_description", "") or org.get("seo_description", ""),
        annual_revenue_estimate=org.get("annual_revenue"),
        first_name="",
        last_name="",
        title="Find via Sales Nav →",
        email="",
        phone="",
        apollo_contact_id="",
        linkedin_url=org.get("linkedin_url", ""),
        sector=sector.name,
        date_generated=date.today().isoformat(),
    )


def _fetch_sector_free(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    leads: List[Lead] = []
    log.info("[FREE] Fetching sector: %s (org search only, up to %d pages)", sector.display_name, pages)

    for page in range(1, pages + 1):
        if len(leads) >= leads_needed:
            break

        raw = apollo_client.search_organizations(
            industries=sector.apollo_industries,
            keywords=sector.apollo_keywords,
            page=page,
            per_page=25,
        )

        orgs = raw.get("organizations", []) or raw.get("accounts", [])
        if not orgs:
            break

        log.info("Page %d: %d orgs returned for %s", page, len(orgs), sector.display_name)

        for org in orgs:
            if len(leads) >= leads_needed:
                break
            org_id = org.get("id", "")
            if not org_id or cache.is_seen(org_id, org_id):
                continue
            lead = _build_company_lead(org, sector)
            if lead is None:
                continue
            cache.mark_seen(org_id, org_id)
            leads.append(lead)

    log.info("[FREE] Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads


# ---------------------------------------------------------------------------
# Public entry point — dispatches based on LEAD_SOURCE + APOLLO_PLAN
# ---------------------------------------------------------------------------

def fetch_sector(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    if config.LEAD_SOURCE == "google":
        return _fetch_sector_google(sector, cache, pages, leads_needed)
    # Apollo paths
    if config.APOLLO_PLAN == "paid":
        return _fetch_sector_paid(sector, cache, pages, leads_needed)
    return _fetch_sector_free(sector, cache, pages, leads_needed)
