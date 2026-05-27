from datetime import date
from typing import List, Optional

import config
from clients import apollo_client
from models.lead import Lead
from models.sector_config import SectorConfig
from utils.cache import LeadCache
from utils.logger import get_logger

log = get_logger("fetcher")

CANADA_PROVINCES = {
    "ON", "QC", "BC", "AB", "SK", "MB", "NS", "NB", "NL", "PE", "NT", "NU", "YT",
    "Ontario", "Quebec", "British Columbia", "Alberta", "Saskatchewan", "Manitoba",
    "Nova Scotia", "New Brunswick", "Newfoundland", "Prince Edward Island",
}

# Decision-maker titles targeted in paid mode
DECISION_MAKER_TITLES = [
    "VP of Operations", "VP Operations", "Director of Operations",
    "Director of Logistics", "VP Supply Chain", "Director Supply Chain",
    "Head of Logistics", "Chief Operating Officer", "COO",
    "VP Logistics", "Director of Transportation", "Logistics Manager",
    "Supply Chain Manager", "Operations Manager",
]


def _extract_province(location_str: str) -> str:
    if not location_str:
        return ""
    for part in location_str.split(","):
        part = part.strip()
        if part in CANADA_PROVINCES:
            return part
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


# ---------------------------------------------------------------------------
# Paid plan path — mixed_people/search returns person + embedded org + email
# ---------------------------------------------------------------------------

def _build_lead_from_person(person: dict, sector: SectorConfig) -> Optional[Lead]:
    org = person.get("organization") or {}
    org_id = person.get("organization_id") or org.get("id") or ""

    # Apply Canadian filter on the org
    if not _is_canadian(org):
        location = person.get("location", "") or ""
        if not any(p in location for p in CANADA_PROVINCES) and "canada" not in location.lower():
            return None

    raw_address = org.get("raw_address", "") or ""
    city = org.get("city") or person.get("city") or ""
    province = org.get("state") or person.get("state") or _extract_province(raw_address)
    technologies = [t.get("name", "") for t in (org.get("technologies") or []) if t.get("name")]

    return Lead(
        # Company
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
        # Contact — emails and phones are present on paid plans
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
            log.info("No more people for %s at page %d", sector.name, page)
            break

        log.info("Page %d: %d people returned for %s", page, len(people), sector.display_name)

        for person in people:
            if len(leads) >= leads_needed:
                break

            person_id = person.get("id", "")
            org_id = person.get("organization_id", "")
            if not person_id:
                continue
            if cache.is_seen(org_id, person_id):
                continue

            lead = _build_lead_from_person(person, sector)
            if lead is None:
                continue

            cache.mark_seen(org_id, person_id)
            leads.append(lead)

    log.info("[PAID] Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads


# ---------------------------------------------------------------------------
# Free plan path — org search only, no person data
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
            log.info("No more orgs for %s at page %d", sector.name, page)
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
# Public entry point — dispatches based on APOLLO_PLAN
# ---------------------------------------------------------------------------

def fetch_sector(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    if config.APOLLO_PLAN == "paid":
        return _fetch_sector_paid(sector, cache, pages, leads_needed)
    return _fetch_sector_free(sector, cache, pages, leads_needed)
