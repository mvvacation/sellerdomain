"""Shared HTTP utilities — robust session factory with retry, timeouts, and connection pooling."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Identify ourselves honestly as a research tool
USER_AGENT = (
    "DomainSeller/2.1 (domain research tool; +https://github.com/sellerdomain) "
    "Python-Requests/{ver}"
).format(ver=requests.__version__)

# Default retry configuration
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 0.5
DEFAULT_TIMEOUT = 10
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)


def create_session(
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF,
    pool_size: int = 10,
    user_agent: str = USER_AGENT,
) -> requests.Session:
    """Create a requests session with retry logic and connection pooling."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_maxsize=pool_size,
        pool_connections=pool_size,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def safe_get(session: requests.Session, url: str, timeout: int = DEFAULT_TIMEOUT, **kwargs):
    """Perform a GET request with graceful error handling. Returns None on failure."""
    try:
        resp = session.get(url, timeout=timeout, allow_redirects=True, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException:
        return None
