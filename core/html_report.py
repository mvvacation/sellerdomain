"""HTML report generator - creates a beautiful standalone HTML report."""

import html
from datetime import datetime


def generate_html_report(leads, analysis):
    """Generate a standalone HTML report with embedded CSS."""
    domain = analysis["domain"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    leads_html = ""
    for i, lead in enumerate(leads, 1):
        score = lead.get("relevance_score", 0)
        if score >= 70:
            badge_class = "badge-hot"
            badge_text = "HOT"
        elif score >= 50:
            badge_class = "badge-warm"
            badge_text = "WARM"
        elif score >= 30:
            badge_class = "badge-cool"
            badge_text = "COOL"
        else:
            badge_class = "badge-low"
            badge_text = "LOW"

        score_bar_color = "#22c55e" if score >= 70 else "#eab308" if score >= 40 else "#94a3b8"
        name = html.escape(lead.get("name", "Unknown"))
        website = html.escape(lead.get("website", ""))
        website_domain = html.escape(lead.get("website_domain", ""))
        desc = html.escape(lead.get("description", "") or lead.get("snippet", ""))
        if len(desc) > 200:
            desc = desc[:197] + "..."

        emails_html = ""
        for email_addr in lead.get("emails", [])[:3]:
            emails_html += f'<a href="mailto:{html.escape(email_addr)}" class="email-link">{html.escape(email_addr)}</a> '

        phone = html.escape(lead.get("phone", ""))
        phone_html = f'<span class="detail-value">{phone}</span>' if phone else ""

        social = lead.get("social", {})
        social_html = ""
        if social.get("linkedin"):
            social_html += f'<a href="{html.escape(social["linkedin"])}" target="_blank" class="social-link li">LinkedIn</a> '
        if social.get("twitter"):
            social_html += f'<a href="{html.escape(social["twitter"])}" target="_blank" class="social-link tw">Twitter/X</a> '
        if social.get("facebook"):
            social_html += f'<a href="{html.escape(social["facebook"])}" target="_blank" class="social-link fb">Facebook</a> '

        reasons = lead.get("relevance_reasons", [])
        reasons_html = ""
        for r in reasons[:3]:
            reasons_html += f'<li>{html.escape(r)}</li>'

        location = html.escape(lead.get("location", ""))
        employees = html.escape(lead.get("employee_count", ""))
        tech_html = ""
        techs = lead.get("technologies", [])
        if techs:
            tech_html = '<div class="tech-tags">' + "".join(
                f'<span class="tech-tag">{html.escape(t)}</span>' for t in techs[:8]
            ) + '</div>'

        leads_html += f"""
        <div class="lead-card" data-score="{score}">
            <div class="lead-header">
                <div class="lead-rank">#{i}</div>
                <div class="lead-name-area">
                    <h3>{name}</h3>
                    <a href="{website}" target="_blank" class="lead-website">{website_domain}</a>
                </div>
                <div class="lead-score-area">
                    <span class="badge {badge_class}">{badge_text}</span>
                    <div class="score-bar-container">
                        <div class="score-bar" style="width: {score}%; background: {score_bar_color};"></div>
                    </div>
                    <span class="score-label">{score}/100</span>
                </div>
            </div>
            {"<p class='lead-desc'>" + desc + "</p>" if desc else ""}
            <div class="lead-details">
                {"<div class='detail-row'><span class='detail-label'>Contact:</span> " + emails_html + "</div>" if emails_html else ""}
                {"<div class='detail-row'><span class='detail-label'>Phone:</span> " + phone_html + "</div>" if phone_html else ""}
                {"<div class='detail-row'><span class='detail-label'>Social:</span> " + social_html + "</div>" if social_html else ""}
                {"<div class='detail-row'><span class='detail-label'>Location:</span> <span class='detail-value'>" + location + "</span></div>" if location else ""}
                {"<div class='detail-row'><span class='detail-label'>Size:</span> <span class='detail-value'>" + employees + "</span></div>" if employees else ""}
                {tech_html}
                {"<div class='detail-row'><span class='detail-label'>Why relevant:</span><ul class='reasons'>" + reasons_html + "</ul></div>" if reasons_html else ""}
            </div>
        </div>"""

    # Analytics
    total = len(leads)
    hot_count = sum(1 for l in leads if l.get("relevance_score", 0) >= 70)
    warm_count = sum(1 for l in leads if 50 <= l.get("relevance_score", 0) < 70)
    with_email = sum(1 for l in leads if l.get("emails"))
    with_social = sum(1 for l in leads if l.get("social", {}).get("linkedin"))
    avg_score = sum(l.get("relevance_score", 0) for l in leads) / max(1, total)

    val_low = analysis.get("estimated_value_low", 0)
    val_high = analysis.get("estimated_value_high", 0)
    industries = [i.replace("_", " ").title() for i in analysis.get("industries", [])]
    keywords = analysis.get("keywords", [])

    # Build enrichment HTML
    enrichment_html = _build_enrichment_html(analysis)

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Domain Seller Report — {html.escape(domain)}</title>
<style>
:root {{ --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #e2e8f0;
    --muted: #94a3b8; --accent: #3b82f6; --green: #22c55e; --yellow: #eab308;
    --red: #ef4444; --purple: #a855f7; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
    color: var(--text); line-height: 1.6; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem; }}
.header {{ text-align: center; margin-bottom: 2.5rem; }}
.header h1 {{ font-size: 2.2rem; color: #fff; margin-bottom: 0.25rem; }}
.header h1 span {{ color: var(--accent); }}
.header .subtitle {{ color: var(--muted); font-size: 1rem; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem; margin-bottom: 2rem; }}
.stat-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.2rem; text-align: center; }}
.stat-value {{ font-size: 1.8rem; font-weight: 700; color: #fff; }}
.stat-value.green {{ color: var(--green); }}
.stat-value.yellow {{ color: var(--yellow); }}
.stat-value.accent {{ color: var(--accent); }}
.stat-value.purple {{ color: var(--purple); }}
.stat-label {{ font-size: 0.8rem; color: var(--muted); text-transform: uppercase;
    letter-spacing: 0.05em; margin-top: 0.25rem; }}
.analysis-panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.5rem; margin-bottom: 2rem; }}
.analysis-panel h2 {{ font-size: 1.1rem; color: var(--accent); margin-bottom: 1rem;
    border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
.analysis-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; }}
.analysis-item {{ display: flex; gap: 0.5rem; }}
.analysis-item .label {{ color: var(--muted); min-width: 90px; font-size: 0.9rem; }}
.analysis-item .value {{ color: #fff; font-weight: 500; font-size: 0.9rem; }}
.value-highlight {{ color: var(--green) !important; font-size: 1.1rem !important; }}
.section-title {{ font-size: 1.3rem; color: #fff; margin: 2rem 0 1rem; }}
.lead-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.2rem 1.5rem; margin-bottom: 1rem; transition: border-color 0.2s; }}
.lead-card:hover {{ border-color: var(--accent); }}
.lead-card[data-score]:not([data-score="0"]) {{ }}
.lead-header {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }}
.lead-rank {{ font-size: 1.2rem; font-weight: 700; color: var(--muted); min-width: 35px; }}
.lead-name-area {{ flex: 1; }}
.lead-name-area h3 {{ font-size: 1.05rem; color: #fff; }}
.lead-website {{ font-size: 0.85rem; color: var(--accent); text-decoration: none; }}
.lead-website:hover {{ text-decoration: underline; }}
.lead-score-area {{ text-align: right; min-width: 120px; }}
.badge {{ display: inline-block; padding: 0.15rem 0.6rem; border-radius: 6px;
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }}
.badge-hot {{ background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }}
.badge-warm {{ background: rgba(234,179,8,0.15); color: var(--yellow); border: 1px solid rgba(234,179,8,0.3); }}
.badge-cool {{ background: rgba(59,130,246,0.15); color: var(--accent); border: 1px solid rgba(59,130,246,0.3); }}
.badge-low {{ background: rgba(148,163,184,0.1); color: var(--muted); border: 1px solid rgba(148,163,184,0.2); }}
.score-bar-container {{ width: 100px; height: 6px; background: rgba(255,255,255,0.1);
    border-radius: 3px; margin: 0.4rem 0 0.2rem auto; }}
.score-bar {{ height: 100%; border-radius: 3px; transition: width 0.3s; }}
.score-label {{ font-size: 0.75rem; color: var(--muted); }}
.lead-desc {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 0.75rem; }}
.lead-details {{ font-size: 0.85rem; }}
.detail-row {{ margin-bottom: 0.4rem; display: flex; align-items: flex-start; gap: 0.5rem; }}
.detail-label {{ color: var(--muted); min-width: 70px; }}
.detail-value {{ color: var(--text); }}
.email-link {{ color: var(--accent); text-decoration: none; margin-right: 0.5rem; }}
.email-link:hover {{ text-decoration: underline; }}
.social-link {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
    font-size: 0.75rem; text-decoration: none; margin-right: 0.3rem; }}
.social-link.li {{ background: rgba(0,119,181,0.15); color: #0077b5; }}
.social-link.tw {{ background: rgba(29,161,242,0.15); color: #1da1f2; }}
.social-link.fb {{ background: rgba(24,119,242,0.15); color: #1877f2; }}
.reasons {{ list-style: none; padding: 0; }}
.reasons li {{ color: var(--muted); font-style: italic; }}
.reasons li::before {{ content: "→ "; color: var(--accent); }}
.tech-tags {{ display: flex; flex-wrap: wrap; gap: 0.3rem; margin: 0.4rem 0; }}
.tech-tag {{ background: rgba(168,85,247,0.12); color: var(--purple); padding: 0.1rem 0.4rem;
    border-radius: 4px; font-size: 0.75rem; }}
/* Enrichment sections */
.enrich-panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.5rem; margin-bottom: 1rem; }}
.enrich-panel h2 {{ font-size: 1.1rem; margin-bottom: 1rem;
    border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
.enrich-panel h2.hist {{ color: #f59e0b; }}
.enrich-panel h2.social {{ color: #06b6d4; }}
.enrich-panel h2.market {{ color: var(--green); }}
.enrich-panel h2.interp {{ color: var(--purple); }}
.enrich-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }}
.enrich-item {{ display: flex; gap: 0.5rem; }}
.enrich-item .elbl {{ color: var(--muted); min-width: 100px; font-size: 0.9rem; }}
.enrich-item .eval {{ color: #fff; font-weight: 500; font-size: 0.9rem; }}
.handle-grid {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem; }}
.handle-pill {{ display: inline-block; padding: 0.25rem 0.7rem; border-radius: 6px;
    font-size: 0.8rem; font-weight: 600; }}
.handle-taken {{ background: rgba(34,197,94,0.12); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }}
.handle-avail {{ background: rgba(239,68,68,0.1); color: var(--red); border: 1px solid rgba(239,68,68,0.2); }}
.handle-unk {{ background: rgba(148,163,184,0.1); color: var(--muted); border: 1px solid rgba(148,163,184,0.2); }}
.comp-table {{ width: 100%; border-collapse: collapse; margin-top: 0.75rem; }}
.comp-table th {{ text-align: left; color: var(--muted); font-size: 0.8rem; text-transform: uppercase;
    letter-spacing: 0.05em; padding: 0.5rem; border-bottom: 1px solid var(--border); }}
.comp-table td {{ padding: 0.5rem; font-size: 0.85rem; border-bottom: 1px solid rgba(51,65,85,0.5); }}
.comp-table td.price {{ color: var(--green); font-weight: 600; }}
.comp-table a {{ color: var(--accent); text-decoration: none; }}
.comp-table a:hover {{ text-decoration: underline; }}
.enrich-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }}
@media (max-width: 700px) {{ .enrich-row {{ grid-template-columns: 1fr; }} }}
.footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 3rem;
    padding-top: 1.5rem; border-top: 1px solid var(--border); }}
.filter-bar {{ display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
.filter-btn {{ background: var(--card); border: 1px solid var(--border); color: var(--text);
    padding: 0.4rem 0.8rem; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }}
.filter-btn:hover, .filter-btn.active {{ border-color: var(--accent); color: var(--accent); }}
@media (max-width: 600px) {{
    .lead-header {{ flex-direction: column; align-items: flex-start; }}
    .lead-score-area {{ text-align: left; }}
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Domain Seller Report: <span>{html.escape(domain)}</span></h1>
        <p class="subtitle">Generated {now} &middot; {total} potential buyers identified</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card"><div class="stat-value accent">{total}</div><div class="stat-label">Total Leads</div></div>
        <div class="stat-card"><div class="stat-value green">{hot_count}</div><div class="stat-label">Hot Leads</div></div>
        <div class="stat-card"><div class="stat-value yellow">{warm_count}</div><div class="stat-label">Warm Leads</div></div>
        <div class="stat-card"><div class="stat-value purple">{with_email}</div><div class="stat-label">With Email</div></div>
        <div class="stat-card"><div class="stat-value">{avg_score:.0f}</div><div class="stat-label">Avg Score</div></div>
        <div class="stat-card"><div class="stat-value green">${val_low:,}–${val_high:,}</div><div class="stat-label">Est. Value</div></div>
    </div>

    <div class="analysis-panel">
        <h2>Domain Analysis</h2>
        <div class="analysis-grid">
            <div class="analysis-item"><span class="label">Domain:</span><span class="value">{html.escape(domain)}</span></div>
            <div class="analysis-item"><span class="label">Keywords:</span><span class="value">{html.escape(', '.join(keywords))}</span></div>
            <div class="analysis-item"><span class="label">Industries:</span><span class="value">{html.escape(', '.join(industries))}</span></div>
            <div class="analysis-item"><span class="label">Domain Age:</span><span class="value">~{analysis.get('domain_age_years', 0)} years</span></div>
            <div class="analysis-item"><span class="label">Est. Value:</span><span class="value value-highlight">${val_low:,} – ${val_high:,}</span></div>
        </div>
    </div>

    {enrichment_html}

    <h2 class="section-title">Potential Buyers</h2>

    <div class="filter-bar">
        <button class="filter-btn active" onclick="filterLeads('all')">All ({total})</button>
        <button class="filter-btn" onclick="filterLeads(70)">Hot ({hot_count})</button>
        <button class="filter-btn" onclick="filterLeads(50)">Warm+ ({hot_count + warm_count})</button>
        <button class="filter-btn" onclick="filterLeads('email')">Has Email ({with_email})</button>
    </div>

    <div id="leads-container">
        {leads_html}
    </div>

    <div class="footer">
        Generated by Domain Seller &middot; {now}
    </div>
</div>

<script>
function filterLeads(criteria) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.querySelectorAll('.lead-card').forEach(card => {{
        const score = parseInt(card.dataset.score);
        if (criteria === 'all') {{ card.style.display = ''; }}
        else if (criteria === 'email') {{
            card.style.display = card.querySelector('.email-link') ? '' : 'none';
        }}
        else {{ card.style.display = score >= criteria ? '' : 'none'; }}
    }});
}}
</script>
</body>
</html>"""

    return report_html


def _build_enrichment_html(analysis):
    """Build HTML sections for history, social handles, market comparables."""
    sections = []

    # --- Interpretation / TLD Intelligence ---
    interp_items = []
    tld_industry = analysis.get("tld_industry")
    tld_geo = analysis.get("tld_geo")
    niche = analysis.get("niche_context")
    abbr_exp = analysis.get("abbreviation_expansions", {})
    geo_targets = analysis.get("geo_targets", [])
    brandability = analysis.get("brandability")

    if tld_industry or tld_geo or niche or abbr_exp or geo_targets or brandability:
        items_html = ""
        if niche:
            items_html += f'<div class="enrich-item"><span class="elbl">Niche:</span><span class="eval">{html.escape(niche)}</span></div>'
        if tld_industry:
            items_html += f'<div class="enrich-item"><span class="elbl">TLD Industry:</span><span class="eval">{html.escape(tld_industry)}</span></div>'
        if tld_geo:
            items_html += f'<div class="enrich-item"><span class="elbl">TLD Geo:</span><span class="eval">{html.escape(tld_geo)}</span></div>'
        if brandability:
            score = brandability.get("score", 0)
            grade = brandability.get("grade", brandability.get("label", ""))
            items_html += f'<div class="enrich-item"><span class="elbl">Brandability:</span><span class="eval">{score}/100 ({html.escape(grade)})</span></div>'
        if geo_targets:
            items_html += f'<div class="enrich-item"><span class="elbl">Geo Targets:</span><span class="eval">{html.escape(", ".join(geo_targets[:5]))}</span></div>'
        if abbr_exp:
            exp_parts = [f"{html.escape(k)} → {html.escape(v)}" for k, v in list(abbr_exp.items())[:5]]
            items_html += f'<div class="enrich-item"><span class="elbl">Expansions:</span><span class="eval">{", ".join(exp_parts)}</span></div>'
        sections.append(
            f'<div class="enrich-panel"><h2 class="interp">🧠 Smart Interpretation</h2>'
            f'<div class="enrich-grid">{items_html}</div></div>'
        )

    # --- Domain History ---
    history = analysis.get("history")
    if history and history.get("has_history"):
        h = history
        items_html = ""
        if h.get("first_seen"):
            items_html += f'<div class="enrich-item"><span class="elbl">First Seen:</span><span class="eval">{html.escape(str(h["first_seen"]))}</span></div>'
        if h.get("last_seen"):
            items_html += f'<div class="enrich-item"><span class="elbl">Last Seen:</span><span class="eval">{html.escape(str(h["last_seen"]))}</span></div>'
        items_html += f'<div class="enrich-item"><span class="elbl">Snapshots:</span><span class="eval">{h.get("total_snapshots", 0)}</span></div>'
        items_html += f'<div class="enrich-item"><span class="elbl">Years Active:</span><span class="eval">{h.get("years_active", 0)}</span></div>'
        if h.get("past_usage"):
            items_html += f'<div class="enrich-item"><span class="elbl">Past Usage:</span><span class="eval">{html.escape(h["past_usage"])}</span></div>'
        sections.append(
            f'<div class="enrich-panel"><h2 class="hist">📜 Domain History (Wayback Machine)</h2>'
            f'<div class="enrich-grid">{items_html}</div></div>'
        )

    # --- Social Handles ---
    social = analysis.get("social_handles")
    if social and social.get("handles"):
        handle_name = html.escape(social.get("handle", ""))
        pills = ""
        for h in social["handles"]:
            status = h.get("status", "unknown")
            cls = "handle-taken" if status == "taken" else "handle-avail" if status == "available" else "handle-unk"
            icon = "✓" if status == "taken" else "✗" if status == "available" else "?"
            pills += f'<span class="handle-pill {cls}">{icon} {html.escape(h["platform"])}</span>'
        summary = html.escape(social.get("summary", ""))
        sections.append(
            f'<div class="enrich-panel"><h2 class="social">📱 Social Handles — @{handle_name}</h2>'
            f'<div class="handle-grid">{pills}</div>'
            f'<p style="color:var(--muted);font-size:0.85rem;margin-top:0.75rem;">{summary}</p></div>'
        )

    # --- Market Comparables ---
    market = analysis.get("market_comp")
    if market and market.get("comparables"):
        rows = ""
        for c in market["comparables"][:8]:
            d = html.escape(c.get("domain", ""))
            p = c.get("price", 0)
            s = html.escape(c.get("source", ""))
            u = html.escape(c.get("url", ""))
            rows += f'<tr><td>{d}</td><td class="price">${p:,.0f}</td><td><a href="{u}" target="_blank">{s}</a></td></tr>'

        summary = html.escape(market.get("market_summary", ""))
        pr = market.get("price_range", {})
        range_html = ""
        if pr:
            range_html = (
                f'<p style="color:var(--green);font-size:0.95rem;font-weight:600;margin-bottom:0.5rem;">'
                f'${pr.get("low", 0):,.0f} — ${pr.get("high", 0):,.0f} '
                f'(median ${pr.get("median", 0):,.0f}, {pr.get("count", 0)} comps)</p>'
            )
        sections.append(
            f'<div class="enrich-panel"><h2 class="market">💰 Market Comparables</h2>'
            f'{range_html}'
            f'<table class="comp-table"><thead><tr><th>Domain</th><th>Price</th><th>Source</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>'
            f'<p style="color:var(--muted);font-size:0.85rem;margin-top:0.75rem;">{summary}</p></div>'
        )

    return "\n    ".join(sections)
