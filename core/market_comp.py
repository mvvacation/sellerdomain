"""Domain marketplace price comparison — searches for similar domain sale prices."""

import re

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


def find_comparable_sales(domain_name, tld, keywords):
    """Search for comparable domain sales and listed prices.

    Returns dict with:
      - comparables: list of {domain, price, source, url}
      - price_range: {low, high} or None
      - market_summary: str
    """
    result = {
        "comparables": [],
        "price_range": None,
        "market_summary": "",
    }

    if DDGS is None:
        result["market_summary"] = "Search engine not available"
        return result

    queries = _build_price_queries(domain_name, tld, keywords)
    all_hits = []

    for query in queries[:6]:
        try:
            for item in DDGS().text(query, max_results=8):
                url = item.get("href", "")
                title = item.get("title", "")
                snippet = item.get("body", "")
                prices = _extract_prices(title + " " + snippet)
                domains = _extract_domains(title + " " + snippet)

                if prices and domains:
                    for d in domains[:2]:
                        for p in prices[:2]:
                            all_hits.append({
                                "domain": d,
                                "price": p,
                                "source": _extract_source(url),
                                "url": url,
                            })
                elif prices and not domains:
                    # Price found but no specific domain — use info from title
                    for p in prices[:1]:
                        all_hits.append({
                            "domain": _clean_title_domain(title),
                            "price": p,
                            "source": _extract_source(url),
                            "url": url,
                        })
        except Exception:
            continue

    # Deduplicate by domain name
    seen = set()
    unique = []
    for h in all_hits:
        key = h["domain"].lower()
        if key and key not in seen and len(key) > 3:
            seen.add(key)
            unique.append(h)
    result["comparables"] = unique[:12]

    # Calculate price range
    prices = [c["price"] for c in result["comparables"] if c["price"] > 0]
    if prices:
        result["price_range"] = {
            "low": min(prices),
            "high": max(prices),
            "median": sorted(prices)[len(prices) // 2],
            "count": len(prices),
        }

    # Summary
    if result["price_range"]:
        pr = result["price_range"]
        result["market_summary"] = (
            f"Found {pr['count']} comparable sales/listings. "
            f"Price range: ${pr['low']:,.0f} — ${pr['high']:,.0f} "
            f"(median ${pr['median']:,.0f})"
        )
    else:
        result["market_summary"] = "No comparable sale prices found"

    return result


def _build_price_queries(name, tld, keywords):
    """Build search queries to find comparable domain prices."""
    kw = " ".join(keywords[:3])
    queries = [
        f'"{name}.{tld}" domain price OR sold OR sale',
        f'"{name}" domain sold price',
        f"{kw} domain sold for",
        f"{kw} .{tld} domain sale price",
        f"site:namebio.com {kw}",
        f"site:dnjournal.com {kw} sale",
        f"{kw} premium domain listing price",
    ]
    return queries


def _extract_prices(text):
    """Extract dollar prices from text."""
    patterns = [
        r"\$\s?([\d,]+(?:\.\d{2})?)\s*(?:USD)?",
        r"([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars)",
    ]
    prices = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            try:
                val = float(m.group(1).replace(",", ""))
                if 50 <= val <= 50_000_000:
                    prices.append(val)
            except ValueError:
                pass
    return prices


def _extract_domains(text):
    """Extract domain names from text."""
    pattern = r"\b([a-zA-Z0-9][-a-zA-Z0-9]*\.(?:com|net|org|io|co|ai|app|dev|tech|us|me))\b"
    found = re.findall(pattern, text, re.I)
    # Filter out common false positives
    skip = {"google.com", "facebook.com", "twitter.com", "example.com",
            "godaddy.com", "namecheap.com", "sedo.com", "dan.com"}
    return [d for d in found if d.lower() not in skip]


def _extract_source(url):
    """Extract source name from URL."""
    import tldextract
    ext = tldextract.extract(url)
    return ext.domain.capitalize()


def _clean_title_domain(title):
    """Try to extract a domain name from a search result title."""
    domains = _extract_domains(title)
    if domains:
        return domains[0]
    # Fallback: use first few words
    return title[:40].strip() if title else ""
