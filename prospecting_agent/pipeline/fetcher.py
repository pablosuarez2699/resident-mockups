from datetime import date
from typing import List, Optional

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


def _extract_province(location_str: str) -> str:
    if not location_str:
        return ""
    for part in location_str.split(","):
        part = part.strip()
        if part in CANADA_PROVINCES:
            return part
    return ""


def _is_canadian(org: dict) -> bool:
    country = (org.get("country") or "").lower()
    if "canada" in country:
        return True
    raw_address = org.get("raw_address") or ""
    return any(p in raw_address for p in CANADA_PROVINCES)


def _build_company_lead(org: dict, sector: SectorConfig) -> Optional[Lead]:
    """Build a Lead from org data only (lookup-assist mode — no person data)."""
    org_id = org.get("id", "")
    if not org_id:
        return None
    if not _is_canadian(org):
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
        # No person data in lookup-assist mode
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


def fetch_sector(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    """Lookup-assist mode: fetch companies only, no person lookup.

    When Apollo Basic is active, switch to the people-search flow by
    calling search_people() + _build_lead() instead.
    """
    leads: List[Lead] = []
    log.info("Fetching sector: %s (up to %d pages of orgs)", sector.display_name, pages)

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
            if not org_id:
                continue

            # Use org_id as both keys (no contact yet in lookup-assist mode)
            if cache.is_seen(org_id, org_id):
                continue

            lead = _build_company_lead(org, sector)
            if lead is None:
                continue

            cache.mark_seen(org_id, org_id)
            leads.append(lead)

    log.info("Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads
