"""CLI interface v2 - rich progress bars, spinners, batch mode, interactive, HTML reports."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from core.analyzer import DomainAnalyzer
from core.config import Config
from core.exporter import export
from core.history import check_domain_history
from core.html_report import generate_html_report
from core.lead_scorer import LeadScorer
from core.market_comp import find_comparable_sales
from core.outreach import generate_all_templates, generate_outreach_email
from core.researcher_v2 import BuyerResearcher
from core.social_checker import check_social_handles
from core.validators import ValidationError, validate_domain

console = Console()


def print_banner():
    banner = Text()
    banner.append("\n  DOMAIN SELLER  ", style="bold white on blue")
    banner.append("  v2.0  ", style="bold blue")
    banner.append("  Find real buyers for your domains\n", style="dim")
    console.print(Panel(banner, border_style="blue", padding=(0, 2)))
    console.print()


def print_analysis(analysis):
    """Print domain analysis results with color-coded value."""
    tbl = Table(
        box=box.ROUNDED, border_style="green", title="[bold]Domain Analysis[/]", show_header=False, padding=(0, 2)
    )
    tbl.add_column("Field", style="cyan", width=14)
    tbl.add_column("Value", style="white")

    tbl.add_row("Domain", f"[bold]{analysis['domain']}[/]")
    tbl.add_row("Name", analysis["name"])
    tbl.add_row("TLD", f".{analysis['tld']}")
    tbl.add_row("Keywords", ", ".join(analysis["keywords"]))

    industries = [i.replace("_", " ").title() for i in analysis["industries"]]
    tbl.add_row("Industries", ", ".join(industries))

    if analysis.get("domain_age_years"):
        age = analysis["domain_age_years"]
        age_style = "bold green" if age >= 10 else "green" if age >= 5 else "yellow"
        tbl.add_row("Domain Age", f"[{age_style}]~{age} years[/]")

    val_low = analysis.get("estimated_value_low", 0)
    val_high = analysis.get("estimated_value_high", 0)
    tbl.add_row("Est. Value", f"[bold green]${val_low:,} — ${val_high:,}[/]")

    console.print(tbl)

    # WHOIS panel (compact)
    whois_data = analysis.get("whois", {})
    if whois_data:
        parts = []
        if whois_data.get("registrar"):
            parts.append(f"[cyan]Registrar:[/] {whois_data['registrar']}")
        if whois_data.get("creation_date"):
            parts.append(f"[cyan]Created:[/] {str(whois_data['creation_date'])[:10]}")
        if whois_data.get("expiration_date"):
            parts.append(f"[cyan]Expires:[/] {str(whois_data['expiration_date'])[:10]}")
        if whois_data.get("registrant"):
            parts.append(f"[cyan]Registrant:[/] {whois_data['registrant']}")
        if parts:
            console.print(Panel("  |  ".join(parts), title="WHOIS", border_style="dim", padding=(0, 1)))

    # DNS (compact)
    dns_data = analysis.get("dns", {})
    active = {k: v for k, v in dns_data.items() if v}
    if active:
        dns_parts = [f"[cyan]{k}:[/] {', '.join(v[:2])}" for k, v in active.items()]
        console.print(Panel("  |  ".join(dns_parts), title="DNS", border_style="dim", padding=(0, 1)))


def print_enrichment(analysis):
    """Print enrichment data: history, social handles, market comparables."""
    # Interpretations / geo
    interps = analysis.get("interpretations", [])
    geo = analysis.get("geo_targets", [])
    niche = analysis.get("niche_context", "")
    if interps or niche:
        parts = []
        if niche:
            parts.append(f"[bold]Niche:[/] {niche}")
        for i in interps[:5]:
            pct = round(i.get("confidence", 0) * 100)
            parts.append(f"[cyan]{i['token']}[/] → {i['expansion']} ({pct}%)")
        if geo:
            parts.append(f"[bold]Geo:[/] {', '.join(geo)}")
        console.print(Panel("\n".join(parts), title="🧠 Smart Interpretation", border_style="magenta", padding=(0, 1)))

    # History
    hist = analysis.get("history", {})
    if hist.get("has_history"):
        h_parts = []
        if hist.get("first_seen"):
            h_parts.append(f"[cyan]First seen:[/] {hist['first_seen']}")
        if hist.get("total_snapshots"):
            h_parts.append(f"[cyan]Snapshots:[/] {hist['total_snapshots']}")
        if hist.get("years_active"):
            h_parts.append(f"[cyan]Years active:[/] {hist['years_active']}")
        if hist.get("past_usage"):
            h_parts.append(f"[cyan]Past usage:[/] {hist['past_usage']}")
        console.print(Panel("  |  ".join(h_parts), title="📜 Domain History", border_style="yellow", padding=(0, 1)))

    # Social handles
    social = analysis.get("social_handles", {})
    handles = social.get("handles", [])
    if handles:
        s_parts = []
        for h in handles:
            icon = "✓" if h["status"] == "taken" else "✗" if h["status"] == "available" else "?"
            style = "green" if h["status"] == "taken" else "red" if h["status"] == "available" else "dim"
            s_parts.append(f"[{style}]{icon} {h['platform']}[/]")
        summary = social.get("summary", "")
        console.print(
            Panel(
                "  ".join(s_parts) + (f"\n{summary}" if summary else ""),
                title=f"📱 @{social.get('handle', '')}",
                border_style="blue",
                padding=(0, 1),
            )
        )

    # Market comparables
    market = analysis.get("market_comp", {})
    comps = market.get("comparables", [])
    if comps:
        tbl = Table(box=box.SIMPLE, border_style="dim", show_header=True, padding=(0, 1))
        tbl.add_column("Domain", style="white")
        tbl.add_column("Price", style="green", justify="right")
        tbl.add_column("Source", style="dim")
        for c in comps[:6]:
            price = f"${c['price']:,.0f}" if c.get("price") else "—"
            tbl.add_row(c.get("domain", ""), price, c.get("source", ""))
        pr = market.get("price_range", {})
        title = "💰 Market Comparables"
        if pr.get("median"):
            title += f"  (median ${pr['median']:,.0f})"
        console.print(Panel(tbl, title=title, border_style="green", padding=(0, 1)))
    elif market.get("market_summary"):
        console.print(f"  [dim]{market['market_summary']}[/]")


def run_research_with_progress(cfg, analysis, verbose):
    """Run buyer research with rich progress bars and spinners."""
    steps = {
        "queries": "Building queries",
        "search": "Searching",
        "extract": "Extracting companies",
        "enrich": "Enriching leads",
        "similar": "Checking similar domains",
        "contacts": "Discovering contacts",
    }
    current_step = {"name": ""}

    progress = Progress(
        SpinnerColumn("dots"),
        TextColumn("[bold blue]{task.description}[/]"),
        BarColumn(bar_width=30),
        TextColumn("[cyan]{task.fields[detail]}[/]"),
        TimeElapsedColumn(),
        console=console,
    )

    task_id = progress.add_task("Starting...", total=None, detail="")

    def progress_cb(msg, step="", total=None, current=None, **kwargs):
        desc = steps.get(step, step) if step else "Working"
        if step != current_step["name"]:
            current_step["name"] = step
            if total:
                progress.update(task_id, total=total, completed=0, description=desc, detail=msg if verbose else "")
            else:
                progress.update(task_id, total=None, completed=0, description=desc, detail=msg if verbose else "")
        elif current is not None:
            progress.update(
                task_id,
                completed=current,
                detail=msg if verbose else f"{current}/{progress.tasks[task_id].total or '?'}",
            )
        elif verbose:
            progress.update(task_id, detail=msg)

    with progress:
        researcher = BuyerResearcher(cfg, analysis, progress_callback=progress_cb)
        raw_leads = researcher.research()
        progress.update(task_id, description="Done", detail=f"{len(raw_leads)} companies found")

    return raw_leads


def print_leads_table(leads, analysis):
    """Print leads as a compact summary table."""
    if not leads:
        console.print("\n[yellow]No leads found. Try a different domain or adjust settings.[/]")
        return

    console.print()
    hot = sum(1 for ld in leads if ld.get("relevance_score", 0) >= 70)
    warm = sum(1 for ld in leads if 50 <= ld.get("relevance_score", 0) < 70)
    with_email = sum(1 for ld in leads if ld.get("emails"))
    with_phone = sum(1 for ld in leads if ld.get("phone"))

    stats = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    stats.add_column("", style="bold")
    stats.add_column("")
    stats.add_row(
        f"[bold green]{len(leads)}[/] leads found",
        f"[green]{hot}[/] hot  |  [yellow]{warm}[/] warm  |  "
        f"[cyan]{with_email}[/] emails  |  [blue]{with_phone}[/] phones",
    )
    console.print(Panel(stats, border_style="blue", title="[bold]Results Summary[/]"))

    # Leads table
    tbl = Table(box=box.ROUNDED, border_style="blue", padding=(0, 1))
    tbl.add_column("#", style="dim", width=3, justify="right")
    tbl.add_column("Company", style="bold white", max_width=30)
    tbl.add_column("Website", style="cyan", max_width=30)
    tbl.add_column("Score", justify="center", width=12)
    tbl.add_column("Contact", style="green", max_width=30)
    tbl.add_column("Why", style="dim italic", max_width=40)

    for i, lead in enumerate(leads, 1):
        score = lead.get("relevance_score", 0)
        if score >= 70:
            score_text = f"[bold green]★★★★★ {score}[/]"
        elif score >= 50:
            score_text = f"[bold yellow]★★★★☆ {score}[/]"
        elif score >= 35:
            score_text = f"[yellow]★★★☆☆ {score}[/]"
        elif score >= 20:
            score_text = f"[dim yellow]★★☆☆☆ {score}[/]"
        else:
            score_text = f"[dim]★☆☆☆☆ {score}[/]"

        contact_parts = []
        if lead.get("emails"):
            contact_parts.append(lead["emails"][0])
        if lead.get("phone"):
            contact_parts.append(lead["phone"])
        contact = "\n".join(contact_parts) if contact_parts else "[dim]—[/]"

        reasons = lead.get("relevance_reasons", ["—"])
        why = reasons[0][:40] if reasons else "—"

        tbl.add_row(str(i), lead.get("name", "?"), lead.get("website_domain", ""), score_text, contact, why)

    console.print(tbl)


def print_lead_detail(lead, idx, analysis):
    """Print detailed view of a single lead."""
    score = lead.get("relevance_score", 0)
    if score >= 70:
        badge = "[bold green]★ HOT LEAD[/]"
        border = "green"
    elif score >= 50:
        badge = "[bold yellow]★ WARM LEAD[/]"
        border = "yellow"
    else:
        badge = "[dim]LEAD[/]"
        border = "dim"

    lines = []
    lines.append(f"[bold white]{lead.get('name', 'Unknown')}[/]  {badge}")
    lines.append(f"[cyan]Website:[/] {lead.get('website', 'N/A')}")
    lines.append(f"[cyan]Score:[/] {score}/100")

    desc = lead.get("description", "") or lead.get("snippet", "")
    if desc:
        if len(desc) > 200:
            desc = desc[:197] + "..."
        lines.append(f"\n[cyan]About:[/] {desc}")

    if lead.get("emails"):
        lines.append(f"\n[cyan]Emails:[/] {', '.join(lead['emails'][:5])}")
    if lead.get("phone"):
        lines.append(f"[cyan]Phone:[/] {lead['phone']}")
    if lead.get("location"):
        lines.append(f"[cyan]Location:[/] {lead['location']}")
    if lead.get("employee_count"):
        lines.append(f"[cyan]Size:[/] {lead['employee_count']}")

    social = lead.get("social", {})
    if social:
        social_parts = []
        for name, url in social.items():
            social_parts.append(f"{name.title()}: {url}")
        lines.append(f"\n[cyan]Social:[/] {' | '.join(social_parts)}")

    techs = lead.get("technologies", [])
    if techs:
        lines.append(f"[cyan]Tech Stack:[/] {', '.join(techs)}")

    reasons = lead.get("relevance_reasons", [])
    if reasons:
        lines.append("\n[cyan]Why relevant:[/]")
        for r in reasons:
            lines.append(f"  [dim]→[/] {r}")

    console.print(Panel("\n".join(lines), title=f"[bold]Lead #{idx}[/]", border_style=border, padding=(1, 2)))


def print_outreach_email(lead, analysis):
    """Print outreach email for a lead."""
    email = generate_outreach_email(lead, analysis)
    console.print(
        Panel(
            f"[bold cyan]Subject:[/] {email['subject']}\n\n{email['body']}",
            title=f"[bold]Outreach Email — {lead.get('name', 'Lead')}[/]",
            border_style="magenta",
            padding=(1, 2),
        )
    )


def interactive_mode(leads, analysis):
    """Interactive mode — browse, inspect, and generate emails for leads."""
    console.print("\n[bold blue]Interactive Mode[/] — type commands below\n")
    console.print(
        "[dim]Commands: [bold]view N[/] (detail) | [bold]email N[/] (outreach) | "
        "[bold]emails N[/] (all templates) | [bold]list[/] (table) | "
        "[bold]export FILE[/] | [bold]html FILE[/] | [bold]quit[/][/]\n"
    )

    while True:
        try:
            cmd = Prompt.ask("[bold blue]>[/]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if not cmd or cmd in ("q", "quit", "exit"):
            break
        elif cmd == "list":
            print_leads_table(leads, analysis)
        elif cmd.startswith("view "):
            try:
                idx = int(cmd.split()[1])
                if 1 <= idx <= len(leads):
                    print_lead_detail(leads[idx - 1], idx, analysis)
                else:
                    console.print(f"[red]Invalid. Use 1-{len(leads)}[/]")
            except ValueError:
                console.print("[red]Usage: view N[/]")
        elif cmd.startswith("email "):
            try:
                idx = int(cmd.split()[1])
                if 1 <= idx <= len(leads):
                    print_outreach_email(leads[idx - 1], analysis)
                else:
                    console.print(f"[red]Invalid. Use 1-{len(leads)}[/]")
            except ValueError:
                console.print("[red]Usage: email N[/]")
        elif cmd.startswith("emails "):
            try:
                idx = int(cmd.split()[1])
                if 1 <= idx <= len(leads):
                    templates = generate_all_templates(leads[idx - 1], analysis)
                    for ttype, email_data in templates.items():
                        console.print(
                            Panel(
                                f"[bold cyan]Subject:[/] {email_data['subject']}\n\n{email_data['body']}",
                                title=f"[bold]{ttype.replace('_', ' ').title()} Template[/]",
                                border_style="magenta",
                                padding=(1, 2),
                            )
                        )
                else:
                    console.print(f"[red]Invalid. Use 1-{len(leads)}[/]")
            except ValueError:
                console.print("[red]Usage: emails N[/]")
        elif cmd.startswith("export "):
            filepath = cmd.split(maxsplit=1)[1]
            try:
                path = export(leads, filepath, analysis)
                console.print(f"[bold green]✓ Exported to {path}[/]")
            except Exception as e:
                console.print(f"[red]Export failed: {e}[/]")
        elif cmd.startswith("html "):
            filepath = cmd.split(maxsplit=1)[1]
            try:
                html_content = generate_html_report(leads, analysis)
                Path(filepath).write_text(html_content, encoding="utf-8")
                console.print(f"[bold green]✓ HTML report saved to {filepath}[/]")
            except Exception as e:
                console.print(f"[red]HTML export failed: {e}[/]")
        else:
            console.print("[dim]Unknown command. Use: view N, email N, emails N, list, export FILE, html FILE, quit[/]")


def process_single_domain(domain, cfg, verbose, max_leads, export_file, show_email, html_file, do_interactive):
    """Process a single domain — full pipeline."""
    console.print(f"\n[bold blue]▶ Step 1:[/] Analyzing [bold cyan]{domain}[/]...\n")

    try:
        with console.status("[bold]Analyzing domain...[/]", spinner="dots"):
            analyzer = DomainAnalyzer(domain)
            analysis = analyzer.analyze()
    except Exception as e:
        console.print(f"[bold red]Error analyzing domain:[/] {e}")
        return None, None

    print_analysis(analysis)

    # Enrichment: domain history, social handles, market comparables — concurrent
    with console.status("[bold]Checking domain history, social handles & market comparables...[/]", spinner="dots"):
        enrichment_fns = {
            "history": lambda: check_domain_history(domain),
            "social_handles": lambda: check_social_handles(analysis["name"]),
            "market_comp": lambda: find_comparable_sales(analysis["name"], analysis["tld"], analysis["keywords"]),
        }
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): key for key, fn in enrichment_fns.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    analysis[key] = future.result()
                except Exception:
                    analysis[key] = {}

    print_enrichment(analysis)
    console.print()

    console.print("[bold blue]▶ Step 2:[/] Researching potential buyers...\n")
    try:
        raw_leads = run_research_with_progress(cfg, analysis, verbose)
    except Exception as e:
        console.print(f"[bold red]Error during research:[/] {e}")
        console.print("[dim]Tip: check your internet connection, or try --serpapi-key[/]")
        return analysis, None

    console.print(f"\n[bold blue]▶ Step 3:[/] Scoring and ranking {len(raw_leads)} leads...\n")
    with console.status("[bold]Scoring leads...[/]", spinner="dots"):
        scorer = LeadScorer(analysis)
        scored_leads = scorer.score_and_rank(raw_leads)

    min_score = cfg.get("leads", "min_score", default=20)
    scored_leads = [ld for ld in scored_leads if ld["relevance_score"] >= min_score]

    lead_limit = max_leads if max_leads > 0 else cfg.get("leads", "max_leads", default=20)
    scored_leads = scored_leads[:lead_limit]

    # Display
    print_leads_table(scored_leads, analysis)

    # Show top 3 lead details automatically
    for i, lead in enumerate(scored_leads[:3], 1):
        if lead.get("relevance_score", 0) >= 50:
            print_lead_detail(lead, i, analysis)

    # Outreach email
    if show_email and scored_leads:
        print_outreach_email(scored_leads[0], analysis)

    # Export CSV/JSON
    if export_file:
        try:
            path = export(scored_leads, export_file, analysis)
            console.print(f"\n[bold green]✓ Exported to:[/] {path}")
        except Exception as e:
            console.print(f"\n[bold red]Export failed:[/] {e}")

    # HTML report
    if html_file:
        try:
            html_content = generate_html_report(scored_leads, analysis)
            Path(html_file).write_text(html_content, encoding="utf-8")
            console.print(f"[bold green]✓ HTML report saved to:[/] {html_file}")
        except Exception as e:
            console.print(f"\n[bold red]HTML report failed:[/] {e}")

    # Auto-export
    auto_export = cfg.get("output", "auto_export", default="")
    if auto_export and not export_file:
        try:
            path = export(scored_leads, auto_export, analysis)
            console.print(f"[bold green]✓ Auto-exported to:[/] {path}")
        except Exception as e:
            console.print(f"[bold red]Auto-export failed:[/] {e}")

    # Summary
    console.print()
    high_q = sum(1 for ld in scored_leads if ld["relevance_score"] >= 50)
    with_mail = sum(1 for ld in scored_leads if ld.get("emails"))
    with_phone = sum(1 for ld in scored_leads if ld.get("phone"))
    console.print(
        f"[bold]Summary:[/] [green]{len(scored_leads)}[/] buyers for [cyan]{domain}[/]"
        f"  |  [green]{high_q}[/] high-relevance"
        f"  |  [cyan]{with_mail}[/] with email"
        f"  |  [blue]{with_phone}[/] with phone"
    )

    # Interactive mode
    if do_interactive and scored_leads:
        interactive_mode(scored_leads, analysis)

    return analysis, scored_leads


@click.command()
@click.argument("domains", nargs=-1, required=True)
@click.option("--analyze-only", is_flag=True, help="Only analyze domain, skip buyer research")
@click.option("--max-leads", default=0, type=int, help="Maximum leads per domain (0 = config default)")
@click.option("--export-file", default="", help="Export results (.csv or .json)")
@click.option("--html", "html_file", default="", help="Generate HTML report (.html)")
@click.option("--serpapi-key", default="", help="SerpAPI key for better search")
@click.option("--config", "config_path", default="", help="Path to config.yaml")
@click.option("--verbose", is_flag=True, help="Show detailed progress")
@click.option("--show-email", is_flag=True, help="Show sample outreach email")
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive mode after results")
@click.option("--no-cache", is_flag=True, help="Disable result caching")
@click.option("--clear-cache", is_flag=True, help="Clear cached results and exit")
def main(
    domains,
    analyze_only,
    max_leads,
    export_file,
    html_file,
    serpapi_key,
    config_path,
    verbose,
    show_email,
    interactive,
    no_cache,
    clear_cache,
):
    """Analyze domains and find potential buyers.

    DOMAINS: One or more domain names to sell (e.g., healthtrack.com cloudpay.io)
    """
    print_banner()

    # Validate all domains upfront
    validated_domains = []
    for d in domains:
        try:
            validated_domains.append(validate_domain(d))
        except ValidationError as e:
            console.print(f"[bold red]Invalid domain '{d}':[/] {e}")
            return
    domains = tuple(validated_domains)

    # Load config
    cfg = Config(config_path if config_path else None)
    if serpapi_key:
        cfg.data["search"]["serpapi_key"] = serpapi_key
        cfg.data["search"]["engine"] = "serpapi"
    if verbose:
        cfg.data["output"]["verbose"] = True
    if no_cache:
        cfg.data.setdefault("cache", {})["enabled"] = False

    # Clear cache
    if clear_cache:
        from core.cache import SearchCache

        SearchCache(enabled=True).clear()
        console.print("[bold green]✓ Cache cleared.[/]")
        return

    # Analyze-only mode
    if analyze_only:
        for domain in domains:
            console.print(f"\n[bold blue]Analyzing:[/] [cyan]{domain}[/]\n")
            try:
                with console.status("[bold]Analyzing...[/]", spinner="dots"):
                    analyzer = DomainAnalyzer(domain)
                    analysis = analyzer.analyze()
                print_analysis(analysis)

                with console.status(
                    "[bold]Checking domain history, social handles & market comparables...[/]", spinner="dots"
                ):
                    _d, _a = domain, analysis
                    enrichment_fns = {
                        "history": lambda d=_d: check_domain_history(d),
                        "social_handles": lambda a=_a: check_social_handles(a["name"]),
                        "market_comp": lambda a=_a: find_comparable_sales(a["name"], a["tld"], a["keywords"]),
                    }
                    with ThreadPoolExecutor(max_workers=3) as executor:
                        futures = {executor.submit(fn): key for key, fn in enrichment_fns.items()}
                        for future in as_completed(futures):
                            key = futures[future]
                            try:
                                analysis[key] = future.result()
                            except Exception:
                                analysis[key] = {}
                print_enrichment(analysis)
            except Exception as e:
                console.print(f"[bold red]Error:[/] {e}")
        return

    # Batch mode
    if len(domains) > 1:
        console.print(f"[bold]Batch mode:[/] Processing {len(domains)} domains\n")
        all_results = {}
        for d_idx, domain in enumerate(domains, 1):
            console.print(f"\n{'━' * 60}")
            console.print(f"[bold blue]Domain {d_idx}/{len(domains)}:[/] [bold cyan]{domain}[/]")
            console.print(f"{'━' * 60}")

            batch_export = ""
            if export_file:
                stem = Path(export_file).stem
                suffix = Path(export_file).suffix
                batch_export = f"{stem}_{domain.replace('.', '_')}{suffix}"

            batch_html = ""
            if html_file:
                stem = Path(html_file).stem
                suffix = Path(html_file).suffix
                batch_html = f"{stem}_{domain.replace('.', '_')}{suffix}"

            analysis, leads = process_single_domain(
                domain,
                cfg,
                verbose,
                max_leads,
                batch_export,
                show_email,
                batch_html,
                do_interactive=False,
            )
            if leads:
                all_results[domain] = {"analysis": analysis, "leads": leads}

        # Batch summary
        console.print(f"\n{'━' * 60}")
        console.print("[bold]Batch Summary[/]")
        console.print(f"{'━' * 60}\n")
        summ = Table(box=box.ROUNDED, border_style="blue")
        summ.add_column("Domain", style="cyan")
        summ.add_column("Leads", justify="center")
        summ.add_column("Hot", justify="center", style="green")
        summ.add_column("With Email", justify="center")
        summ.add_column("Top Lead")
        for d, data in all_results.items():
            leads = data["leads"]
            hot = sum(1 for ld in leads if ld.get("relevance_score", 0) >= 70)
            with_email = sum(1 for ld in leads if ld.get("emails"))
            top = leads[0].get("name", "—") if leads else "—"
            summ.add_row(d, str(len(leads)), str(hot), str(with_email), top)
        console.print(summ)

        if interactive:
            console.print("\n[bold]Select a domain to explore interactively:[/]")
            for i, d in enumerate(all_results.keys(), 1):
                console.print(f"  [bold]{i}.[/] {d}")
            try:
                choice = Prompt.ask("Domain #", default="1")
                idx = int(choice) - 1
                d_list = list(all_results.keys())
                if 0 <= idx < len(d_list):
                    chosen = d_list[idx]
                    interactive_mode(all_results[chosen]["leads"], all_results[chosen]["analysis"])
            except (ValueError, KeyboardInterrupt):
                pass
    else:
        # Single domain
        process_single_domain(
            domains[0],
            cfg,
            verbose,
            max_leads,
            export_file,
            show_email,
            html_file,
            do_interactive=interactive,
        )

    console.print()


if __name__ == "__main__":
    main()
