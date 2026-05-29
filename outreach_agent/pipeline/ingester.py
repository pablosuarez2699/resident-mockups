import re
from typing import List

import pandas as pd

import config
from models.lead import Lead
from utils.logger import get_logger

log = get_logger("ingester")


def _norm(header: str) -> str:
    """Normalize a column header: lowercase, drop everything non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", str(header).lower())


# Normalized header -> Lead attribute. "fullname" is special-cased (split below).
_HEADER_MAP = {
    "companyname": "company_name", "company": "company_name",
    "account": "company_name", "accountname": "company_name", "business": "company_name",
    "industry": "industry",
    "sector": "sector",
    "website": "website", "url": "website", "web": "website", "domain": "website",
    "city": "city",
    "province": "province", "state": "province", "prov": "province",
    "firstname": "first_name", "first": "first_name",
    "lastname": "last_name", "last": "last_name", "surname": "last_name",
    "decisionmaker": "_fullname", "contact": "_fullname", "contactname": "_fullname",
    "name": "_fullname", "fullname": "_fullname",
    "title": "title", "jobtitle": "title", "position": "title", "role": "title",
    "email": "email", "emailaddress": "email", "email1": "email",
    "phone": "phone", "phonenumber": "phone", "telephone": "phone",
    "tel": "phone", "mobile": "phone", "directdial": "phone",
    "carrierest": "current_carrier_estimated", "carrier": "current_carrier_estimated",
    "currentcarrier": "current_carrier_estimated", "estimatedcarrier": "current_carrier_estimated",
    "carrierestimated": "current_carrier_estimated",
    "talkingpoints": "talking_points", "talkingpoint": "talking_points",
    "leadtype": "lead_type", "type": "lead_type",
    "relationship": "relationship_status", "relationshipstatus": "relationship_status",
    "status": "relationship_status", "customerstatus": "relationship_status",
    "lastshipment": "last_shipment_note", "lastshipmentnote": "last_shipment_note",
    "lastshipped": "last_shipment_note",
    "prioryearrevenue": "prior_year_revenue", "priorrevenue": "prior_year_revenue",
    "annualrevenue": "prior_year_revenue", "revenue": "prior_year_revenue",
    "accountnotes": "account_notes", "accountnote": "account_notes", "notes": "account_notes",
    "callnotes": "call_notes", "callnote": "call_notes",
    "conversationnotes": "call_notes", "discussion": "call_notes",
}


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _row_to_lead(row: dict) -> Lead:
    lead = Lead()
    full_name = ""
    for header, value in row.items():
        attr = _HEADER_MAP.get(_norm(header))
        if not attr:
            continue
        text = _clean(value)
        if attr == "_fullname":
            full_name = text
        elif attr == "prior_year_revenue":
            num = re.sub(r"[^0-9.]", "", text)
            if num:
                try:
                    lead.prior_year_revenue = float(num)
                except ValueError:
                    pass
        else:
            setattr(lead, attr, text)

    # Split a combined "Decision Maker / Contact" name when first/last weren't given
    if full_name and not (lead.first_name or lead.last_name):
        parts = full_name.split()
        lead.first_name = parts[0]
        lead.last_name = " ".join(parts[1:])

    # Derive relationship_status from lead_type when not explicitly provided
    if not _norm_present(row, "relationship_status") and lead.lead_type:
        lt = lead.lead_type.strip().lower()
        if lt == "reactivation":
            lead.relationship_status = "lapsed"
        elif lt == "new":
            lead.relationship_status = "prospect"
    return lead


def _norm_present(row: dict, attr: str) -> bool:
    """True if any column in the row maps to `attr` and has a non-empty value."""
    for header, value in row.items():
        if _HEADER_MAP.get(_norm(header)) == attr and _clean(value):
            return True
    return False


def _read_dataframe(path: str) -> pd.DataFrame:
    source = config.LEAD_SOURCE.lower()
    if source == "csv" or path.lower().endswith(".csv"):
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    return pd.read_excel(path, dtype=str, engine="openpyxl")


def ingest(path: str) -> List[Lead]:
    """Read a leads spreadsheet into a list of Lead objects. Logs and returns []
    on failure rather than crashing the run."""
    try:
        df = _read_dataframe(path)
    except Exception as e:
        log.error("Failed to read input file %s: %s", path, e)
        return []

    leads: List[Lead] = []
    for record in df.to_dict(orient="records"):
        lead = _row_to_lead(record)
        if not lead.company_name and not lead.full_name:
            continue  # skip blank rows
        leads.append(lead)

    no_email = sum(1 for lead in leads if not lead.email)
    log.info("Ingested %d leads from %s (%d without an email on file)",
             len(leads), path, no_email)
    return leads


def lead_from_flags(company: str, name: str, email: str, title: str = "",
                    phone: str = "", relationship: str = "current",
                    carrier: str = "Unknown", call_notes: str = "") -> Lead:
    """Build a single Lead for --source manual."""
    parts = (name or "").split()
    return Lead(
        company_name=company,
        first_name=parts[0] if parts else "",
        last_name=" ".join(parts[1:]) if len(parts) > 1 else "",
        email=email,
        title=title,
        phone=phone,
        relationship_status=relationship,
        current_carrier_estimated=carrier,
        call_notes=call_notes,
    )
