from dataclasses import dataclass


@dataclass
class EmailDraft:
    """A composed outreach email — the downstream currency produced by the
    composer and consumed by the output writers. Both the Claude path and the
    deterministic template path produce this identical shape."""

    company_name: str
    to_name: str
    to_email: str
    subject: str
    body: str
    mode: str                      # OutreachMode.name (e.g. "no_answer", "follow_up")
    generated_by: str              # "claude" or "template"
    date_generated: str
    cc: str = ""
    status: str = "draft"

    @property
    def has_email(self) -> bool:
        return bool(self.to_email.strip())
