import urllib.parse
from models.lead import Lead


def _slug_from_url(linkedin_url: str) -> str:
    if not linkedin_url:
        return ""
    # Extract /in/slug or /company/slug
    parts = linkedin_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-1]
    return ""


def build_urls(lead: Lead) -> Lead:
    name_query = urllib.parse.quote_plus(lead.full_name)
    company_query = urllib.parse.quote_plus(lead.company_name)

    slug = _slug_from_url(lead.linkedin_url)
    if slug and "/in/" in (lead.linkedin_url or ""):
        lead.sales_nav_url = f"https://www.linkedin.com/sales/people/{slug},NAME_SEARCH"
    else:
        lead.sales_nav_url = (
            f"https://www.linkedin.com/sales/search/people"
            f"?query=(keywords:{name_query},filters:List((type:CURRENT_COMPANY,values:List((text:{company_query})))))"
        )

    lead.sales_nav_company_url = (
        f"https://www.linkedin.com/sales/search/company"
        f"?query=(keywords:{company_query})"
    )

    return lead


def build_urls_batch(leads: list) -> list:
    for lead in leads:
        build_urls(lead)
    return leads
