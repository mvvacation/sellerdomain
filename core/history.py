"""Domain history via Wayback Machine — checks archive.org for past usage."""

import logging

from bs4 import BeautifulSoup

from core.http_utils import create_session, safe_get

logger = logging.getLogger(__name__)

_TIMEOUT = 20


def check_domain_history(domain):
    """Query the Wayback Machine for domain history.

    Returns dict with:
      - total_snapshots: int
      - first_seen: str (date) or None
      - last_seen: str (date) or None
      - years_active: int
      - past_usage: str  (brief description of what the site was)
      - has_history: bool
    """
    result = {
        "total_snapshots": 0,
        "first_seen": None,
        "last_seen": None,
        "years_active": 0,
        "past_usage": "",
        "has_history": False,
    }

    session = create_session(retries=2, backoff_factor=1.0)

    # 1 — CDX API: single query with yearly collapse to get date range + count
    cdx_url = "https://web.archive.org/cdx/search/cdx"

    try:
        resp = session.get(
            cdx_url,
            params={
                "url": domain,
                "output": "json",
                "fl": "timestamp",
                "collapse": "timestamp:4",  # yearly collapse
                "limit": 500,
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if len(rows) > 1:
                timestamps = [r[0] for r in rows[1:]]
                result["has_history"] = True
                result["total_snapshots"] = len(timestamps)
                result["first_seen"] = _parse_ts(timestamps[0])
                result["last_seen"] = _parse_ts(timestamps[-1])
                first_year = int(timestamps[0][:4])
                last_year = int(timestamps[-1][:4])
                result["years_active"] = max(1, last_year - first_year + 1)
    except Exception:
        logger.debug("Failed to query Wayback Machine CDX for %s", domain, exc_info=True)
    finally:
        session.close()

    # 2 — Grab the most recent snapshot to classify past usage
    if result["has_history"]:
        result["past_usage"] = _classify_last_snapshot(domain)

    return result


def _parse_ts(ts):
    """Parse Wayback timestamp (YYYYMMDDhhmmss) to 'YYYY-MM-DD'."""
    try:
        return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
    except Exception:
        return None


def _classify_last_snapshot(domain):
    """Fetch the latest Wayback snapshot and classify the site's purpose."""
    session = create_session(retries=1, backoff_factor=0.5)
    try:
        api_url = f"https://web.archive.org/web/2/{domain}"
        resp = safe_get(session, api_url, timeout=_TIMEOUT)
        if resp is None:
            return ""

        text = resp.text[:30000]  # limit parsing size
        soup = BeautifulSoup(text, "html.parser")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()[:200]

        # Check for parking / for-sale signals
        body_text = soup.get_text(" ", strip=True)[:3000].lower()

        parking_signals = [
            "domain is for sale",
            "buy this domain",
            "domain may be for sale",
            "this domain is parked",
            "godaddy",
            "afternic",
            "sedo",
            "dan.com",
            "hugedomains",
            "domain parking",
            "under construction",
            "coming soon",
            "future home",
            "this page is parked",
            "inquire about this domain",
            "make an offer",
        ]
        is_parked = any(sig in body_text for sig in parking_signals)

        if is_parked:
            return "Parked / for sale page"

        # Category detection from content
        categories = {
            "E-commerce / Online Store": ["shop", "cart", "product", "buy now", "add to cart", "checkout"],
            "Blog / Content Site": ["blog", "article", "posted on", "read more", "comments"],
            "Business / Corporate": ["about us", "our team", "services", "contact us", "our mission"],
            "Portfolio / Personal": ["portfolio", "my work", "resume", "hire me"],
            "SaaS / Software": ["sign up", "log in", "pricing", "free trial", "dashboard"],
            "Community / Forum": ["forum", "thread", "reply", "members", "discussion"],
            "News / Media": ["breaking", "headline", "editor", "reporter", "published"],
            "Restaurant / Food": ["menu", "reservation", "dining", "cuisine", "chef"],
            "Real Estate": ["listing", "property", "bedroom", "sqft", "real estate"],
            "Healthcare": ["patient", "appointment", "doctor", "clinic", "health"],
        }

        for cat, signals in categories.items():
            matches = sum(1 for s in signals if s in body_text)
            if matches >= 2:
                summary = cat
                if title:
                    summary += f' — "{title[:80]}"'
                return summary

        if title:
            return f'Active site — "{title[:100]}"'
        return "Active site (content detected)"

    except Exception:
        return ""
    finally:
        session.close()
