"""Lead scoring module v4 — relevance-first scoring.

Relevance is king. A lead's score is dominated by how closely their brand,
content, and industry match the domain being sold. Secondary signals
(funding, contact info, tech stack) are tie-breakers, not score inflators.
"""

import re
from difflib import SequenceMatcher

import tldextract

# TLD desirability tiers (lower = they'd want to upgrade more)
_TLD_TIER = {
    "com": 5,
    "org": 4,
    "net": 4,
    "co": 3,
    "io": 3,
    "ai": 4,
    "app": 3,
    "dev": 3,
    "tech": 2,
    "us": 2,
    "me": 2,
    "tv": 2,
    "xyz": 1,
    "info": 1,
    "biz": 1,
    "online": 1,
    "site": 1,
    "store": 2,
    "club": 1,
    "space": 1,
    "website": 1,
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
_TEAM_SIZE_RE = re.compile(r"(\d{1,5})\+?\s*(?:employees?|team members?|people|staff|engineers?)", re.I)


class LeadScorer:
    """Relevance-first scorer. Irrelevant leads get crushed, relevant ones shine.

    Weight allocation (total 100):
      Brand fit      : 40  (domain name / keyword alignment — THE key signal)
      Content match  : 25  (description, snippet, industry relevance)
      Domain gap     : 12  (their domain is worse → upgrade motivation)
      Discovery depth:  8  (appeared in many queries → cross-validated)
      Buyer signals  : 10  (funded, growing, rebranding intent)
      Actionability  :  5  (contact info — useful but not a relevance signal)

    PENALTY: leads with zero brand_fit AND zero content_match get -15.
    This ensures random companies that just happen to be funded or have
    contact info don't pollute the results.
    """

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
        brand = self._brand_fit(lead)
        content = self._content_match(lead)
        gap = self._domain_gap(lead)
        depth = self._discovery_depth(lead)
        signals = self._buyer_signals(lead)
        action = self._actionability(lead)

        # PENALTY: if the lead has NO brand fit AND NO content match,
        # it's almost certainly irrelevant noise. Penalize heavily.
        penalty = 0
        if brand == 0 and content == 0:
            penalty = -15

        return {
            "brand_fit": brand,
            "content_match": content,
            "domain_gap": gap,
            "discovery_depth": depth,
            "buyer_signals": signals,
            "actionability": action,
            "relevance_penalty": penalty,
        }

    def _brand_fit(self, lead):
        """How well the lead's brand aligns with our domain. Max 40."""
        pts = 0
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()
        name_lower = lead.get("name", "").lower()

        # Exact domain name match — perfect fit
        if self.domain_name == cdomain:
            pts += 30
        elif self.domain_name in cdomain or cdomain in self.domain_name:
            # Substring match: "seller" in "sellerdomain" or vice versa
            overlap = min(len(self.domain_name), len(cdomain))
            longer = max(len(self.domain_name), len(cdomain))
            ratio = overlap / longer if longer > 0 else 0
            pts += int(ratio * 24)
        else:
            ratio = SequenceMatcher(None, self.domain_name, cdomain).ratio()
            if ratio >= 0.75:
                pts += int(ratio * 18)
            elif ratio >= 0.6:
                pts += int(ratio * 10)
            # Below 0.6 similarity → no brand fit points

        # Keyword presence in company name — strong relevance signal
        matched_kws = sum(1 for kw in self.keywords if kw in name_lower and len(kw) >= 3)
        if matched_kws >= 3:
            pts += 12
        elif matched_kws >= 2:
            pts += 8
        elif matched_kws >= 1:
            pts += 5

        # Keyword presence in their domain name
        domain_kw_hits = sum(1 for kw in self.keywords if kw in cdomain and len(kw) >= 3)
        if domain_kw_hits >= 1:
            pts += 4

        return min(40, pts)

    def _content_match(self, lead):
        """How relevant the lead's content is to our domain. Max 25."""
        pts = 0
        text = " ".join(
            [
                lead.get("title", ""),
                lead.get("snippet", ""),
                lead.get("description", ""),
                lead.get("location", ""),
            ]
        ).lower()
        if not text.strip():
            return 0

        # Keyword density in content
        kw_hits = 0
        for kw in self.keywords:
            if len(kw) < 3:
                continue
            if kw in text:
                kw_hits += 1
        if kw_hits >= len(self.keywords) and len(self.keywords) >= 2:
            pts += 14  # all keywords present — very strong match
        elif kw_hits >= 2:
            pts += 9
        elif kw_hits >= 1:
            pts += 5

        # Industry match in content
        ind_hits = sum(1 for ind in self.industries if ind in text)
        if ind_hits >= 2:
            pts += 6
        elif ind_hits >= 1:
            pts += 4

        # Geographic match — lead is in a detected geo target
        loc_clean = text.replace("'", "").replace("\u2019", "")
        for geo in self.geo_targets:
            geo_clean = geo.lower().replace("'", "").replace("\u2019", "")
            if geo_clean in loc_clean:
                pts += 5
                break

        return min(25, pts)

    def _domain_gap(self, lead):
        """How much worse their current domain is vs ours. Max 12."""
        pts = 0
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()
        ctld = ext.suffix.lower()
        our_tld_tier = _TLD_TIER.get(self.tld, 1)
        their_tld_tier = _TLD_TIER.get(ctld, 1)

        # Similar domain flag — strongest gap signal
        if lead.get("is_similar_domain"):
            pts += 7

        # TLD upgrade opportunity
        if our_tld_tier > their_tld_tier:
            pts += min(4, (our_tld_tier - their_tld_tier) * 2)

        # Length penalty — they have a longer domain
        len_diff = len(cdomain) - len(self.domain_name)
        if len_diff > 2:
            pts += min(3, len_diff - 1)

        # Hyphenated domain — they might want a clean one
        if "-" in cdomain:
            pts += 2

        # Their domain has numbers
        if re.search(r"\d", cdomain):
            pts += 1

        # Both are short .com → small upgrade gap
        if len(cdomain) <= 4 and ctld == "com" and self.tld == "com" and not lead.get("is_similar_domain"):
            pts -= 2

        return max(0, min(12, pts))

    def _discovery_depth(self, lead):
        """How many different queries surfaced this lead. Max 8."""
        n = len(lead.get("matched_queries", []))
        if n >= 5:
            return 8
        if n >= 4:
            return 6
        if n >= 3:
            return 5
        if n >= 2:
            return 3
        return 0  # single query hit = no depth bonus

    def _actionability(self, lead):
        """How easy it is to contact them. Max 5. (Tie-breaker only.)"""
        pts = 0
        if lead.get("emails"):
            pts += 2
            # Extra for a matching-domain email (not generic gmail)
            for e in lead["emails"]:
                edomain = e.split("@")[-1].lower()
                if edomain == lead.get("website_domain", "").lower():
                    pts += 1
                    break
        if lead.get("phone"):
            pts += 1
        social = lead.get("social", {})
        if social.get("linkedin"):
            pts += 1
        return min(5, pts)

    def _buyer_signals(self, lead):
        """Indirect buying-intent signals. Max 10."""
        pts = 0
        text = " ".join(
            [
                lead.get("title", ""),
                lead.get("snippet", ""),
                lead.get("description", ""),
            ]
        ).lower()

        # Rebrand / domain acquisition intent — strongest signal
        if _REBRAND_SIGNALS.search(text):
            pts += 4

        # Funded startup → has money to spend
        if _FUNDING_SIGNALS.search(text):
            pts += 3

        # Active growth → brand investment phase
        if _GROWTH_SIGNALS.search(text):
            pts += 2

        # Team size
        m = _TEAM_SIZE_RE.search(text)
        if m:
            size = int(m.group(1))
            if 10 <= size <= 500:
                pts += 1  # mid-size = sweet spot

        return min(10, pts)

    # ── Buyer classification ──────────────────────────────────────

    def _classify_buyer(self, lead, breakdown):
        score = lead["relevance_score"]
        ext = tldextract.extract(lead.get("website_domain", ""))
        cdomain = ext.domain.lower()

        if lead.get("is_similar_domain"):
            return "similar_domain"
        if self.domain_name == cdomain:
            return "exact_match"
        if breakdown["brand_fit"] >= 25 and breakdown["domain_gap"] >= 6:
            return "strong_upgrade"
        if breakdown["buyer_signals"] >= 7:
            return "rebrand_candidate"
        if breakdown["brand_fit"] >= 20 and score >= 60:
            return "brand_match"
        if breakdown["buyer_signals"] >= 4 and breakdown["brand_fit"] >= 10:
            return "funded_startup"
        if score >= 55:
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
        text = " ".join(
            [
                lead.get("title", ""),
                lead.get("snippet", ""),
                lead.get("description", ""),
            ]
        ).lower()

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
        if breakdown.get("content_match", 0) >= 12:
            reasons.append("Strong keyword and industry overlap in their content")
        elif breakdown.get("content_match", 0) >= 7:
            reasons.append("Good keyword overlap in their content")

        # Geo-match reasons
        loc = (lead.get("location", "") + " " + text).lower()
        loc_clean = loc.replace("'", "").replace("\u2019", "")
        for geo in self.geo_targets:
            geo_clean = geo.replace("'", "").replace("\u2019", "")
            if geo_clean in loc_clean:
                reasons.append(f"Located in / operates in {geo} \u2014 matches domain niche")
                break

        # Actionability
        if lead.get("emails"):
            on_domain = any(e.split("@")[-1].lower() == lead.get("website_domain", "").lower() for e in lead["emails"])
            if on_domain:
                reasons.append("Direct company email available")

        if not reasons:
            reasons.append("Operates in a related industry")

        return reasons
