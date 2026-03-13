"""CLI interface - rich terminal UI for Domain Seller."""

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import box

from core.config import Config
from core.analyzer import DomainAnalyzer
from core.researcher import BuyerResearcher
from core.lead_scorer import LeadScorer
from core.exporter import export
from core.outreach import generate_outreach_email

console = Console()


def print_banner():
    banner = Text()
    banner.append("  DOMAIN SELLER  ", style="bold white on blue")
    banner.append("  Find real buyers for your domains", style="dim")
    console.print()
    console.print(Panel(banner, border_style="blue", padding=(0, 2)))
    console.print()


def print_analysis(analysis):
    """Print domain analysis results."""
    # Domain info panel
    info_lines = []
    info_lines.append(f"[bold cyan]Domain:[/] {analysis['domain']}")
    info_lines.append(f"[bold cyan]Name:[/] {analysis['name']}")
    info_lines.append(f"[bold cyan]TLD:[/] .{analysis['tld']}")
    info_lines.append(f"[bold cyan]Keywords:[/] {', '.join(analysis['keywords'])}")

    industries = [i.replace('_', ' ').title() for i in analysis['industries']]
    info_lines.append(f"[bold cyan]Industries:[/] {', '.join(industries)}")

    if analysis.get('domain_age_years'):
        info_lines.append(f"[bold cyan]Domain Age:[/] ~{analysis['domain_age_years']} years")

    val_low = analysis.get('estimated_value_low', 0)
    val_high = analysis.get('estimated_value_high', 0)
    info_lines.append(
        f"[bold cyan]Est. Value:[/] [bold green]${val_low:,} - ${val_high:,}[/]"
    )

    console.print(Panel(
        "\n".join(info_lines),
        title="[bold]Domain Analysis[/]",
        border_style="green",
        padding=(1, 2),
    ))

    # WHOIS info
    whois_data = analysis.get('whois', {})
    if whois_data:
        whois_lines = []
        if whois_data.get('registrar'):
            whois_lines.append(f"[cyan]Registrar:[/] {whois_data['registrar']}")
        if whois_data.get('creation_date'):
            whois_lines.append(f"[cyan]Created:[/] {whois_data['creation_date']}")
        if whois_data.get('expiration_date'):
            whois_lines.append(f"[cyan]Expires:[/] {whois_data['expiration_date']}")
        if whois_data.get('registrant'):
            whois_lines.append(f"[cyan]Registrant:[/] {whois_data['registrant']}")
        if whois_lines:
            console.print(Panel(
                "\n".join(whois_lines),
                title="[bold]WHOIS Data[/]",
                border_style="yellow",
                padding=(0, 2),
            ))

    # DNS info
    dns_data = analysis.get('dns', {})
    active_records = {k: v for k, v in dns_data.items() if v}
    if active_records:
        dns_lines = []
        for rtype, records in active_records.items():
            dns_lines.append(f"[cyan]{rtype}:[/] {', '.join(records[:3])}")
        console.print(Panel(
            "\n".join(dns_lines),
            title="[bold]DNS Records[/]",
            border_style="dim",
            padding=(0, 2),
        ))


def print_leads(leads, analysis):
    """Print the leads table."""
    if not leads:
        console.print("\n[yellow]No leads found. Try a different domain or adjust search settings.[/]")
        return

    console.print()
    console.print(Panel(
        f"[bold]Found {len(leads)} potential buyers[/]",
        border_style="blue",
    ))

    for i, lead in enumerate(leads, 1):
        score = lead.get('relevance_score', 0)

        # Score color
        if score >= 70:
            score_style = "bold green"
            stars = "★★★★★"
        elif score >= 50:
            score_style = "bold yellow"
            stars = "★★★★☆"
        elif score >= 35:
            score_style = "yellow"
            stars = "★★★☆☆"
        elif score >= 20:
            score_style = "dim yellow"
            stars = "★★☆☆☆"
        else:
            score_style = "dim"
            stars = "★☆☆☆☆"

        # Build lead card
        lines = []
        lines.append(f"[bold]{lead.get('name', 'Unknown')}[/]")
        lines.append(f"[cyan]Website:[/] {lead.get('website', 'N/A')}")
        lines.append(f"[cyan]Relevance:[/] [{score_style}]{stars} ({score}/100)[/{score_style}]")

        desc = lead.get('description', '') or lead.get('snippet', '')
        if desc:
            # Truncate long descriptions
            if len(desc) > 150:
                desc = desc[:147] + "..."
            lines.append(f"[cyan]About:[/] {desc}")

        emails = lead.get('emails', [])
        if emails:
            lines.append(f"[cyan]Contact:[/] {', '.join(emails[:3])}")

        social = lead.get('social', {})
        social_parts = []
        if social.get('linkedin'):
            social_parts.append(f"[link={social['linkedin']}]LinkedIn[/link]")
        if social.get('twitter'):
            social_parts.append(f"[link={social['twitter']}]Twitter/X[/link]")
        if social_parts:
            lines.append(f"[cyan]Social:[/] {' | '.join(social_parts)}")

        reasons = lead.get('relevance_reasons', [])
        if reasons:
            lines.append(f"[cyan]Why:[/] [italic]{reasons[0]}[/italic]")

        border = "green" if score >= 50 else "yellow" if score >= 30 else "dim"
        console.print(Panel(
            "\n".join(lines),
            title=f"[bold]#{i}[/]",
            border_style=border,
            padding=(0, 2),
        ))


def print_outreach_sample(leads, analysis):
    """Print a sample outreach email for the top lead."""
    if not leads:
        return

    top_lead = leads[0]
    email = generate_outreach_email(top_lead, analysis)

    console.print()
    console.print(Panel(
        f"[bold cyan]Subject:[/] {email['subject']}\n\n{email['body']}",
        title=f"[bold]Sample Outreach Email — {top_lead.get('name', 'Top Lead')}[/]",
        border_style="magenta",
        padding=(1, 2),
    ))


@click.command()
@click.argument("domain")
@click.option("--analyze-only", is_flag=True, help="Only analyze the domain, don't search for buyers")
@click.option("--max-leads", default=0, type=int, help="Maximum leads to return (0 = use config default)")
@click.option("--export-file", default="", help="Export results to file (.csv or .json)")
@click.option("--serpapi-key", default="", help="SerpAPI key for better search results")
@click.option("--config", "config_path", default="", help="Path to config.yaml file")
@click.option("--verbose", is_flag=True, help="Show detailed progress")
@click.option("--show-email", is_flag=True, help="Show sample outreach email")
def main(domain, analyze_only, max_leads, export_file, serpapi_key, config_path, verbose, show_email):
    """Analyze a domain and find potential buyers.

    DOMAIN: The domain name to sell (e.g., healthtrack.com)
    """
    print_banner()

    # Load config
    cfg = Config(config_path if config_path else None)
    if serpapi_key:
        cfg.data["search"]["serpapi_key"] = serpapi_key
        cfg.data["search"]["engine"] = "serpapi"
    if verbose:
        cfg.data["output"]["verbose"] = True

    # --- Step 1: Analyze domain ---
    console.print("[bold blue]▶ Step 1:[/] Analyzing domain...\n")
    try:
        analyzer = DomainAnalyzer(domain)
        analysis = analyzer.analyze()
    except Exception as e:
        console.print(f"[bold red]Error analyzing domain:[/] {e}")
        sys.exit(1)

    print_analysis(analysis)

    if analyze_only:
        console.print("\n[dim]Use without --analyze-only to find potential buyers.[/]")
        return

    # --- Step 2: Research buyers ---
    console.print("\n[bold blue]▶ Step 2:[/] Researching potential buyers...\n")

    def progress_cb(msg):
        if verbose:
            console.print(f"  [dim]{msg}[/]")

    try:
        researcher = BuyerResearcher(cfg, analysis, progress_callback=progress_cb)
        raw_leads = researcher.research()
    except Exception as e:
        console.print(f"[bold red]Error during research:[/] {e}")
        console.print("[dim]Tip: If Google is rate-limiting, try using a SerpAPI key.[/]")
        sys.exit(1)

    # --- Step 3: Score and rank ---
    console.print("\n[bold blue]▶ Step 3:[/] Scoring and ranking leads...\n")
    scorer = LeadScorer(analysis)
    scored_leads = scorer.score_and_rank(raw_leads)

    # Apply filters
    min_score = cfg.get("leads", "min_score", default=20)
    scored_leads = [l for l in scored_leads if l["relevance_score"] >= min_score]

    lead_limit = max_leads if max_leads > 0 else cfg.get("leads", "max_leads", default=20)
    scored_leads = scored_leads[:lead_limit]

    # --- Step 4: Display results ---
    print_leads(scored_leads, analysis)

    # Show sample outreach email
    if show_email or True:  # Always show for top lead
        print_outreach_sample(scored_leads, analysis)

    # --- Step 5: Export ---
    if export_file:
        try:
            path = export(scored_leads, export_file, analysis)
            console.print(f"\n[bold green]✓ Results exported to:[/] {path}")
        except Exception as e:
            console.print(f"\n[bold red]Export failed:[/] {e}")

    auto_export = cfg.get("output", "auto_export", default="")
    if auto_export and not export_file:
        try:
            path = export(scored_leads, auto_export, analysis)
            console.print(f"\n[bold green]✓ Auto-exported to:[/] {path}")
        except Exception as e:
            console.print(f"\n[bold red]Auto-export failed:[/] {e}")

    # Summary
    console.print()
    summary_parts = [
        f"[bold]Summary:[/] Found [bold green]{len(scored_leads)}[/] potential buyers",
        f"for [bold cyan]{domain}[/]",
    ]
    high_quality = sum(1 for l in scored_leads if l["relevance_score"] >= 50)
    if high_quality:
        summary_parts.append(f"([bold]{high_quality}[/] high-relevance)")
    with_contact = sum(1 for l in scored_leads if l.get("emails"))
    if with_contact:
        summary_parts.append(f"([bold]{with_contact}[/] with contact info)")

    console.print(" ".join(summary_parts))
    console.print()


if __name__ == "__main__":
    main()
