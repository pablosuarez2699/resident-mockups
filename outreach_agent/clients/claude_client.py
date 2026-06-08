import json
import os
from datetime import date
from typing import Dict, Optional

import anthropic

import config
from models.lead import Lead
from models.mode_config import OutreachMode
from models.email_draft import EmailDraft
from utils.rate_limiter import RateLimiter
from utils.logger import get_logger

log = get_logger("claude")
_limiter = RateLimiter(config.ANTHROPIC_MIN_SPACING_S)

_client: Optional[anthropic.Anthropic] = None
_system_prompt: Optional[str] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        path = os.path.join(os.path.dirname(__file__), "..", "prompts", "system_prompt.txt")
        with open(os.path.normpath(path)) as f:
            _system_prompt = f.read()
    return _system_prompt


def _load_prompt_template(prompt_file: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", prompt_file)
    with open(os.path.normpath(path)) as f:
        return f.read()


def compose_email(lead: Lead, mode: OutreachMode, fields: Dict[str, str],
                  fallback_subject: str) -> Optional[EmailDraft]:
    """Compose one email via Claude. Returns an EmailDraft on success, or None on
    any failure (logged) so the composer can fall back to the template path —
    the run never crashes on a single lead."""
    template = _load_prompt_template(mode.prompt_file)
    user_message = template.format(**fields)

    try:
        _limiter.wait()
        client = _get_client()
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=700,
            system=[
                {
                    "type": "text",
                    "text": _get_system_prompt(),
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
        data = json.loads(raw)
        subject = (data.get("subject") or "").strip() or fallback_subject
        body = (data.get("body") or "").strip()
        if not body:
            log.warning("Claude returned empty body for %s — falling back to template", lead.company_name)
            return None
        return EmailDraft(
            company_name=lead.company_name,
            to_name=lead.full_name,
            to_email=lead.email,
            subject=subject,
            body=body,
            mode=mode.name,
            generated_by="claude",
            date_generated=date.today().isoformat(),
        )
    except json.JSONDecodeError as e:
        log.warning("Claude returned invalid JSON for %s: %s", lead.company_name, e)
        return None
    except Exception as e:
        log.error("Claude compose failed for %s: %s", lead.company_name, e)
        return None
