"""Smart abbreviation and acronym expansion for domain names.

Interprets short tokens (2-4 chars) that wordninja can't expand, mapping them
to likely real-world meanings using geographic codes, industry shorthand,
common initialisms, and contextual clues from neighbouring keywords.
"""

# ── Geographic codes ─────────────────────────────────────────────────────
# US states / territories
US_STATES = {
    "al": "Alabama",
    "ak": "Alaska",
    "az": "Arizona",
    "ar": "Arkansas",
    "ca": "California",
    "co": "Colorado",
    "ct": "Connecticut",
    "de": "Delaware",
    "fl": "Florida",
    "ga": "Georgia",
    "hi": "Hawaii",
    "id": "Idaho",
    "il": "Illinois",
    "in": "Indiana",
    "ia": "Iowa",
    "ks": "Kansas",
    "ky": "Kentucky",
    "la": "Louisiana",
    "me": "Maine",
    "md": "Maryland",
    "ma": "Massachusetts",
    "mi": "Michigan",
    "mn": "Minnesota",
    "ms": "Mississippi",
    "mo": "Missouri",
    "mt": "Montana",
    "ne": "Nebraska",
    "nv": "Nevada",
    "nh": "New Hampshire",
    "nj": "New Jersey",
    "nm": "New Mexico",
    "ny": "New York",
    "nc": "North Carolina",
    "nd": "North Dakota",
    "oh": "Ohio",
    "ok": "Oklahoma",
    "or": "Oregon",
    "pa": "Pennsylvania",
    "ri": "Rhode Island",
    "sc": "South Carolina",
    "sd": "South Dakota",
    "tn": "Tennessee",
    "tx": "Texas",
    "ut": "Utah",
    "vt": "Vermont",
    "va": "Virginia",
    "wa": "Washington",
    "wv": "West Virginia",
    "wi": "Wisconsin",
    "wy": "Wyoming",
    "dc": "Washington DC",
    "pr": "Puerto Rico",
    "vi": "US Virgin Islands",
    "gu": "Guam",
}

# Major US metropolitan area abbreviations
US_METRO = {
    "nyc": "New York City",
    "sf": "San Francisco",
    "la": "Los Angeles",
    "chi": "Chicago",
    "atl": "Atlanta",
    "dfw": "Dallas Fort Worth",
    "phx": "Phoenix",
    "hou": "Houston",
    "sa": "San Antonio",
    "sd": "San Diego",
    "sj": "San Jose",
    "jax": "Jacksonville",
    "lv": "Las Vegas",
    "den": "Denver",
    "sea": "Seattle",
    "pdx": "Portland",
    "stl": "St Louis",
    "kc": "Kansas City",
    "nola": "New Orleans",
    "mia": "Miami",
    "orl": "Orlando",
    "tb": "Tampa Bay",
    "pit": "Pittsburgh",
    "cle": "Cleveland",
    "cin": "Cincinnati",
    "det": "Detroit",
    "msp": "Minneapolis",
    "aus": "Austin",
    "slc": "Salt Lake City",
    "rdu": "Raleigh Durham",
    "bos": "Boston",
    "phl": "Philadelphia",
    "bal": "Baltimore",
    "rva": "Richmond",
    "clt": "Charlotte",
    "jsy": "Jersey",
    "li": "Long Island",
}

# Well-known geographic abbreviations beyond US
GEO_ABBREV = {
    "uk": "United Kingdom",
    "eu": "Europe",
    "mv": "Martha's Vineyard",
    "bc": "British Columbia",
    "hk": "Hong Kong",
    "sg": "Singapore",
    "ae": "UAE",
    "nz": "New Zealand",
    "oz": "Australia",
    "uae": "UAE",
    "aus": "Australia",
    "can": "Canada",
    "ire": "Ireland",
    "sco": "Scotland",
    "lon": "London",
    "ber": "Berlin",
    "par": "Paris",
    "ams": "Amsterdam",
    "dxb": "Dubai",
    "ist": "Istanbul",
    "tok": "Tokyo",
    "ban": "Bangalore",
    "mum": "Mumbai",
    "del": "Delhi",
    "mel": "Melbourne",
    "syd": "Sydney",
    "tor": "Toronto",
    "van": "Vancouver",
    "mtl": "Montreal",
    "edi": "Edinburgh",
    "man": "Manchester",
    "bri": "Bristol",
    "brm": "Birmingham",
}

# Island / resort / vacation destinations (important for travel/food)
ISLAND_ABBREV = {
    "mv": "Maldives",
    "bvi": "British Virgin Islands",
    "usvi": "US Virgin Islands",
    "stx": "St Croix",
    "stt": "St Thomas",
    "stj": "St John",
    "obx": "Outer Banks",
    "lbi": "Long Beach Island",
    "hhi": "Hilton Head Island",
    "jfk": "JFK",
    "kw": "Key West",
    "si": "Staten Island",
    "bi": "Block Island",
    "fi": "Fire Island",
    "ai": "Amelia Island",
    "ki": "Kiawah Island",
    "nk": "Nantucket",
    "ack": "Nantucket",
    "mvy": "Martha's Vineyard",
    "cc": "Cape Cod",
}

# Country codes (ISO 3166-1 alpha-2) — selective, most useful
COUNTRY_CODES = {
    "us": "United States",
    "gb": "United Kingdom",
    "uk": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "nz": "New Zealand",
    "ie": "Ireland",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "it": "Italy",
    "nl": "Netherlands",
    "se": "Sweden",
    "no": "Norway",
    "dk": "Denmark",
    "fi": "Finland",
    "pt": "Portugal",
    "ch": "Switzerland",
    "at": "Austria",
    "be": "Belgium",
    "pl": "Poland",
    "cz": "Czech Republic",
    "jp": "Japan",
    "cn": "China",
    "kr": "South Korea",
    "in": "India",
    "sg": "Singapore",
    "hk": "Hong Kong",
    "tw": "Taiwan",
    "th": "Thailand",
    "my": "Malaysia",
    "ph": "Philippines",
    "id": "Indonesia",
    "vn": "Vietnam",
    "ae": "UAE",
    "sa": "Saudi Arabia",
    "il": "Israel",
    "tr": "Turkey",
    "za": "South Africa",
    "ng": "Nigeria",
    "ke": "Kenya",
    "eg": "Egypt",
    "br": "Brazil",
    "mx": "Mexico",
    "ar": "Argentina",
    "cl": "Chile",
    "co": "Colombia",
    "pe": "Peru",
    "mv": "Maldives",
    "lk": "Sri Lanka",
    "np": "Nepal",
    "bd": "Bangladesh",
}

# ── Industry / niche abbreviations ───────────────────────────────────────
INDUSTRY_ABBREV = {
    "hr": "human resources",
    "pr": "public relations",
    "it": "information technology",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "iot": "internet of things",
    "ev": "electric vehicle",
    "vr": "virtual reality",
    "ar": "augmented reality",
    "xr": "extended reality",
    "rx": "pharmacy",
    "dx": "diagnostics",
    "fx": "foreign exchange",
    "dj": "DJ",
    "biz": "business",
    "mgmt": "management",
    "mkt": "marketing",
    "ops": "operations",
    "dev": "development",
    "eng": "engineering",
    "svc": "services",
    "sys": "systems",
    "sol": "solutions",
    "grp": "group",
    "intl": "international",
    "natl": "national",
    "assn": "association",
    "org": "organization",
    "acct": "accounting",
    "med": "medical",
    "vet": "veterinary",
    "edu": "education",
    "govt": "government",
    "fin": "financial",
    "ins": "insurance",
    "tech": "technology",
    "bio": "biotech",
    "eco": "eco",
    "auto": "automotive",
}

# ── Common prefix / suffix patterns ─────────────────────────────────────
COMMON_PREFIXES = {
    "get": "get",
    "my": "my",
    "go": "go",
    "the": "the",
    "try": "try",
    "use": "use",
    "pro": "professional",
    "ez": "easy",
    "e": "electronic",
    "i": "internet",
}

# ── Context-aware matching ───────────────────────────────────────────────
# When a short token appears next to certain keywords, prefer certain expansions.
# Key = neighbour keyword, Value = dict of {abbrev: preferred_expansion}
CONTEXT_HINTS = {
    # Food / dining context → prefer location meaning
    "restaurant": {
        "mv": "Martha's Vineyard",
        "la": "Los Angeles",
        "sf": "San Francisco",
        "dc": "Washington DC",
        "kc": "Kansas City",
        "nola": "New Orleans",
    },
    "restaurants": {
        "mv": "Martha's Vineyard",
        "la": "Los Angeles",
        "sf": "San Francisco",
        "dc": "Washington DC",
        "kc": "Kansas City",
        "nola": "New Orleans",
    },
    "food": {"mv": "Martha's Vineyard", "la": "Los Angeles", "ny": "New York"},
    "foods": {"mv": "Martha's Vineyard", "la": "Los Angeles", "ny": "New York"},
    "eat": {"mv": "Martha's Vineyard", "la": "Los Angeles"},
    "eats": {"mv": "Martha's Vineyard", "la": "Los Angeles"},
    "dine": {"mv": "Martha's Vineyard"},
    "dining": {"mv": "Martha's Vineyard"},
    "cafe": {"mv": "Martha's Vineyard", "sf": "San Francisco"},
    "pizza": {"nyc": "New York City", "ny": "New York", "chi": "Chicago"},
    "bbq": {"kc": "Kansas City", "tx": "Texas", "nc": "North Carolina"},
    "sushi": {"la": "Los Angeles", "sf": "San Francisco", "nyc": "New York City"},
    "tacos": {"la": "Los Angeles", "sd": "San Diego", "tx": "Texas"},
    "chef": {"mv": "Martha's Vineyard", "la": "Los Angeles"},
    "catering": {"mv": "Martha's Vineyard"},
    "bar": {"mv": "Martha's Vineyard"},
    "grill": {"mv": "Martha's Vineyard"},
    "bakery": {"mv": "Martha's Vineyard", "sf": "San Francisco"},
    "brew": {"den": "Denver", "pdx": "Portland", "sd": "San Diego"},
    # Hotel / travel / tourism context → prefer destination
    "hotel": {"mv": "Maldives", "la": "Los Angeles", "lv": "Las Vegas"},
    "hotels": {"mv": "Maldives", "la": "Los Angeles", "lv": "Las Vegas"},
    "resort": {"mv": "Maldives"},
    "resorts": {"mv": "Maldives"},
    "villa": {"mv": "Maldives"},
    "villas": {"mv": "Maldives"},
    "travel": {"mv": "Maldives"},
    "tours": {"mv": "Maldives", "la": "Los Angeles"},
    "trip": {"mv": "Maldives"},
    "booking": {"mv": "Maldives"},
    "vacation": {"mv": "Maldives"},
    "getaway": {"mv": "Maldives"},
    "beach": {"mv": "Maldives"},
    "island": {"mv": "Maldives"},
    "spa": {"mv": "Maldives"},
    "dive": {"mv": "Maldives"},
    "diving": {"mv": "Maldives"},
    "snorkel": {"mv": "Maldives"},
    "cruise": {"mv": "Maldives"},
    "yacht": {"mv": "Maldives"},
    # Real estate context → prefer location
    "homes": {"la": "Los Angeles", "sf": "San Francisco", "dc": "Washington DC"},
    "realty": {"la": "Los Angeles", "sf": "San Francisco"},
    "property": {"la": "Los Angeles", "mv": "Martha's Vineyard"},
    "rentals": {"la": "Los Angeles", "mv": "Martha's Vineyard"},
    "rent": {"la": "Los Angeles", "sf": "San Francisco"},
    # Services context → prefer location
    "plumber": {"dc": "Washington DC", "la": "Los Angeles"},
    "plumbing": {"dc": "Washington DC", "la": "Los Angeles"},
    "lawyer": {"dc": "Washington DC", "la": "Los Angeles", "ny": "New York"},
    "dental": {"la": "Los Angeles", "sf": "San Francisco"},
    "cleaning": {"la": "Los Angeles", "sf": "San Francisco"},
    "moving": {"la": "Los Angeles", "nyc": "New York City"},
    "auto": {"la": "Los Angeles"},
}


def expand_abbreviations(keywords, domain_name=""):
    """Given extracted keywords and the raw domain name, expand any
    abbreviations/acronyms into meaningful interpretations.

    Returns a dict with:
      - interpretations: list of {expansion, type, confidence} dicts
      - expanded_keywords: enriched keyword list including expansions
      - geo_targets: list of geographic location strings detected
      - niche_context: string describing the detected niche (e.g. "restaurants in Martha's Vineyard")
      - search_phrases: list of expanded phrases for search queries
    """
    keywords_lower = [k.lower() for k in keywords]
    name_lower = domain_name.lower()

    interpretations = []
    geo_targets = []
    expanded_kws = list(keywords_lower)
    search_phrases = []

    # Partition keywords into "short" (potential abbreviation) and "long" (context)
    short_tokens = [k for k in keywords_lower if len(k) <= 4]
    long_tokens = [k for k in keywords_lower if len(k) > 4]

    for token in short_tokens:
        token_interps = _expand_single_token(token, long_tokens, keywords_lower)
        if token_interps:
            interpretations.extend(token_interps)

    # Also check for compound patterns in the raw name
    # e.g., "mvrestaurants" — check if the full name minus a known suffix gives an abbreviation
    _check_compound_patterns(name_lower, keywords_lower, interpretations)

    # Deduplicate interpretations
    seen = set()
    unique_interps = []
    for interp in interpretations:
        key = (interp["token"], interp["expansion"].lower())
        if key not in seen:
            seen.add(key)
            unique_interps.append(interp)
    interpretations = sorted(unique_interps, key=lambda x: -x["confidence"])

    # Build geo_targets from geographic interpretations
    for interp in interpretations:
        if interp["type"] in ("geo_metro", "geo_state", "geo_country", "geo_island", "geo_other", "geo_context"):
            if interp["expansion"] not in geo_targets:
                geo_targets.append(interp["expansion"])

    # Build expanded keywords — add geo and industry expansions to keyword list
    for interp in interpretations:
        exp_lower = interp["expansion"].lower()
        exp_words = exp_lower.split()
        for w in exp_words:
            if w not in expanded_kws and len(w) > 1:
                expanded_kws.append(w)

    # Build search phrases — combining expanded abbreviations with context keywords
    for interp in interpretations:
        expansion = interp["expansion"]
        for lk in long_tokens:
            phrase = f"{expansion} {lk}"
            if phrase not in search_phrases:
                search_phrases.append(phrase)
        # Also add just the expansion by itself if it's a location
        if interp["type"].startswith("geo") and expansion not in search_phrases:
            search_phrases.append(expansion)

    # Build niche context — human-readable description
    niche_context = _build_niche_context(interpretations, long_tokens, keywords_lower)

    return {
        "interpretations": interpretations,
        "expanded_keywords": expanded_kws,
        "geo_targets": geo_targets,
        "niche_context": niche_context,
        "search_phrases": search_phrases,
    }


def _expand_single_token(token, context_keywords, all_keywords):
    """Expand a single short token using all available dictionaries and context."""
    results = []

    # 1. Context-aware expansion — highest confidence
    for ctx_kw in context_keywords:
        hints = CONTEXT_HINTS.get(ctx_kw, {})
        if token in hints:
            results.append(
                {
                    "token": token,
                    "expansion": hints[token],
                    "type": "geo_context",
                    "confidence": 0.95,
                    "reason": f"'{token}' + '{ctx_kw}' → {hints[token]}",
                }
            )

    # 2. US metro areas
    if token in US_METRO:
        results.append(
            {
                "token": token,
                "expansion": US_METRO[token],
                "type": "geo_metro",
                "confidence": 0.85,
                "reason": f"'{token}' is a US metro abbreviation for {US_METRO[token]}",
            }
        )

    # 3. Island / destination codes
    if token in ISLAND_ABBREV:
        exp = ISLAND_ABBREV[token]
        # Don't duplicate if already in results with higher confidence
        existing = {r["expansion"] for r in results}
        if exp not in existing:
            results.append(
                {
                    "token": token,
                    "expansion": exp,
                    "type": "geo_island",
                    "confidence": 0.75,
                    "reason": f"'{token}' is an abbreviation for {exp}",
                }
            )

    # 4. Geographic abbreviations
    if token in GEO_ABBREV:
        exp = GEO_ABBREV[token]
        existing = {r["expansion"] for r in results}
        if exp not in existing:
            results.append(
                {
                    "token": token,
                    "expansion": exp,
                    "type": "geo_other",
                    "confidence": 0.70,
                    "reason": f"'{token}' → {exp}",
                }
            )

    # 5. US state codes (only 2-letter tokens)
    if len(token) == 2 and token in US_STATES:
        exp = US_STATES[token]
        existing = {r["expansion"] for r in results}
        if exp not in existing:
            results.append(
                {
                    "token": token,
                    "expansion": exp,
                    "type": "geo_state",
                    "confidence": 0.60,
                    "reason": f"'{token}' is the US state code for {exp}",
                }
            )

    # 6. Country codes (lower confidence for ambiguous ones)
    if len(token) == 2 and token in COUNTRY_CODES:
        exp = COUNTRY_CODES[token]
        existing = {r["expansion"] for r in results}
        if exp not in existing:
            results.append(
                {
                    "token": token,
                    "expansion": exp,
                    "type": "geo_country",
                    "confidence": 0.45,
                    "reason": f"'{token}' is the country code for {exp}",
                }
            )

    # 7. Industry abbreviations
    if token in INDUSTRY_ABBREV:
        results.append(
            {
                "token": token,
                "expansion": INDUSTRY_ABBREV[token],
                "type": "industry",
                "confidence": 0.65,
                "reason": f"'{token}' = {INDUSTRY_ABBREV[token]}",
            }
        )

    return results


def _check_compound_patterns(name, keywords, interpretations):
    """Check if the domain name embeds a known prefix+keyword pattern.
    e.g. 'getpizza' → 'get' + 'pizza', 'myhotel' → 'my' + 'hotel'
    """
    for prefix, meaning in COMMON_PREFIXES.items():
        if name.startswith(prefix) and len(name) > len(prefix) + 2:
            rest = name[len(prefix) :]
            # Check if the rest is a real word (appears in keywords or is long)
            if rest in keywords or len(rest) >= 4:
                interpretations.append(
                    {
                        "token": prefix,
                        "expansion": meaning,
                        "type": "prefix",
                        "confidence": 0.50,
                        "reason": f"Prefix pattern: '{prefix}' + '{rest}'",
                    }
                )


def _build_niche_context(interpretations, long_tokens, all_keywords):
    """Build a human-readable niche context string."""
    if not interpretations:
        return ""

    # Find the highest-confidence geographic interpretation
    geo_interps = [i for i in interpretations if i["type"].startswith("geo")]
    industry_interps = [i for i in interpretations if i["type"] == "industry"]

    parts = []

    if long_tokens:
        niche = " ".join(long_tokens)
        if geo_interps:
            # Multiple geo interpretations = multiple target markets
            locations = []
            for gi in geo_interps[:3]:  # Top 3
                locations.append(gi["expansion"])
            if len(locations) == 1:
                parts.append(f"{niche} in {locations[0]}")
            else:
                parts.append(f"{niche} targeting: {', '.join(locations)}")
        else:
            parts.append(niche)
    elif geo_interps:
        parts.append(f"Targeting {geo_interps[0]['expansion']}")

    if industry_interps and not long_tokens:
        parts.append(f"({industry_interps[0]['expansion']})")

    return " — ".join(parts) if parts else ""
