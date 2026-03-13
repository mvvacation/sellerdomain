"""Domain analysis module - WHOIS, DNS, keyword extraction, industry classification, valuation, brandability."""

import re
from datetime import datetime

import dns.resolver
import tldextract
import wordninja

from core.abbreviations import expand_abbreviations

try:
    import whois
except ImportError:
    whois = None


# Industry keyword mappings for classification
INDUSTRY_KEYWORDS = {
    "technology": [
        "tech", "soft", "code", "dev", "app", "cloud", "data", "ai",
        "cyber", "net", "web", "digital", "byte", "pixel", "sys", "comp",
        "logic", "algo", "stack", "hub", "sync", "meta", "quantum", "bot",
        "auto", "smart", "intel", "micro", "nano", "robot",
    ],
    "health": [
        "health", "med", "care", "fit", "well", "bio", "pharma", "doc",
        "clinic", "vita", "heal", "cure", "body", "mind", "therapy",
        "nurse", "dental", "cardio", "neuro", "genetic",
    ],
    "finance": [
        "fin", "pay", "bank", "money", "cash", "fund", "invest", "trade",
        "wealth", "credit", "loan", "capital", "stock", "crypto", "coin",
        "wallet", "insure", "tax", "audit", "profit",
    ],
    "education": [
        "edu", "learn", "teach", "school", "academy", "tutor", "course",
        "study", "train", "skill", "class", "mentor", "exam", "quiz",
        "degree", "campus", "lecture",
    ],
    "ecommerce": [
        "shop", "store", "buy", "sell", "deal", "market", "cart", "commerce",
        "retail", "mall", "outlet", "merch", "goods", "product", "price",
        "order", "ship", "deliver",
    ],
    "travel": [
        "travel", "trip", "tour", "fly", "hotel", "stay", "book", "journey",
        "voyage", "destination", "cruise", "resort", "vacation", "hostel",
        "flight", "passport",
    ],
    "food": [
        "food", "eat", "cook", "recipe", "meal", "chef", "kitchen", "dine",
        "taste", "fresh", "organic", "grill", "bake", "brew", "cafe",
        "restaurant", "vegan", "nutrition",
    ],
    "real_estate": [
        "home", "house", "property", "real", "estate", "rent", "land",
        "build", "construct", "apart", "condo", "mortgage", "realty",
        "lease", "tenant", "landlord",
    ],
    "marketing": [
        "brand", "market", "promo", "social", "media", "seo", "content",
        "viral", "growth", "campaign", "engage", "influence", "creative",
        "design", "agency",
    ],
    "gaming": [
        "game", "play", "quest", "level", "score", "gamer", "esport",
        "arcade", "rpg", "console", "stream", "twitch", "guild", "clan",
    ],
    "automotive": [
        "auto", "car", "drive", "motor", "vehicle", "ride", "fleet",
        "wheel", "gear", "engine", "speed", "turbo", "electric", "ev",
    ],
    "energy": [
        "energy", "solar", "wind", "power", "green", "eco", "sustain",
        "clean", "volt", "watt", "battery", "fuel", "renew", "carbon",
    ],
    "security": [
        "secure", "guard", "protect", "safe", "shield", "lock", "defend",
        "firewall", "encrypt", "vault", "alarm", "surveil", "monitor",
    ],
    "logistics": [
        "ship", "freight", "cargo", "deliver", "supply", "chain", "ware",
        "fleet", "track", "route", "dispatch", "port", "dock", "haul",
    ],
}

# TLD value multipliers
TLD_VALUES = {
    "com": 1.0, "net": 0.55, "org": 0.45, "io": 0.65, "co": 0.55,
    "ai": 0.80, "app": 0.45, "dev": 0.45, "xyz": 0.20, "info": 0.20,
    "biz": 0.20, "us": 0.30, "me": 0.30, "tv": 0.35, "cc": 0.25,
    "tech": 0.35, "online": 0.20, "site": 0.15, "store": 0.25,
}

# TLD → industry intelligence (new gTLDs carry strong niche signal)
TLD_INDUSTRY_MAP = {
    "tech": "technology", "dev": "technology", "app": "technology",
    "io": "technology", "ai": "technology", "code": "technology",
    "software": "technology", "cloud": "technology", "digital": "technology",
    "health": "health", "medical": "health", "clinic": "health",
    "dental": "health", "fitness": "health", "yoga": "health",
    "finance": "finance", "money": "finance", "bank": "finance",
    "insurance": "finance", "tax": "finance", "credit": "finance",
    "edu": "education", "academy": "education", "school": "education",
    "training": "education", "courses": "education",
    "shop": "ecommerce", "store": "ecommerce", "buy": "ecommerce",
    "market": "ecommerce", "deals": "ecommerce", "sale": "ecommerce",
    "travel": "travel", "holiday": "travel", "hotel": "travel",
    "flights": "travel", "tours": "travel", "vacations": "travel",
    "restaurant": "food", "recipes": "food", "cafe": "food",
    "catering": "food", "pizza": "food", "wine": "food", "beer": "food",
    "realty": "real_estate", "properties": "real_estate", "homes": "real_estate",
    "apartments": "real_estate", "house": "real_estate", "land": "real_estate",
    "agency": "marketing", "design": "marketing", "studio": "marketing",
    "media": "marketing", "marketing": "marketing", "social": "marketing",
    "games": "gaming", "game": "gaming",
    "auto": "automotive", "cars": "automotive", "car": "automotive",
    "energy": "energy", "solar": "energy", "green": "energy", "eco": "energy",
    "security": "security",
    "logistics": "logistics", "delivery": "logistics", "express": "logistics",
    # Country code TLDs → geographic signal
    "us": "geo:United States", "uk": "geo:United Kingdom", "co.uk": "geo:United Kingdom",
    "ca": "geo:Canada", "au": "geo:Australia", "de": "geo:Germany",
    "fr": "geo:France", "nl": "geo:Netherlands", "jp": "geo:Japan",
    "in": "geo:India", "br": "geo:Brazil", "mx": "geo:Mexico",
    "es": "geo:Spain", "it": "geo:Italy", "se": "geo:Sweden",
    "no": "geo:Norway", "dk": "geo:Denmark", "fi": "geo:Finland",
    "nz": "geo:New Zealand", "ie": "geo:Ireland", "sg": "geo:Singapore",
    "hk": "geo:Hong Kong", "kr": "geo:South Korea",
}


class DomainAnalyzer:
    """Analyzes a domain name to extract keywords, WHOIS, DNS, and estimate value."""

    def __init__(self, domain):
        self.domain = domain.lower().strip()
        self.extracted = tldextract.extract(self.domain)
        self.name = self.extracted.domain
        self.tld = self.extracted.suffix
        self.keywords = []
        self.industries = []
        self.whois_data = None
        self.dns_records = {}
        self.is_registered = False
        self.domain_age_years = 0
        self.estimated_value_low = 0
        self.estimated_value_high = 0

    def analyze(self):
        """Run full domain analysis. Returns analysis dict."""
        self._extract_keywords()
        self._expand_abbreviations()
        self._identify_industries()
        self._check_whois()
        self._check_dns()
        self._estimate_value()
        brand = self._assess_brandability()

        # TLD intelligence
        tld_industry = TLD_INDUSTRY_MAP.get(self.tld, "")
        tld_geo = ""
        if tld_industry.startswith("geo:"):
            tld_geo = tld_industry[4:]
            tld_industry = ""

        return {
            "domain": self.domain,
            "name": self.name,
            "tld": self.tld,
            "keywords": self.keywords,
            "industries": self.industries,
            "whois": self._format_whois(),
            "dns": self.dns_records,
            "is_registered": self.is_registered,
            "domain_age_years": self.domain_age_years,
            "estimated_value_low": self.estimated_value_low,
            "estimated_value_high": self.estimated_value_high,
            "brandability": brand,
            "interpretations": self.abbrev_data.get("interpretations", []),
            "geo_targets": self.abbrev_data.get("geo_targets", []),
            "niche_context": self.abbrev_data.get("niche_context", ""),
            "search_phrases": self.abbrev_data.get("search_phrases", []),
            "expanded_keywords": self.abbrev_data.get("expanded_keywords", []),
            "tld_industry": tld_industry,
            "tld_geo": tld_geo,
        }

    def _extract_keywords(self):
        """Extract meaningful keywords from the domain name using word segmentation."""
        words = wordninja.split(self.name)
        # Keep words with 2+ characters
        self.keywords = [w.lower() for w in words if len(w) >= 2]
        if not self.keywords:
            self.keywords = [self.name]

    def _expand_abbreviations(self):
        """Expand any abbreviations/acronyms found in keywords using smart mapping."""
        self.abbrev_data = expand_abbreviations(self.keywords, self.name)
        # Enrich keywords with expanded terms for better industry matching
        if self.abbrev_data["expanded_keywords"]:
            self.keywords = self.abbrev_data["expanded_keywords"]

    def _identify_industries(self):
        """Identify industries matching the domain keywords and TLD."""
        name_lower = self.name.lower()
        scores = {}

        for industry, terms in INDUSTRY_KEYWORDS.items():
            score = 0
            for term in terms:
                # Check if term appears in full domain name
                if term in name_lower:
                    score += len(term) * 2
                # Check if term matches any extracted keyword
                for kw in self.keywords:
                    if term == kw:
                        score += 5
                    elif term in kw or kw in term:
                        score += 2
            if score > 0:
                scores[industry] = score

        # TLD industry boost — strong niche signal from new gTLDs
        tld_ind = TLD_INDUSTRY_MAP.get(self.tld, "")
        if tld_ind and not tld_ind.startswith("geo:"):
            scores[tld_ind] = scores.get(tld_ind, 0) + 15

        sorted_industries = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        self.industries = [ind for ind, _ in sorted_industries[:3]]

        if not self.industries:
            self.industries = ["general"]

    def _check_whois(self):
        """Look up WHOIS data for the domain."""
        if whois is None:
            return
        try:
            self.whois_data = whois.whois(self.domain)
            self.is_registered = bool(self.whois_data.domain_name)
            # Calculate age
            creation = getattr(self.whois_data, "creation_date", None)
            if creation:
                if isinstance(creation, list):
                    creation = creation[0]
                if hasattr(creation, "year"):
                    self.domain_age_years = datetime.now().year - creation.year
        except Exception:
            self.whois_data = None
            self.is_registered = False

    def _check_dns(self):
        """Check DNS records."""
        for rtype in ["A", "MX", "NS"]:
            try:
                answers = dns.resolver.resolve(self.domain, rtype)
                self.dns_records[rtype] = [str(r) for r in answers]
            except Exception:
                self.dns_records[rtype] = []

    def _format_whois(self):
        """Format WHOIS data into a clean dict."""
        if not self.whois_data:
            return {}

        def safe_get(attr):
            val = getattr(self.whois_data, attr, None)
            if isinstance(val, list):
                return val[0] if val else None
            return val

        creation = safe_get("creation_date")
        expiration = safe_get("expiration_date")

        return {
            "registrar": safe_get("registrar"),
            "creation_date": str(creation) if creation else None,
            "expiration_date": str(expiration) if expiration else None,
            "name_servers": getattr(self.whois_data, "name_servers", None) or [],
            "registrant": safe_get("org") or safe_get("name"),
        }

    def _estimate_value(self):
        """Estimate domain value range based on multiple factors."""
        base_low = 300
        base_high = 800

        # --- Length factor ---
        name_len = len(self.name)
        if name_len <= 2:
            len_mult = (15.0, 50.0)
        elif name_len <= 3:
            len_mult = (8.0, 25.0)
        elif name_len <= 4:
            len_mult = (4.0, 15.0)
        elif name_len <= 5:
            len_mult = (2.5, 8.0)
        elif name_len <= 7:
            len_mult = (1.5, 4.0)
        elif name_len <= 10:
            len_mult = (1.0, 2.5)
        elif name_len <= 15:
            len_mult = (0.7, 1.5)
        else:
            len_mult = (0.3, 0.8)

        base_low *= len_mult[0]
        base_high *= len_mult[1]

        # --- TLD factor ---
        tld_val = TLD_VALUES.get(self.tld, 0.15)
        base_low *= tld_val
        base_high *= tld_val

        # --- Keyword quality ---
        if len(self.keywords) == 1 and len(self.keywords[0]) == len(self.name):
            # Single dictionary word — premium
            base_low *= 3.0
            base_high *= 5.0
        elif len(self.keywords) == 2:
            # Two-word combo — good
            base_low *= 1.5
            base_high *= 3.0
        elif len(self.keywords) >= 3:
            base_low *= 0.8
            base_high *= 1.5

        # --- Industry premium ---
        hot = {"technology", "finance", "health", "ecommerce", "energy", "security", "automotive"}
        if any(ind in hot for ind in self.industries):
            base_low *= 1.3
            base_high *= 1.8

        # --- Age premium ---
        if self.domain_age_years >= 20:
            base_low *= 2.5
            base_high *= 4.0
        elif self.domain_age_years >= 15:
            base_low *= 2.0
            base_high *= 3.0
        elif self.domain_age_years >= 10:
            base_low *= 1.5
            base_high *= 2.0
        elif self.domain_age_years >= 5:
            base_low *= 1.2
            base_high *= 1.5

        # --- Round ---
        self.estimated_value_low = max(50, int(round(base_low, -1)))
        self.estimated_value_high = max(100, int(round(base_high, -1)))
        if self.estimated_value_low > self.estimated_value_high:
            self.estimated_value_low, self.estimated_value_high = (
                self.estimated_value_high,
                self.estimated_value_low,
            )

    def _assess_brandability(self):
        """Compute a brandability assessment dict."""
        name = self.name
        score = 0
        factors = []

        # Length
        nlen = len(name)
        if nlen <= 5:
            score += 25
            factors.append("Very short — highly memorable")
        elif nlen <= 8:
            score += 18
            factors.append("Short and concise")
        elif nlen <= 12:
            score += 10
            factors.append("Moderate length")
        else:
            score += 3
            factors.append("Long — harder to remember")

        # Pronounceability heuristic (vowel/consonant ratio)
        vowels = sum(1 for c in name if c in "aeiou")
        consonants = sum(1 for c in name if c.isalpha() and c not in "aeiou")
        if consonants:
            vc_ratio = vowels / consonants
            if 0.3 <= vc_ratio <= 1.0:
                score += 20
                factors.append("Easy to pronounce")
            elif 0.15 <= vc_ratio < 0.3 or 1.0 < vc_ratio <= 2.0:
                score += 10
                factors.append("Moderately pronounceable")
            else:
                score += 3
                factors.append("Difficult to pronounce")
        else:
            score += 5

        # Single dictionary word
        if len(self.keywords) == 1 and self.keywords[0] == name:
            score += 20
            factors.append("Single dictionary word — premium category")
        elif len(self.keywords) == 2:
            score += 12
            factors.append("Clean two-word combination")

        # No hyphens or numbers
        if re.search(r"[-_]", name):
            factors.append("Contains hyphen/underscore — reduces brandability")
        elif re.search(r"\d", name):
            score += 3
            factors.append("Contains numbers — limits brand appeal")
        else:
            score += 10
            factors.append("Clean alphanumeric — no hyphens or numbers")

        # TLD
        if self.tld == "com":
            score += 15
            factors.append(".com — the gold standard TLD")
        elif self.tld in ("io", "ai", "co"):
            score += 10
            factors.append(f".{self.tld} — strong alternative TLD")
        elif self.tld in ("net", "org"):
            score += 7
            factors.append(f".{self.tld} — established TLD")
        else:
            score += 2

        # Industry relevance
        if self.industries and self.industries[0] != "general":
            score += 10
            factors.append(f"Strong industry signal: {self.industries[0]}")

        return {
            "score": min(100, score),
            "grade": self._brand_grade(score),
            "factors": factors,
        }

    @staticmethod
    def _brand_grade(score):
        if score >= 80:
            return "A+"
        if score >= 70:
            return "A"
        if score >= 60:
            return "B+"
        if score >= 50:
            return "B"
        if score >= 40:
            return "C+"
        if score >= 30:
            return "C"
        return "D"
