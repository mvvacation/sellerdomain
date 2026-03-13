"""Lead scoring module v3 — deep, multi-signal relevance scoring."""

import re
from difflib import SequenceMatcher

import tldextract

# TLD desirability tiers (lower = they'd want to upgrade more)
_TLD_TIER = {
    "com": 5, "org": 4, "net": 4,
    "co": 3, "io": 3, "ai": 4, "app": 3, "dev": 3,
    "tech": 2, "us": 2, "me": 2, "tv": 2,
    "xyz": 1, "info": 1, "biz": 1, "online": 1, "site": 1,
    "store": 2, "club": 1, "space": 1, "website": 1,
}

# Funding-related keywords in descriptions
_FUNDING_SIGNALS = re.compile(
    r"(?:series [a-e]|seed round|pre-seed|raised \$|funding|backed by|venture|investment|"
    r"yc\b|y combinator|techstars|500 startups|sequoia|andreessen|accel|"
    r"greylock|benchmark|kleiner|lightspeed|general catalyst|tiger global|"
    r"capital raise|ipo|valuation|unicorn|decacorn)",
    re.I,
)

# Rebranding / domain-buying intent signals
_REBRAND_SIGNALS = re.compile(
    r"(?:rebrand|relaunch|new identity|brand refresh|name change|acquiring domain|"
    r"looking for.*domain|domain acquisition|brand upgrade|digital transformation)",
    re.I,
)

# Growth signals
_GROWTH_SIGNALS = re.compile(
    r"(?:hiring|we.re growing|join our team|open positions|expanding|"
    r"new office|opened|launched|announcing|scaling|rapid growth|"
    r"went viral|million users|100k|growing fast|hypergrowth)",
    re.I,
)

# Company size keywords
_TEAM_SIZE_RE = re.compile(
    r"(\d{1,5})\+?\s*(?:employees?|team members?|people|staff|engineers?)", re.I
)


class LeadScorer:
    """Multi-signal relevance scorer with weighted categories."""

    # Weight allocation (total 100):
    #   Brand fit      : 28  (domain name / keyword alignment)
    #   Content match  : 18  (description and snippet relevance)
    #   Domain gap     : 18  (their domain is worse → upgrade signal)
    #   Discovery depth: 10  (appeared in many queries)
    #   Actionability  : 12  (contact info present)
    #   Buyer signals  : 14  (funded, growing, rebranding intent)

    def __init__(self, analysis):
        self.analysis = analysis
        self.domain_name = analysis["name"].lower()
        self.tld = analysis["tld"].lower()
        self.keywords = [k.lower() for k in analysis["keywords"]]
        self.industries = [i.lower() for i in analysis["industries"]]
        self.geo_targets = [g.lower() for g in analysis.get("geo_targets", [])]
        self.niche_context = analysis.get("niche_context", "")

    # ── Public API ────────────────────────────────────────────────

    def score_and_rank(self, leads):
        scored = []
        for lead in leads:
            breakdown = self._score_breakdown(lead)
            total = max(0, min(100, sum(breakdown.values())))
            lead["relevance_score"] = total
            lead["score_breakdown"] = breakdown
            lead["relevance_reasons"] = self._get_reasons(lead, breakdown)
            lead["buyer_type"] = self._classify_buyer(lead, breakdown)
            scored.append(lead)
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored

    # ── Score breakdown ───────────────────────────────────────────

    def _score_breakdown(self, lead):
        return {
            "brand_fit":       self._brand_fit(lead),
            "content_match":   self._content_match(lead),
            "domain_gap":      self._domain_gap(lead),
            "discovery_depth": self._discovery_depth(lead),
            "actionability":   self._actionability(lead),
            "buyer_signals":   self._buyer_signals(lead),
        }

    def _brand_fit(self, lead):
        """How well the lead's brand aligns with our domain. Max 28."""
        pts = 0
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()
        name_lower = lead.get("name", "").lower()

        # Exact domain name match
        if self.domain_name == cdomain:
            pts += 20
        elif self.domain_name in cdomain or cdomain in self.domain_name:
            ratio = SequenceMatcher(None, self.domain_name, cdomain).ratio()
            pts += int(ratio * 16)
        else:
            ratio = SequenceMatcher(None, self.domain_name, cdomain).ratio()
            if ratio >= 0.65:
                pts += int(ratio * 12)

        # Keyword presence in company name
        matched_kws = sum(1 for kw in self.keywords if kw in name_lower and len(kw) >= 3)
        pts += min(8, matched_kws * 4)

        return min(28, pts)

    def _content_match(self, lead):
        """How relevant the lead's content is to our domain. Max 18."""
        pts = 0
        text = " ".join([
            lead.get("title", ""), lead.get("snippet", ""),
            lead.get("description", ""), lead.get("location", ""),
        ]).lower()
        if not text.strip():
            return 0

        # Each keyword found in content (diminishing returns)
        kw_hits = 0
        for kw in self.keywords:
            if len(kw) < 3:
                continue
            if kw in text:
                kw_hits += 1
        if kw_hits >= len(self.keywords) and len(self.keywords) >= 2:
            pts += 10  # all keywords present — strong match
        elif kw_hits >= 2:
            pts += 7
        elif kw_hits >= 1:
            pts += 4

        # Industry match in content
        for ind in self.industries:
            if ind in text:
                pts += 3
                break

        # Geographic match — lead is in a detected geo target
        loc_clean = text.replace("'", "").replace("\u2019", "")
        for geo in self.geo_targets:
            geo_clean = geo.lower().replace("'", "").replace("\u2019", "")
            if geo_clean in loc_clean:
                pts += 4
                break

        return min(18, pts)

    def _domain_gap(self, lead):
        """How much worse their current domain is vs ours. Max 18."""
        pts = 0
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()
        ctld = ext.suffix.lower()
        our_tld_tier = _TLD_TIER.get(self.tld, 1)
        their_tld_tier = _TLD_TIER.get(ctld, 1)

        # Similar domain flag — strongest gap signal
        if lead.get("is_similar_domain"):
            pts += 10

        # TLD upgrade opportunity
        if our_tld_tier > their_tld_tier:
            pts += min(6, (our_tld_tier - their_tld_tier) * 2)

        # Length penalty — they have a longer domain
        len_diff = len(cdomain) - len(self.domain_name)
        if len_diff > 0:
            pts += min(5, len_diff)

        # Hyphenated domain — they might want a clean one
        if "-" in cdomain:
            pts += 3

        # Their domain has numbers
        if re.search(r"\d", cdomain):
            pts += 2

        # Both are short .com → small upgrade gap
        if len(cdomain) <= 4 and ctld == "com" and self.tld == "com" and not lead.get("is_similar_domain"):
            pts -= 2

        return max(0, min(18, pts))

    def _discovery_depth(self, lead):
        """How many different queries surfaced this lead. Max 10."""
        n = len(lead.get("matched_queries", []))
        if n >= 6:
            return 10
        if n >= 4:
            return 8
        if n >= 3:
            return 6
        if n >= 2:
            return 4
        return 1

    def _actionability(self, lead):
        """How easy it is to contact them. Max 12."""
        pts = 0
        if lead.get("emails"):
            pts += 4
            # Extra for a matching-domain email (not generic gmail)
            for e in lead["emails"]:
                edomain = e.split("@")[-1].lower()
                if edomain == lead.get("website_domain", "").lower():
                    pts += 2
                    break
        if lead.get("phone"):
            pts += 3
        social = lead.get("social", {})
        if social.get("linkedin"):
            pts += 2
        if social.get("twitter") or social.get("facebook"):
            pts += 1
        return min(12, pts)

    def _buyer_signals(self, lead):
        """Indirect buying-intent signals. Max 14."""
        pts = 0
        text = " ".join([
            lead.get("title", ""), lead.get("snippet", ""),
            lead.get("description", ""),
        ]).lower()

        # Funded startup → has money to spend
        if _FUNDING_SIGNALS.search(text):
            pts += 4

        # Rebrand / domain acquisition intent — strongest signal
        if _REBRAND_SIGNALS.search(text):
            pts += 5

        # Active growth → brand investment phase
        if _GROWTH_SIGNALS.search(text):
            pts += 2

        # Team growing → brand investment phase
        m = _TEAM_SIZE_RE.search(text)
        if m:
            size = int(m.group(1))
            if 10 <= size <= 500:
                pts += 2  # mid-size = sweet spot for domain buying
            elif size > 500:
                pts += 1  # large companies still buy but less urgently

        # Technology investment signals — modern stack = higher budget
        techs = {t.lower() for t in lead.get("technologies", [])}
        modern = {"react", "vue.js", "next.js", "angular", "graphql", "kubernetes", "webflow"}
        if techs & modern:
            pts += 3
        elif len(techs) >= 3:
            pts += 1

        # Location present (established company)
        if lead.get("location"):
            pts += 1

        return min(14, pts)

    # ── Buyer classification ──────────────────────────────────────

    def _classify_buyer(self, lead, breakdown):
        score = lead["relevance_score"]
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()

        if lead.get("is_similar_domain"):
            return "similar_domain"
        if self.domain_name == cdomain:
            return "exact_match"
        if breakdown["brand_fit"] >= 18 and breakdown["domain_gap"] >= 10:
            return "strong_upgrade"
        if breakdown["buyer_signals"] >= 9:
            return "rebrand_candidate"
        if breakdown["buyer_signals"] >= 5:
            return "funded_startup"
        if breakdown["brand_fit"] >= 12 and score >= 55:
            return "brand_match"
        if score >= 60:
            return "high_relevance"
        if score >= 40:
            return "moderate_relevance"
        return "general"

    # ── Reasons ───────────────────────────────────────────────────

    def _get_reasons(self, lead, breakdown):
        reasons = []
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()
        ctld = ext.suffix
        name_lower = lead.get("name", "").lower()
        text = " ".join([
            lead.get("title", ""), lead.get("snippet", ""),
            lead.get("description", ""),
        ]).lower()

        # Brand fit reasons
        if self.domain_name == cdomain:
            reasons.append("Exact domain name match — they likely want this domain")
        elif self.domain_name in cdomain:
            reasons.append(f"Their domain contains '{self.domain_name}'")
        elif cdomain in self.domain_name and len(cdomain) >= 3:
            reasons.append(f"Your domain contains their brand '{cdomain}'")

        matching_kws = [kw for kw in self.keywords if kw in name_lower and len(kw) >= 3]
        if matching_kws:
            reasons.append(f"Company name matches keywords: {', '.join(matching_kws)}")

        # Domain gap reasons
        if lead.get("is_similar_domain"):
            reasons.append(f"Owns similar domain ({lead.get('website_domain', '')})")
        if len(cdomain) > len(self.domain_name) + 2:
            reasons.append("Currently uses a longer domain — upgrade opportunity")
        if "-" in cdomain:
            reasons.append("Hyphenated domain — may want a cleaner brand")
        if ctld not in ("com", "org", "net") and self.tld == "com":
            reasons.append(f"Currently on .{ctld} — may want .com upgrade")

        # Buyer signals
        if _REBRAND_SIGNALS.search(text):
            reasons.append("Shows rebranding or domain acquisition intent")
        if _FUNDING_SIGNALS.search(text):
            reasons.append("Recently funded — has budget for brand investment")
        if _GROWTH_SIGNALS.search(text):
            reasons.append("Growing company — investing in brand presence")
        m = _TEAM_SIZE_RE.search(text)
        if m:
            reasons.append(f"Established team (~{m.group(1)} employees)")

        # Content relevance
        if breakdown.get("content_match", 0) >= 10:
            reasons.append("Strong keyword overlap in their content")

        # Geo-match reasons
        loc = (lead.get("location", "") + " " + text).lower()
        # Strip apostrophes for flexible matching (Martha's vs Marthas, etc.)
        loc_clean = loc.replace("'", "").replace("\u2019", "")
        for geo in self.geo_targets:
            geo_clean = geo.replace("'", "").replace("\u2019", "")
            if geo_clean in loc_clean:
                reasons.append(f"Located in / operates in {geo} \u2014 matches domain niche")
                break

        # Actionability
        if lead.get("emails"):
            on_domain = any(e.split("@")[-1].lower() == lead.get("website_domain", "").lower()
                            for e in lead["emails"])
            if on_domain:
                reasons.append("Direct company email available")

        if not reasons:
            reasons.append("Operates in a related industry")

        return reasons
