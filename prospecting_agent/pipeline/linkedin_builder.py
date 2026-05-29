import urllib.parse
from models.lead import Lead


def _company_linkedin_slug(linkedin_url: str) -> str:
    if not linkedin_url:
        return ""
    parts = linkedin_url.rstrip("/").split("/")
    if len(parts) >= 2 and "company" in linkedin_url:
        return parts[-1]
    return ""


def build_urls(lead: Lead) -> Lead:
    company_query = urllib.parse.quote_plus(lead.company_name)

    # Company Sales Nav URL — direct to the company page if we have a slug,
    # otherwise a company keyword search
    slug = _company_linkedin_slug(lead.linkedin_url)
    if slug:
        lead.sales_nav_company_url = f"https://www.linkedin.com/sales/company/{slug}"
    else:
        lead.sales_nav_company_url = (
            f"https://www.linkedin.com/sales/search/company"
            f"?query=(keywords:{company_query})"
        )

    # Person Sales Nav URL — search for decision-maker titles at this company
    # Rep clicks this to find the right contact manually
    lead.sales_nav_url = (
        f"https://www.linkedin.com/sales/search/people"
        f"?query=(keywords:{company_query},"
        f"filters:List((type:CURRENT_COMPANY,values:List((text:{company_query})))))"
    )

    return lead


def build_urls_batch(leads: list) -> list:
    for lead in leads:
        build_urls(lead)
    return leads
