"""Social handle availability checker — checks major platforms for matching usernames."""

import re
import requests


_TIMEOUT = 8
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# Platforms to check, with URL template and "taken" detection strategy.
# {name} is replaced with the username.
PLATFORMS = [
    {
        "name": "Twitter / X",
        "url": "https://x.com/{name}",
        "taken_if_status": 200,
        "icon": "twitter",
    },
    {
        "name": "Instagram",
        "url": "https://www.instagram.com/{name}/",
        "taken_if_status": 200,
        "icon": "instagram",
    },
    {
        "name": "GitHub",
        "url": "https://github.com/{name}",
        "taken_if_status": 200,
        "icon": "github",
    },
    {
        "name": "TikTok",
        "url": "https://www.tiktok.com/@{name}",
        "taken_if_status": 200,
        "icon": "tiktok",
    },
    {
        "name": "YouTube",
        "url": "https://www.youtube.com/@{name}",
        "taken_if_status": 200,
        "icon": "youtube",
    },
    {
        "name": "Reddit",
        "url": "https://www.reddit.com/user/{name}",
        "taken_if_status": 200,
        "icon": "reddit",
    },
    {
        "name": "LinkedIn (company)",
        "url": "https://www.linkedin.com/company/{name}",
        "taken_if_status": 200,
        "icon": "linkedin",
    },
]


def check_social_handles(domain_name):
    """Check if the domain name (without TLD) is taken as a username on major platforms.

    Returns dict with:
      - handles: list of {platform, url, status, icon}
      - taken_count: int
      - available_count: int
      - summary: str
    """
    # Clean the name for use as a handle — remove non-alphanumeric
    handle = re.sub(r"[^a-zA-Z0-9]", "", domain_name).lower()
    if len(handle) < 2:
        return {"handles": [], "taken_count": 0, "available_count": 0, "summary": ""}

    handles = []
    taken = 0
    available = 0

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    for platform in PLATFORMS:
        url = platform["url"].format(name=handle)
        status = "unknown"
        try:
            resp = session.head(url, timeout=_TIMEOUT, allow_redirects=True)
            if resp.status_code == platform["taken_if_status"]:
                status = "taken"
                taken += 1
            elif resp.status_code in (404, 410):
                status = "available"
                available += 1
            else:
                # Some platforms return 302 to login for taken profiles
                if resp.status_code in (301, 302):
                    final = resp.headers.get("Location", "")
                    if handle in final.lower():
                        status = "taken"
                        taken += 1
                    else:
                        status = "available"
                        available += 1
                else:
                    status = "unknown"
        except requests.RequestException:
            status = "unknown"

        handles.append({
            "platform": platform["name"],
            "url": url if status == "taken" else "",
            "status": status,
            "icon": platform["icon"],
        })

    # Build summary
    total = len(PLATFORMS)
    if taken == 0:
        summary = f"Handle @{handle} appears available on all {total} platforms"
    elif taken == total:
        summary = f"Handle @{handle} is taken on all {total} platforms — high demand name"
    elif taken >= total // 2:
        summary = f"Handle @{handle} is taken on {taken}/{total} platforms — established brand name"
    else:
        summary = f"Handle @{handle} is taken on {taken}/{total} platforms"

    return {
        "handle": handle,
        "handles": handles,
        "taken_count": taken,
        "available_count": available,
        "summary": summary,
    }
