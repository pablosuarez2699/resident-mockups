from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Lead:
    # Company
    company_name: str
    industry: str
    website: str = ""
    employee_count: Optional[int] = None
    city: str = ""
    province: str = ""
    apollo_org_id: str = ""
    technologies: list = field(default_factory=list)
    company_description: str = ""
    annual_revenue_estimate: Optional[int] = None

    # Contact
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    email: str = ""
    email_verified: bool = False
    phone: str = ""
    apollo_contact_id: str = ""
    linkedin_url: str = ""

    # Enriched
    sales_nav_url: str = ""
    sales_nav_company_url: str = ""

    # Classification
    lead_type: str = "NEW"  # NEW or REACTIVATION
    sf_prior_year_revenue: Optional[float] = None
    current_carrier_estimated: str = "Unknown"
    three_pl_risk: bool = False

    # Scoring
    shipping_score: int = 0
    rule_score: int = 0
    talking_points: str = ""

    # Meta
    sector: str = ""
    date_generated: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def location(self) -> str:
        parts = [p for p in [self.city, self.province] if p]
        return ", ".join(parts)
