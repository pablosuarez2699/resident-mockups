import os
import re
from datetime import date
from typing import List, Dict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

import config
from models.lead import Lead
from models.mode_config import OutreachMode
from models.email_draft import EmailDraft
from clients import claude_client
from utils.logger import get_logger

log = get_logger("composer")
console = Console()


# Relationship-aware snippets. "context" feeds the Claude prompt; "line" is the
# ready-to-drop sentence used by the deterministic template path.
_RELATIONSHIP = {
    "current": {
        "context": "An existing Purolator customer — reinforce the relationship and be proactive, not salesy.",
        "line": "It's a pleasure to have {company} shipping with Purolator, and I want to make sure everything is set up to work as hard as you do. ",
    },
    "lapsed": {
        "context": "Has shipped with Purolator before but activity has lapsed — warm reconnection, no guilt.",
        "line": "I see {company} has shipped with Purolator in the past, and I'd genuinely value the chance to reconnect. ",
    },
    "past": {
        "context": "A former customer — respectful reconnection after some time has passed.",
        "line": "I know it's been a little while since {company} last shipped with Purolator, and I'd welcome the chance to take a fresh look together. ",
    },
    "prospect": {
        "context": "No prior Purolator history — introduce our Canadian strength without assuming a relationship.",
        "line": "I'd love to introduce {company} to what Purolator can do for Canadian businesses like yours. ",
    },
}

_CARRIER_LINE = (
    "As a Canadian carrier, Purolator offers strong domestic transit times, deep "
    "national coverage, and bilingual support coast to coast. "
)


def _signature() -> str:
    lines = [config.REP_NAME, config.REP_TITLE,
             f"Phone: {config.REP_PHONE}", f"Email: {config.REP_EMAIL}"]
    if config.REP_BOOKING_LINK:
        lines.append(f"Book a time: {config.REP_BOOKING_LINK}")
    return "\n".join(lines)


def build_fields(lead: Lead) -> Dict[str, str]:
    """Build the shared .format() field dict used by BOTH the Claude prompt
    templates and the deterministic email templates."""
    rel = _RELATIONSHIP.get((lead.relationship_status or "current").lower(),
                            _RELATIONSHIP["current"])
    company = lead.company_name or "your team"

    carrier = (lead.current_carrier_estimated or "").lower()
    carrier_line = _CARRIER_LINE if ("fedex" in carrier or "ups" in carrier) else ""

    tp = lead.talking_points.strip()
    talking_points_line = (tp if tp.endswith((".", "!", "?")) else tp + ".") + " " if tp else ""

    notes = lead.call_notes.strip()
    call_recap_line = (
        "To briefly recap what we discussed: " + notes.rstrip(".") + ". " if notes else ""
    )

    booking_line = f"Prefer to book a time directly? {config.REP_BOOKING_LINK}" \
        if config.REP_BOOKING_LINK else ""

    return {
        # raw lead fields
        "first_name": lead.first_name,
        "full_name": lead.full_name or "the team",
        "greeting_name": lead.greeting_name,
        "title": lead.title or "Unknown",
        "company_name": company,
        "industry": lead.industry or "Unknown",
        "location": lead.location or "Canada",
        "relationship_status": lead.relationship_status or "current",
        "current_carrier_estimated": lead.current_carrier_estimated or "Unknown",
        "talking_points": tp or "N/A",
        "account_notes": lead.account_notes.strip() or "N/A",
        "call_notes": notes or "N/A",
        # computed snippets
        "relationship_context": rel["context"],
        "relationship_line": rel["line"].format(company=company),
        "carrier_line": carrier_line,
        "talking_points_line": talking_points_line,
        "call_recap_line": call_recap_line,
        "signature": _signature(),
        # rep identity
        "rep_name": config.REP_NAME,
        "rep_title": config.REP_TITLE,
        "rep_phone": config.REP_PHONE,
        "rep_email": config.REP_EMAIL,
        "rep_booking_line": booking_line,
    }


def _subject(lead: Lead, mode: OutreachMode) -> str:
    return mode.subject_template.format(
        company_name=lead.company_name or "your team",
        first_name=lead.first_name or "there",
    )


def render_template(lead: Lead, mode: OutreachMode, fields: Dict[str, str]) -> EmailDraft:
    """Deterministic, zero-cost composition — the free-first fallback."""
    template_path = os.path.join(os.path.dirname(__file__), "..", "templates", mode.template_file)
    with open(os.path.normpath(template_path)) as f:
        body = f.read().format(**fields)
    # Tidy cosmetic whitespace left by empty/optional snippets
    body = re.sub(r"[ \t]+\n", "\n", body).strip()

    return EmailDraft(
        company_name=lead.company_name,
        to_name=lead.full_name,
        to_email=lead.email,
        subject=_subject(lead, mode),
        body=body,
        mode=mode.name,
        generated_by="template",
        date_generated=date.today().isoformat(),
    )


def compose_all(leads: List[Lead], mode: OutreachMode) -> List[EmailDraft]:
    use_llm = config.COMPOSE_MODE == "llm" and bool(config.ANTHROPIC_API_KEY)
    if config.COMPOSE_MODE == "llm" and not config.ANTHROPIC_API_KEY:
        console.print("[yellow]COMPOSE_MODE=llm but no ANTHROPIC_API_KEY — using free template path.[/yellow]")

    drafts: List[EmailDraft] = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(),
                  MofNCompleteColumn(), console=console) as progress:
        task = progress.add_task(
            f"Composing {mode.display_name} emails...", total=len(leads))

        for lead in leads:
            fields = build_fields(lead)
            draft = None
            if use_llm:
                draft = claude_client.compose_email(lead, mode, fields, _subject(lead, mode))
            if draft is None:  # template path, or Claude failed → safe fallback
                draft = render_template(lead, mode, fields)
            drafts.append(draft)
            progress.advance(task)

    by_claude = sum(1 for d in drafts if d.generated_by == "claude")
    log.info("Composed %d drafts (%d via Claude, %d via template)",
             len(drafts), by_claude, len(drafts) - by_claude)
    return drafts
