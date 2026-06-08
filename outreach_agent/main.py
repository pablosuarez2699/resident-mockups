#!/usr/bin/env python3
import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--mode", "mode_keyword", required=True,
              help='Outreach mode trigger: "no-answer" (intro after an unanswered call) '
                   'or "follow-up" (after you spoke with them). Aliases accepted.')
@click.option("--input", "input_path", default=None, type=click.Path(exists=True),
              help="Path to the leads spreadsheet (.xlsx or .csv). Overrides INPUT_FILE.")
@click.option("--source", default=None, type=click.Choice(["excel", "csv", "manual"]),
              help="Input source. Overrides LEAD_SOURCE (default: excel).")
@click.option("--compose", default=None, type=click.Choice(["llm", "template"]),
              help="Composition mode. Overrides COMPOSE_MODE (default: llm).")
@click.option("--dry-run", is_flag=True, default=False,
              help="Parse leads + validate config without composing or writing.")
# Single-lead (manual) flags — used with --source manual
@click.option("--company", default="", help="[manual] Company name")
@click.option("--name", default="", help="[manual] Decision-maker full name")
@click.option("--email", default="", help="[manual] Decision-maker email")
@click.option("--title", default="", help="[manual] Decision-maker title")
@click.option("--phone", default="", help="[manual] Decision-maker phone")
@click.option("--relationship", default="current",
              type=click.Choice(["current", "lapsed", "past", "prospect"]),
              help="[manual] Relationship with Purolator")
@click.option("--carrier", default="Unknown", help="[manual] Estimated current carrier")
@click.option("--call-notes", default="", help="[manual] What you discussed (follow-up mode)")
def main(mode_keyword, input_path, source, compose, dry_run,
         company, name, email, title, phone, relationship, carrier, call_notes):
    """Purolator SMB Outreach Agent — compose personalized, consultative follow-up emails.

    Phone-first: use --mode no-answer for an intro after an unanswered call, or
    --mode follow-up after you've spoken with the decision-maker.
    """
    # Apply CLI overrides to config before importing modules that read it
    import config
    if source:
        config.LEAD_SOURCE = source
    if compose:
        config.COMPOSE_MODE = compose
    if input_path is None and config.INPUT_FILE:
        input_path = config.INPUT_FILE

    from models.mode_config import resolve_mode
    from agent import run

    try:
        mode = resolve_mode(mode_keyword)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise SystemExit(1)

    console.print(f"[bold purple]Purolator SMB Outreach Agent[/bold purple]")

    manual_lead = None
    if config.LEAD_SOURCE == "manual":
        from pipeline.ingester import lead_from_flags
        if not company or not name:
            console.print("[red]Manual mode needs at least --company and --name.[/red]")
            raise SystemExit(1)
        manual_lead = lead_from_flags(
            company=company, name=name, email=email, title=title, phone=phone,
            relationship=relationship, carrier=carrier, call_notes=call_notes)

    run(mode=mode, input_path=input_path, manual_lead=manual_lead, dry_run=dry_run)


if __name__ == "__main__":
    main()
