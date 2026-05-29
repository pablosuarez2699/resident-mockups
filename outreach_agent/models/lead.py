from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Lead:
    """A lead/account to reach out to.

    Superset-compatible with the prospecting agent's Lead so the qualified-leads
    .xlsx it emits ingests cleanly here, plus outreach/relationship fields used to
    position Purolator strategically against the existing/lapsed relationship.
    """

    # Company
    company_name: str = ""
    industry: str = ""
    website: str = ""
    city: str = ""
    province: str = ""

    # Contact (the decision-maker)
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""

    # Positioning signals (carried from the prospecting agent)
    current_carrier_estimated: str = "Unknown"
    talking_points: str = ""
    lead_type: str = "NEW"  # NEW or REACTIVATION
    sector: str = ""

    # Relationship context (drives consultative, non-salesy positioning)
    # current | lapsed | past | prospect
    relationship_status: str = "current"
    last_shipment_note: str = ""
    prior_year_revenue: Optional[float] = None
    account_notes: str = ""

    # Free-form notes from a call (used by the follow-up mode)
    call_notes: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def location(self) -> str:
        parts = [p for p in [self.city, self.province] if p]
        return ", ".join(parts)

    @property
    def greeting_name(self) -> str:
        """Name to address the contact by — first name, else a polite fallback."""
        return self.first_name.strip() or "there"
