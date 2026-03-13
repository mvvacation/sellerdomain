"""Outreach module - generates personalized, data-driven email templates for contacting potential buyers."""


def generate_outreach_email(lead, analysis, template_type="auto"):
    """Generate a personalized outreach email for a lead."""
    domain = analysis["domain"]
    value_low = analysis.get("estimated_value_low", 0)
    value_high = analysis.get("estimated_value_high", 0)
    keywords = analysis.get("keywords", [])
    company_name = lead.get("name", "the team")

    reason = _build_natural_reason(lead, analysis)
    selling_points = _build_selling_points(analysis, lead)
    data_points = _build_data_points(lead, analysis)

    generators = {
        "standard": _standard_template,
        "premium": _premium_template,
        "startup": _startup_template,
        "similar_domain": _similar_domain_template,
        "upgrade": _upgrade_template,
    }

    # Auto-select template based on buyer type / score
    if template_type == "auto":
        buyer_type = lead.get("buyer_type", "general")
        if buyer_type in ("similar_domain", "exact_match"):
            template_type = "similar_domain"
        elif buyer_type == "strong_upgrade":
            template_type = "upgrade"
        elif buyer_type in ("funded_startup", "rebrand_candidate"):
            template_type = "startup"
        elif buyer_type == "brand_match" or lead.get("relevance_score", 0) >= 70:
            template_type = "premium"
        else:
            template_type = "standard"

    generator = generators.get(template_type, _standard_template)
    return generator(domain, company_name, keywords, reason, value_low, value_high,
                     selling_points, data_points)


def _build_natural_reason(lead, analysis):
    """Build a natural-sounding reason for why we're reaching out."""
    import tldextract
    website_domain = lead.get("website_domain", "")
    ext = tldextract.extract(website_domain)
    company_domain_name = ext.domain.lower()
    domain_name = analysis["name"].lower()
    keywords = analysis.get("keywords", [])

    if domain_name == company_domain_name:
        current_tld = ext.suffix
        return f"your company currently operates under {website_domain}, and {analysis['domain']} could strengthen and consolidate your online brand"
    elif domain_name in company_domain_name:
        return f"your brand name closely aligns with {analysis['domain']} — it's a natural brand asset"
    elif lead.get("is_similar_domain"):
        return f"you already own {website_domain}, and {analysis['domain']} would complement your domain portfolio"
    elif any(kw in lead.get("name", "").lower() for kw in keywords if len(kw) >= 3):
        matching = [kw for kw in keywords if len(kw) >= 3 and kw in lead.get("name", "").lower()]
        return f"your company's focus on {', '.join(matching)} is a perfect match for this domain"
    else:
        # Use relevance reasons if available
        reasons = lead.get("relevance_reasons", [])
        if reasons:
            return reasons[0].lower().rstrip(".")
        # Contextual fallbacks
        techs = lead.get("technologies", [])
        if techs:
            return f"your modern tech stack ({', '.join(techs[:2])}) signals a brand that's investing in growth"
        location = lead.get("location", "")
        if location and analysis.get("industries"):
            ind = analysis["industries"][0].replace("_", " ")
            return f"you're a {location}-based leader in the {ind} space"
        if analysis.get("industries") and analysis["industries"][0] != "general":
            ind = analysis["industries"][0].replace("_", " ")
            return f"your focus on {ind} aligns perfectly with what this domain represents"
        return "your company operates in a space where this domain could drive real value"


def _build_selling_points(analysis, lead=None):
    """Build extra selling points from enrichment data."""
    points = []

    # Domain history
    history = analysis.get("history", {})
    if history.get("has_history"):
        years = history.get("years_active", 0)
        if years >= 10:
            points.append(f"Domain has {years}+ years of web history — established trust and residual SEO authority")
        elif years >= 5:
            points.append(f"Active domain history spanning {years}+ years")

    # Social handles
    social = analysis.get("social_handles", {})
    taken = social.get("taken_count", 0)
    if taken >= 5:
        points.append(f"Brand name @{social.get('handle','')} is claimed on {taken}/7 major platforms — proven brand demand")
    elif taken >= 3:
        points.append(f"Matching social handles active on {taken} platforms — established brand identity")

    # Market comparables
    market = analysis.get("market_comp", {})
    pr = market.get("price_range")
    if pr and pr.get("median", 0) > 0:
        points.append(f"Comparable domains in this space trade at ${pr['median']:,.0f} median")

    # Brandability
    brand = analysis.get("brandability", {})
    if brand.get("score", 0) >= 70:
        points.append(f"Brandability score: {brand['score']}/100 ({brand.get('grade','')}) — top-tier naming")

    # Geo niche
    niche = analysis.get("niche_context", "")
    geo = analysis.get("geo_targets", [])
    if niche:
        points.append(f"Strong niche positioning: {niche}")
    elif geo:
        points.append(f"Geographic relevance: {', '.join(geo[:3])}")

    return points


def _build_data_points(lead, analysis):
    """Build specific data points about why this lead is a fit."""
    points = []
    domain = analysis["domain"]
    website = lead.get("website_domain", "")

    if lead.get("is_similar_domain") and website:
        points.append(f"You own {website} — {domain} is the natural upgrade")
    if len(analysis.get("name", "")) <= 6:
        points.append(f"At just {len(analysis['name'])} characters, {domain} is concise and instantly memorable")
    if analysis.get("domain_age_years", 0) >= 5:
        points.append(f"Registered for {analysis['domain_age_years']}+ years — carries domain authority")

    reasons = lead.get("relevance_reasons", [])
    for r in reasons[:2]:
        if r not in points and "industry" not in r.lower():
            points.append(r)

    return points[:4]


def _standard_template(domain, company, keywords, reason, val_low, val_high, selling_points=None, data_points=None):
    kw_text = ", ".join(keywords[:3]) if keywords else "your industry"
    bullets = ""
    if data_points:
        bullets = "\n".join(f"  \u2022 {p}" for p in data_points)
        bullets = f"\nWhy this makes sense:\n{bullets}\n"
    extra = ""
    if selling_points:
        extra = "\n" + "\n".join(f"\u2022 {p}" for p in selling_points) + "\n"

    return {
        "subject": f"{domain} — quick question before I list it",
        "body": f"""Hi {company} team,

I noticed {reason}. I own {domain} and wanted to see if it might be a good fit for your brand before I list it publicly.

A strong domain in the {kw_text} space can make a real difference — shorter URLs, better recall, and more credibility with customers.
{bullets}
Key highlights:
\u2022 Short, memorable, and easy to type
\u2022 Aligns directly with your market positioning
\u2022 Builds trust and boosts SEO from day one{extra}
I'm flexible on terms and happy to discuss. Would a quick call this week work?

Best regards""",
    }


def _premium_template(domain, company, keywords, reason, val_low, val_high, selling_points=None, data_points=None):
    kw_text = ", ".join(keywords[:3]) if keywords else "your industry"
    bullets = ""
    if data_points:
        bullets = "\n".join(f"  \u2022 {p}" for p in data_points)
        bullets = f"\nSpecifically:\n{bullets}\n"
    extra = ""
    if selling_points:
        extra = "\n\n" + "\n".join(f"\u2022 {p}" for p in selling_points)

    return {
        "subject": f"{domain} \u2014 before it goes to market",
        "body": f"""Dear {company} team,

I'm reaching out because {reason}.

I own {domain} \u2014 a premium domain that I believe could be a significant strategic asset for your brand. In the {kw_text} space, the right domain name is often the difference between a customer remembering your brand or not.
{bullets}
What makes {domain} valuable:
\u2022 Instantly recognizable \u2014 no spelling ambiguity, no hyphens
\u2022 Keyword-rich for natural search visibility
\u2022 Positions you as the category leader
\u2022 A permanent asset that appreciates over time{extra}

I'm reaching out to a small group of companies where the strategic fit is strongest. I'd welcome a conversation before listing this publicly.

Would you be open to a brief call?

Best regards""",
    }


def _startup_template(domain, company, keywords, reason, val_low, val_high, selling_points=None, data_points=None):
    kw_text = ", ".join(keywords[:3]) if keywords else "your space"
    bullets = ""
    if data_points:
        bullets = "\n".join(f"  \u2022 {p}" for p in data_points)
        bullets = f"\n{bullets}\n"
    extra = ""
    if selling_points:
        extra = "\n" + "\n".join(f"\u2022 {p}" for p in selling_points) + "\n"

    return {
        "subject": f"{company} + {domain} — a natural fit",
        "body": f"""Hi {company} team,

Congrats on the momentum \u2014 I noticed {reason}.

As you scale in the {kw_text} space, your domain name becomes part of your brand equity. I own {domain} and think it could accelerate your growth:

\u2022 Easier brand recall = lower customer acquisition costs
\u2022 Premium domain = instant credibility with investors and partners
\u2022 Direct-type traffic from customers searching for your category
\u2022 Long-term SEO foundation that compounds over time
{bullets}{extra}
I know budgets are tight at growth stage \u2014 I'm open to flexible terms (installments, lease-to-own, etc.). The goal is to find the right home for this domain.

Worth a quick conversation?

Best regards""",
    }


def _similar_domain_template(domain, company, keywords, reason, val_low, val_high, selling_points=None, data_points=None):
    bullets = ""
    if data_points:
        bullets = "\n".join(f"  \u2022 {p}" for p in data_points)
        bullets = f"\n{bullets}\n"
    extra = ""
    if selling_points:
        extra = "\n" + "\n".join(f"\u2022 {p}" for p in selling_points) + "\n"

    return {
        "subject": f"Consolidate your brand \u2014 {domain} is available",
        "body": f"""Hi {company} team,

I noticed {reason}. I own {domain} and thought you should know it's available before I list it on the open market.

Owning {domain} would let you:
\u2022 Unify your online presence under one strong brand
\u2022 Capture direct-type traffic you may be missing
\u2022 Prevent a competitor from acquiring it
\u2022 Simplify your marketing across channels
{bullets}{extra}
Given the natural overlap, I wanted to reach out directly. I think this makes more sense in your hands than anyone else's.

Would you be interested in a quick conversation?

Best regards""",
    }


def _upgrade_template(domain, company, keywords, reason, val_low, val_high, selling_points=None, data_points=None):
    kw_text = ", ".join(keywords[:3]) if keywords else "your industry"
    bullets = ""
    if data_points:
        bullets = "\n".join(f"  \u2022 {p}" for p in data_points)
        bullets = f"\n{bullets}\n"
    extra = ""
    if selling_points:
        extra = "\n" + "\n".join(f"\u2022 {p}" for p in selling_points) + "\n"

    return {
        "subject": f"Upgrade opportunity: {domain}",
        "body": f"""Hi {company} team,

I noticed {reason}. A shorter, cleaner domain in the {kw_text} space could give your brand an immediate edge.

{domain} is available, and here's why it matters:
\u2022 Customers remember shorter domains \u2014 more word-of-mouth referrals
\u2022 Cleaner brand identity across print, social, and digital
\u2022 Signals market leadership to customers and partners
\u2022 One-time investment that pays dividends for years
{bullets}{extra}
I'm reaching out because the fit is strong \u2014 I'd rather see this domain with a company that can put it to work.

Open to a brief call this week?

Best regards""",
    }


def generate_all_templates(lead, analysis):
    """Generate all template variants for a lead."""
    templates = {}
    for ttype in ["standard", "premium", "startup", "similar_domain", "upgrade"]:
        templates[ttype] = generate_outreach_email(lead, analysis, ttype)
    return templates
