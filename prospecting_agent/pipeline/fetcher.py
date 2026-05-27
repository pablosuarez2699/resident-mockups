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
    raw_address = org.get("organization_raw_address") or org.get("raw_address") or ""
    return any(p in raw_address for p in CANADA_PROVINCES)


def _build_lead(person: dict, org: dict, sector: SectorConfig) -> Optional[Lead]:
    org_id = org.get("id", "")
    contact_id = person.get("id", "")
    if not org_id or not contact_id:
        return None
    if not _is_canadian(org):
        return None

    city = org.get("city") or person.get("city") or ""
    province_raw = (
        org.get("state")
        or person.get("state")
        or _extract_province(org.get("organization_raw_address", "") or org.get("raw_address", ""))
    )
    technologies = [t.get("name", "") for t in (org.get("technologies") or []) if t.get("name")]

    return Lead(
        company_name=org.get("name", ""),
        industry=org.get("industry", sector.display_name),
        website=org.get("website_url", ""),
        employee_count=org.get("num_employees") or org.get("estimated_num_employees"),
        city=city,
        province=province_raw,
        apollo_org_id=org_id,
        technologies=technologies,
        company_description=org.get("short_description", "") or org.get("seo_description", ""),
        annual_revenue_estimate=org.get("annual_revenue"),
        first_name=person.get("first_name", ""),
        last_name=person.get("last_name", ""),
        title=person.get("title", ""),
        email=person.get("email", ""),
        email_verified=person.get("email_status") == "verified",
        phone=person.get("sanitized_phone") or person.get("mobile_phone") or "",
        apollo_contact_id=contact_id,
        linkedin_url=person.get("linkedin_url", ""),
        sector=sector.name,
        date_generated=date.today().isoformat(),
    )


def fetch_sector(
    sector: SectorConfig,
    cache: LeadCache,
    pages: int,
    leads_needed: int,
) -> List[Lead]:
    """Org-first prospecting flow (works on Apollo plans without mixed_people/search).

    1. Search organizations matching sector filters.
    2. For each org, pull top contacts and filter by target titles.
    3. Build Lead objects, dedup against cache.
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
            if not org_id or not _is_canadian(org):
                continue

            people = apollo_client.get_organization_top_people(
                organization_id=org_id,
                titles=sector.target_titles,
                per_page=5,
            )

            for person in people:
                contact_id = person.get("id", "")
                if not contact_id:
                    continue
                if cache.is_seen(org_id, contact_id):
                    continue

                lead = _build_lead(person, org, sector)
                if lead is None:
                    continue

                cache.mark_seen(org_id, contact_id)
                leads.append(lead)

                if len(leads) >= leads_needed:
                    break

    log.info("Sector %s: fetched %d leads", sector.display_name, len(leads))
    return leads
