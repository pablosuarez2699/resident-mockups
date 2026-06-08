from typing import List, Optional

from rich.console import Console

import config
from models.lead import Lead
from models.mode_config import OutreachMode
from pipeline.ingester import ingest
from pipeline.composer import compose_all
from output.draft_writer import write_drafts
from utils.logger import get_logger

log = get_logger("agent")
console = Console()


def run(
    mode: OutreachMode,
    input_path: Optional[str] = None,
    manual_lead: Optional[Lead] = None,
    dry_run: bool = False,
) -> Optional[dict]:
    """Orchestrate: ingest leads -> compose emails for the chosen mode -> write drafts."""

    # Compose-mode banner (free-first, paid-optional)
    if config.COMPOSE_MODE == "llm" and config.ANTHROPIC_API_KEY:
        compose_label = f"[green]Claude ({config.CLAUDE_MODEL}) — tailored composition[/green]"
    else:
        reason = "COMPOSE_MODE=template" if config.COMPOSE_MODE != "llm" else "no ANTHROPIC_API_KEY"
        compose_label = f"[yellow]Deterministic templates (free path — {reason})[/yellow]"
    console.print(f"[bold]Mode:[/bold] {mode.display_name} — {mode.intent_note}")
    console.print(f"[bold]Composition:[/bold] {compose_label}")

    # 1. Ingest
    if manual_lead is not None:
        leads: List[Lead] = [manual_lead]
        console.print("[bold]Source:[/bold] single lead from CLI flags")
    else:
        if not input_path:
            console.print("[red]No input file. Pass --input <file> or use --source manual.[/red]")
            return None
        leads = ingest(input_path)
        console.print(f"[bold]Source:[/bold] {config.LEAD_SOURCE} — {input_path}")

    if not leads:
        console.print("[red]No leads to process.[/red]")
        return None

    no_email = sum(1 for lead in leads if not lead.email)
    console.print(f"[bold]Leads loaded:[/bold] {len(leads)}"
                  + (f" [yellow]({no_email} without an email on file)[/yellow]" if no_email else ""))

    if dry_run:
        console.print("[yellow]Dry run — leads parsed and config validated. No emails composed or written.[/yellow]")
        for lead in leads[:5]:
            console.print(f"  • {lead.company_name} — {lead.full_name or '(no contact)'} "
                          f"<{lead.email or 'no email'}> [{lead.relationship_status}]")
        if len(leads) > 5:
            console.print(f"  … and {len(leads) - 5} more")
        if config.COMPOSE_MODE == "llm" and not config.ANTHROPIC_API_KEY:
            console.print("[yellow]Note: ANTHROPIC_API_KEY not set — a real run would use the free template path.[/yellow]")
        return None

    # 2. Compose
    drafts = compose_all(leads, mode)

    # 3. Write
    result = write_drafts(drafts, mode.name)
    console.print(f"[bold green]Drafts written:[/bold green] {len(result['drafts'])} emails")
    console.print(f"[bold green]Tracking index:[/bold green] {result['index']}")
    return result
