from typing import List
from models.lead import Lead
from models.sector_config import SECTOR_CONFIGS
from utils.logger import get_logger

log = get_logger("qualifier")

ECOMMERCE_TECHS = {"shopify", "woocommerce", "magento", "bigcommerce", "wix stores", "squarespace commerce"}
HARDWARE_KEYWORDS = {"hardware", "iot", "electronics", "circuit", "pcb", "device", "sensor", "component"}
DISTRIBUTION_KEYWORDS = {"distribution", "warehouse", "wholesale", "fulfillment", "logistics", "supply chain"}
THREE_PL_KEYWORDS = {"3pl", "third-party logistics", "shipbob", "flexport", "freightos", "freight broker", "fulfillment for"}
WINNABLE_SHIP_TECH = {"shipstation", "shippo", "stamps.com", "easypost", "pirateship"}


def _techs_lower(lead: Lead) -> set:
    return {t.lower() for t in lead.technologies}


def _desc_lower(lead: Lead) -> str:
    return (lead.company_description or "").lower()


def _has_ecommerce_tech(lead: Lead) -> bool:
    return bool(_techs_lower(lead) & ECOMMERCE_TECHS)


def _has_hardware_keyword(lead: Lead) -> bool:
    desc = _desc_lower(lead)
    industry = lead.industry.lower()
    return any(k in desc or k in industry for k in HARDWARE_KEYWORDS)


def _has_distribution_keyword(lead: Lead) -> bool:
    desc = _desc_lower(lead)
    industry = lead.industry.lower()
    return any(k in desc or k in industry for k in DISTRIBUTION_KEYWORDS)


def _is_3pl_risk(lead: Lead) -> bool:
    desc = _desc_lower(lead)
    industry = lead.industry.lower()
    tech_names = _techs_lower(lead)

    # Company is itself a 3PL or broker
    if any(k in desc or k in industry for k in THREE_PL_KEYWORDS):
        # Check if they are a client vs provider
        if "ships on behalf" in desc or "shipping for" in desc or "fulfillment provider" in desc:
            return True
        if "3pl" in industry or "freight broker" in industry:
            return True

    # Using a full outsourced fulfillment provider (not just their own shipping tool)
    outsourced = {"shipbob", "flexport", "freightos"}
    if tech_names & outsourced:
        return True

    return False


def score_rule_based(lead: Lead) -> int:
    cfg = SECTOR_CONFIGS.get(lead.sector)
    base = cfg.base_score if cfg else 3
    score = base

    weights = cfg.score_weights if cfg else {}

    if weights.get("has_ecommerce_tech") and _has_ecommerce_tech(lead):
        score += weights["has_ecommerce_tech"]
    if weights.get("hardware_keyword_match") and _has_hardware_keyword(lead):
        score += weights["hardware_keyword_match"]
    if weights.get("distribution_keyword") and _has_distribution_keyword(lead):
        score += weights["distribution_keyword"]

    emp = lead.employee_count or 0
    if weights.get("employee_20_plus") and emp >= 20:
        score += weights["employee_20_plus"]
    if weights.get("employee_50_plus") and emp >= 50:
        score += weights["employee_50_plus"]
    if weights.get("multi_location") and lead.company_description and "location" in _desc_lower(lead):
        score += weights["multi_location"]

    if weights.get("has_phone") and lead.phone:
        score += weights["has_phone"]
    if weights.get("has_email") and lead.email:
        score += weights["has_email"]

    if cfg and cfg.hardware_required and not _has_hardware_keyword(lead):
        score = min(score, 3)

    if _is_3pl_risk(lead):
        lead.three_pl_risk = True
        score = min(score, 4)

    return min(score, 10)


def rule_qualify_all(leads: List[Lead]) -> List[Lead]:
    for lead in leads:
        lead.rule_score = score_rule_based(lead)
    leads.sort(key=lambda l: l.rule_score, reverse=True)
    log.info("Rule-based scoring complete for %d leads", len(leads))
    return leads
