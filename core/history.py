"""Domain history via Wayback Machine — checks archive.org for past usage."""

import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


_TIMEOUT = 20
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


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

    # 1 — CDX API: single query with yearly collapse to get date range + count
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    try:
        resp = session.get(cdx_url, params={
            "url": domain, "output": "json", "fl": "timestamp",
            "collapse": "timestamp:4",  # yearly collapse
            "limit": 500,
        }, timeout=_TIMEOUT)
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
        pass

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
    try:
        api_url = f"https://web.archive.org/web/2/{domain}"
        resp = requests.get(api_url, timeout=_TIMEOUT, headers={"User-Agent": _UA},
                            allow_redirects=True)
        if resp.status_code != 200:
            return ""

        text = resp.text[:30000]  # limit parsing size
        soup = BeautifulSoup(text, "lxml")

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()[:200]

        desc = ""
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            desc = meta["content"].strip()[:300]

        # Check for parking / for-sale signals
        body_text = soup.get_text(" ", strip=True)[:3000].lower()

        parking_signals = [
            "domain is for sale", "buy this domain", "domain may be for sale",
            "this domain is parked", "godaddy", "afternic", "sedo",
            "dan.com", "hugedomains", "domain parking", "under construction",
            "coming soon", "future home", "this page is parked",
            "inquire about this domain", "make an offer",
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
                    summary += f" — \"{title[:80]}\""
                return summary

        if title:
            return f"Active site — \"{title[:100]}\""
        return "Active site (content detected)"

    except Exception:
        return ""
