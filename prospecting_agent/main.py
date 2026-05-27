#!/usr/bin/env python3
import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--sectors", default="retail,healthcare,tech,industrial",
              help="Comma-separated list of sectors (retail, healthcare, tech, industrial)")
@click.option("--leads", default=100, type=int, help="Target number of output leads")
@click.option("--hunter-budget", default=50, type=int, help="Max Hunter.io API calls per run")
@click.option("--pages", default=5, type=int, help="Apollo pages to fetch per sector")
@click.option("--sf-export", default=None, type=click.Path(exists=True),
              help="Path to Salesforce inactive accounts CSV export")
@click.option("--no-cache", is_flag=True, default=False, help="Ignore existing lead cache")
@click.option("--dry-run", is_flag=True, default=False, help="Validate API keys without generating leads")
def main(sectors, leads, hunter_budget, pages, sf_export, no_cache, dry_run):
    """Purolator SMB Prospecting Agent — generate qualified Canadian shipping leads."""
    from agent import run

    sector_list = [s.strip().lower() for s in sectors.split(",") if s.strip()]

    console.print(f"[bold purple]Purolator Prospecting Agent[/bold purple]")
    console.print(f"Sectors: {', '.join(sector_list)} | Target: {leads} leads")
    if sf_export:
        console.print(f"Salesforce export: {sf_export}")

    output = run(
        sectors=sector_list,
        target_leads=leads,
        hunter_budget=hunter_budget,
        pages_per_sector=pages,
        sf_export_path=sf_export,
        use_cache=not no_cache,
        dry_run=dry_run,
    )

    if output:
        console.print(f"\n[bold]Done.[/bold] Open your report:\n  {output}")


if __name__ == "__main__":
    main()
