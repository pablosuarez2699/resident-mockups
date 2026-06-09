import random
from typing import List, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

import config
from models.sector_config import SECTOR_CONFIGS, SectorConfig
from models.lead import Lead
from pipeline import fetcher as fetcher_module
from pipeline.fetcher import fetch_sector
from pipeline.enricher import enrich_emails
from pipeline.linkedin_builder import build_urls_batch
from pipeline.qualifier import rule_qualify_all
from clients.claude_client import qualify_leads_batch
from output.excel_writer import write_excel
from utils.cache import LeadCache
from utils.sf_loader import load_sf_accounts, match_sf_account
from utils.logger import get_logger

log = get_logger("agent")
console = Console()


def run(
    sectors: List[str],
    target_leads: int = config.TARGET_LEADS,
    hunter_budget: int = config.HUNTER_BUDGET_PER_RUN,
    pages_per_sector: int = config.APOLLO_PAGES_PER_SECTOR,
    sf_export_path: Optional[str] = None,
    use_cache: bool = True,
    dry_run: bool = False,
    randomize: bool = False,
) -> Optional[str]:

    cache = LeadCache()
    if not use_cache:
        # Bypass seen-checks for this run only — history is preserved, and new
        # leads are still recorded. WARNING: this run may repeat past companies.
        cache.bypass = True
        console.print("[bold red]⚠ --no-cache: this run may repeat companies "
                      "from previous reports. Freshness history is preserved.[/bold red]")

    sf_accounts = {}
    if sf_export_path:
        sf_accounts = load_sf_accounts(sf_export_path)
        console.print(f"[bold]Salesforce accounts loaded:[/bold] {len(sf_accounts)}")

    valid_sectors = [s for s in sectors if s in SECTOR_CONFIGS]
    if not valid_sectors:
        console.print(f"[red]No valid sectors specified. Choose from: {list(SECTOR_CONFIGS.keys())}[/red]")
        return None

    if config.LEAD_SOURCE == "google":
        source_label = "[green]Google Places + Hunter domain-search + web scraper (free path)[/green]"
    else:
        source_label = (
            "[yellow]Apollo.io PAID — emails + phones enabled[/yellow]"
            if config.APOLLO_PLAN == "paid"
            else "[yellow]Apollo.io FREE — lookup-assist mode[/yellow]"
        )
    console.print(f"[bold]Lead source:[/bold] {source_label}")

    # Reset Hunter domain-search budget for this run (Google path only)
    fetcher_module.init_run()

    if dry_run:
        console.print("[yellow]Dry run: validating API connectivity...[/yellow]")
        if config.LEAD_SOURCE == "google":
            from clients.google_places_client import health_check as gp_check
            ok = gp_check()
            console.print(f"Google Places API: {'[green]OK[/green]' if ok else '[red]FAILED — check GOOGLE_PLACES_API_KEY[/red]'}")
        else:
            from clients.apollo_client import health_check
            ok = health_check()
            console.print(f"Apollo API: {'[green]OK[/green]' if ok else '[red]FAILED[/red]'}")
        if config.ANTHROPIC_API_KEY:
            console.print("[green]Anthropic API key: present[/green]")
        else:
            console.print("[red]Anthropic API key: MISSING[/red]")
        if config.HUNTER_API_KEY:
            console.print(f"[green]Hunter API key: present (domain-search budget: {config.HUNTER_DOMAIN_SEARCH_BUDGET}/run)[/green]")
        else:
            console.print("[yellow]Hunter API key: not set — contact scraping will use website-only fallback[/yellow]")
        return None

    all_leads: List[Lead] = []
    leads_per_sector = max(target_leads // len(valid_sectors), 20)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), MofNCompleteColumn(), console=console) as progress:
        fetch_task = progress.add_task("Fetching leads from Apollo...", total=len(valid_sectors))

        for sector_name in valid_sectors:
            sector = SECTOR_CONFIGS[sector_name]
            leads = fetch_sector(sector, cache, pages_per_sector, leads_per_sector)
            all_leads.extend(leads)
            progress.advance(fetch_task)

    console.print(f"[bold]Total raw leads fetched:[/bold] {len(all_leads)}")

    # Salesforce reactivation matching
    if sf_accounts:
        for lead in all_leads:
            match = match_sf_account(lead.company_name, sf_accounts)
            if match:
                lead.lead_type = "REACTIVATION"
                lead.sf_prior_year_revenue = match.get("prior_year_revenue")

    # LinkedIn URLs
    build_urls_batch(all_leads)

    # Rule-based pre-scoring and sort
    all_leads = rule_qualify_all(all_leads)

    # Claude refinement on top 120% candidates
    claude_pool_size = min(int(target_leads * 1.2), len(all_leads))
    claude_pool = all_leads[:claude_pool_size]

    console.print(f"[bold]Sending {len(claude_pool)} leads to Claude for qualification...[/bold]")
    claude_pool = qualify_leads_batch(claude_pool)

    # Hunter find-email enrichment for Apollo-paid path (Google path handles Hunter inline)
    if config.LEAD_SOURCE == "apollo" and config.APOLLO_PLAN == "paid" \
            and config.HUNTER_API_KEY and hunter_budget > 0:
        missing_email = sum(1 for l in claude_pool if not l.email)
        console.print(
            f"[bold]Hunter email enrichment:[/bold] {missing_email} contacts without email "
            f"(budget: {hunter_budget})"
        )
        claude_pool = enrich_emails(claude_pool, hunter_budget)

    # $25K/yr shipping spend filter: drop companies estimated below the
    # volume bar (MIN_DAILY_SHIPMENTS parcels/business day, ~$20 avg parcel)
    if config.MIN_DAILY_SHIPMENTS > 0:
        before = len(claude_pool)
        claude_pool = [
            l for l in claude_pool
            if l.meets_spend_threshold and (
                l.est_daily_shipments == 0  # estimate unavailable (API fallback) — keep
                or l.est_daily_shipments >= config.MIN_DAILY_SHIPMENTS
            )
        ]
        dropped = before - len(claude_pool)
        if dropped:
            console.print(
                f"[yellow]Spend filter:[/yellow] dropped {dropped} leads below "
                f"~{config.MIN_DAILY_SHIPMENTS} shipments/day (≈$25K/yr)"
            )

    # Final sort — strict by score, or shuffled within score bands for variety
    if randomize:
        high   = [l for l in claude_pool if l.shipping_score >= 8]
        medium = [l for l in claude_pool if 5 <= l.shipping_score < 8]
        low    = [l for l in claude_pool if l.shipping_score < 5]
        random.shuffle(high)
        random.shuffle(medium)
        random.shuffle(low)
        final_leads = (high + medium + low)[:target_leads]
        console.print("[cyan]Randomized output:[/cyan] leads shuffled within score bands")
    else:
        final_leads = sorted(claude_pool, key=lambda l: l.shipping_score, reverse=True)[:target_leads]

    console.print(f"[bold green]Final leads selected:[/bold green] {len(final_leads)}")

    output_path = None
    try:
        output_path = write_excel(final_leads, valid_sectors)
        console.print(f"[bold green]Report saved:[/bold green] {output_path}")
    finally:
        cache.save()

    return output_path
