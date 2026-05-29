from dataclasses import dataclass, field
from typing import List


@dataclass
class OutreachMode:
    name: str
    display_name: str
    keywords: List[str]            # triggers that activate this mode
    subject_template: str          # .format()-templated with lead fields
    prompt_file: str               # Claude user-prompt template in prompts/
    template_file: str             # deterministic free-path body in templates/
    intent_note: str               # one-line summary of the email's purpose


OUTREACH_MODES = {
    "no_answer": OutreachMode(
        name="no_answer",
        display_name="No-Answer Intro",
        keywords=["no-answer", "noanswer", "intro", "missed", "voicemail", "vm"],
        subject_template="Following my call — Purolator + {company_name}",
        prompt_file="compose_no_answer.txt",
        template_file="no_answer.txt",
        intent_note=(
            "I tried reaching them by phone today and couldn't connect — a brief, "
            "consultative introduction and my contact info for whenever it suits them."
        ),
    ),
    "follow_up": OutreachMode(
        name="follow_up",
        display_name="Post-Call Follow-Up",
        keywords=["follow-up", "followup", "post-call", "postcall", "proposal", "recap"],
        subject_template="Great speaking with you, {first_name} — next steps",
        prompt_file="compose_followup.txt",
        template_file="followup.txt",
        intent_note=(
            "We spoke by phone — a thank-you, a recap of what we discussed, a clear "
            "next step/proposal, and my contact info."
        ),
    ),
}


def resolve_mode(keyword: str) -> OutreachMode:
    """Match a typed trigger/keyword to an OutreachMode.

    Raises ValueError with the list of valid triggers on a miss.
    """
    if keyword:
        needle = keyword.strip().lower()
        for mode in OUTREACH_MODES.values():
            if needle == mode.name or needle in mode.keywords:
                return mode

    valid = []
    for mode in OUTREACH_MODES.values():
        valid.append(f"{mode.display_name}: {', '.join([mode.name] + mode.keywords)}")
    raise ValueError(
        f"Unknown mode trigger: '{keyword}'. Valid triggers —\n  " + "\n  ".join(valid)
    )
