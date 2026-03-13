"""Input validation utilities for Domain Seller."""

import re

import tldextract

# Strict domain pattern: alphanumeric + hyphens, valid TLD
_DOMAIN_RE = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")

# Maximum domain length per RFC
_MAX_DOMAIN_LENGTH = 253


class ValidationError(ValueError):
    """Raised when input validation fails."""


def validate_domain(domain: str) -> str:
    """Validate and normalise a domain name.

    Returns the cleaned domain string or raises ValidationError.
    """
    if not domain or not isinstance(domain, str):
        raise ValidationError("Domain must be a non-empty string")

    domain = domain.strip().lower()

    # Strip protocol if user accidentally included it
    for prefix in ("https://", "http://", "//"):
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]

    # Strip trailing slash / path
    domain = domain.split("/")[0]

    # Strip www.
    if domain.startswith("www."):
        domain = domain[4:]

    if len(domain) > _MAX_DOMAIN_LENGTH:
        raise ValidationError(f"Domain exceeds maximum length ({_MAX_DOMAIN_LENGTH} chars)")

    if not _DOMAIN_RE.match(domain):
        raise ValidationError(f"Invalid domain format: '{domain}'. Expected format: example.com")

    # Verify it has a real TLD
    ext = tldextract.extract(domain)
    if not ext.domain or not ext.suffix:
        raise ValidationError(f"Could not parse domain/TLD from '{domain}'")

    return domain


def validate_config_values(config_data: dict) -> list[str]:
    """Validate configuration values, returning a list of warnings."""
    warnings = []

    search = config_data.get("search", {})
    if search.get("max_results_per_query", 10) > 50:
        warnings.append("max_results_per_query > 50 may cause rate limiting")
    if search.get("delay_between_searches", 2) < 1:
        warnings.append("delay_between_searches < 1s risks rate limiting")

    enrichment = config_data.get("enrichment", {})
    if enrichment.get("request_timeout", 10) < 3:
        warnings.append("request_timeout < 3s may cause too many timeouts")
    if enrichment.get("max_enrich", 20) > 50:
        warnings.append("max_enrich > 50 will significantly slow down processing")

    leads = config_data.get("leads", {})
    if leads.get("min_score", 20) > 80:
        warnings.append("min_score > 80 may filter out most leads")

    return warnings
