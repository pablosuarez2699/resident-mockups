import json
import os
from typing import List
import anthropic

import config
from models.lead import Lead
from utils.logger import get_logger

log = get_logger("claude")

_client: anthropic.Anthropic = None
_system_prompt: str = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")
        with open(os.path.normpath(prompt_path)) as f:
            _system_prompt = f.read()
    return _system_prompt


def _load_qualify_template() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "qualify_lead.txt")
    with open(os.path.normpath(prompt_path)) as f:
        return f.read()


def qualify_lead(lead: Lead) -> dict:
    template = _load_qualify_template()
    user_message = template.format(
        company_name=lead.company_name,
        industry=lead.industry,
        employee_count=lead.employee_count or "Unknown",
        location=lead.location,
        website=lead.website,
        technologies=", ".join(lead.technologies[:10]) if lead.technologies else "Unknown",
        company_description=lead.company_description[:400] if lead.company_description else "N/A",
        annual_revenue_estimate=lead.annual_revenue_estimate or "Unknown",
        title=lead.title,
        lead_type=lead.lead_type,
        sf_prior_year_revenue=lead.sf_prior_year_revenue or "N/A",
    )

    client = _get_client()
    system_prompt = _get_system_prompt()

    try:
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=512,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("Claude returned invalid JSON for %s: %s", lead.company_name, e)
        return {
            "shipping_score": lead.rule_score,
            "current_carrier_estimated": "Unknown",
            "three_pl_risk": False,
            "talking_points": "",
            "reactivation_viable": True,
        }
    except Exception as e:
        log.error("Claude qualify failed for %s: %s", lead.company_name, e)
        return {
            "shipping_score": lead.rule_score,
            "current_carrier_estimated": "Unknown",
            "three_pl_risk": False,
            "talking_points": "",
            "reactivation_viable": True,
        }


def qualify_leads_batch(leads: List[Lead]) -> List[Lead]:
    for i, lead in enumerate(leads):
        log.info("Qualifying lead %d/%d: %s", i + 1, len(leads), lead.company_name)
        result = qualify_lead(lead)
        lead.shipping_score = result.get("shipping_score", lead.rule_score)
        lead.current_carrier_estimated = result.get("current_carrier_estimated", "Unknown")
        lead.three_pl_risk = result.get("three_pl_risk", False)
        lead.talking_points = result.get("talking_points", "")

        if lead.lead_type == "REACTIVATION" and not result.get("reactivation_viable", True):
            lead.shipping_score = min(lead.shipping_score, 3)

        if lead.three_pl_risk:
            lead.shipping_score = min(lead.shipping_score, 4)

    return leads
