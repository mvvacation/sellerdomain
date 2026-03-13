"""Buyer research module - finds potential buyers using real search data and web scraping."""

import re
import time
from urllib.parse import urlparse

import requests
import tldextract
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from googlesearch import search as google_search
except ImportError:
    google_search = None

try:
    from serpapi import GoogleSearch as SerpApiSearch
except ImportError:
    SerpApiSearch = None


# Domains to skip (search engines, social media, directories, etc.)
SKIP_DOMAINS = {
    "google.com", "google.co", "youtube.com", "facebook.com", "twitter.com",
    "x.com", "instagram.com", "linkedin.com", "pinterest.com", "reddit.com",
    "wikipedia.org", "wikimedia.org", "amazon.com", "ebay.com", "craigslist.org",
    "yelp.com", "bbb.org", "glassdoor.com", "indeed.com", "github.com",
    "stackoverflow.com", "medium.com", "quora.com", "tiktok.com",
    "apple.com", "microsoft.com", "wordpress.com", "blogspot.com",
    "godaddy.com", "namecheap.com", "sedo.com", "dan.com", "afternic.com",
    "hugedomains.com", "domainmarket.com",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Emails to filter out
JUNK_EMAIL_PREFIXES = {
    "noreply", "no-reply", "mailer-daemon", "postmaster", "webmaster",
    "admin", "support", "info", "sales", "example", "test", "spam",
    "abuse", "privacy", "security", "donotreply",
}


class BuyerResearcher:
    """Finds potential buyers for a domain using search engines and web scraping."""

    def __init__(self, config, analysis, progress_callback=None):
        self.config = config
        self.analysis = analysis
        self.domain = analysis["domain"]
        self.keywords = analysis["keywords"]
        self.industries = analysis["industries"]
        self.progress = progress_callback or (lambda msg: None)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

    def research(self):
        """Run the full buyer research pipeline. Returns list of lead dicts."""
        self.progress("Building search queries...")
        queries = self._build_queries()

        self.progress(f"Searching with {len(queries)} queries...")
        raw_results = self._execute_searches(queries)

        self.progress(f"Extracting companies from {len(raw_results)} results...")
        companies = self._extract_companies(raw_results)

        if self.config.get("enrichment", "scrape_websites", default=True):
            max_enrich = self.config.get("enrichment", "max_enrich", default=15)
            to_enrich = companies[:max_enrich]
            self.progress(f"Enriching {len(to_enrich)} companies with website data...")
            companies = self._enrich_companies(to_enrich) + companies[max_enrich:]

        self.progress("Checking similar domains for competing companies...")
        similar = self._check_similar_domains()
        companies.extend(similar)

        # Deduplicate by base domain
        seen = set()
        unique = []
        for c in companies:
            key = c.get("website_domain", c.get("website", "")).lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(c)
            elif not key:
                unique.append(c)

        return unique

    def _build_queries(self):
        """Build intelligent search queries to find potential buyers."""
        queries = []
        kw_phrase = " ".join(self.keywords)
        name = self.analysis["name"]

        # Direct name search
        queries.append(f'"{name}" company')
        queries.append(f'"{name}" startup')

        # Keyword-based industry searches
        queries.append(f"{kw_phrase} company")
        queries.append(f"{kw_phrase} startup funding")
        queries.append(f"{kw_phrase} software company")
        queries.append(f"{kw_phrase} business")

        # Per-industry searches
        industry_terms = {
            "technology": "tech company",
            "health": "healthcare startup",
            "finance": "fintech company",
            "education": "edtech startup",
            "ecommerce": "ecommerce company",
            "travel": "travel startup",
            "food": "food tech company",
            "real_estate": "proptech company",
            "marketing": "marketing agency",
            "gaming": "gaming company",
            "automotive": "autotech startup",
            "energy": "cleantech company",
            "security": "cybersecurity company",
            "logistics": "logistics startup",
        }
        for ind in self.industries:
            if ind in industry_terms:
                queries.append(f"{kw_phrase} {industry_terms[ind]}")

        # Buyer intent queries
        queries.append(f"buy {kw_phrase} domain")
        queries.append(f"{kw_phrase} brand name")

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for q in queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)

        return unique

    def _execute_searches(self, queries):
        """Execute search queries using the configured engine."""
        engine = self.config.get("search", "engine", default="auto")
        max_per_query = self.config.get("search", "max_results_per_query", default=10)
        delay = self.config.get("search", "delay_between_searches", default=2)

        all_results = []

        for i, query in enumerate(queries):
            self.progress(f"  Query {i + 1}/{len(queries)}: {query}")
            try:
                if engine == "serpapi":
                    results = self._search_serpapi(query, max_per_query)
                elif engine == "google":
                    results = self._search_google(query, max_per_query)
                elif engine == "ddgs":
                    results = self._search_ddgs(query, max_per_query)
                else:
                    # Auto: try ddgs first, then google
                    results = self._search_auto(query, max_per_query)
                all_results.extend(results)
            except Exception as e:
                self.progress(f"  Search failed for '{query}': {e}")

            if i < len(queries) - 1:
                time.sleep(delay)

        return all_results

    def _search_auto(self, query, max_results):
        """Auto-select the best available search engine."""
        # Try DuckDuckGo first (most reliable for automation)
        if DDGS is not None:
            try:
                results = self._search_ddgs(query, max_results)
                if results:
                    return results
            except Exception:
                pass

        # Fall back to googlesearch-python
        if google_search is not None:
            try:
                results = self._search_google(query, max_results)
                if results:
                    return results
            except Exception:
                pass

        self.progress("  No search engine available. Install 'ddgs' or 'googlesearch-python'.")
        return []

    def _search_ddgs(self, query, max_results):
        """Search using DuckDuckGo (free, reliable, no API key)."""
        if DDGS is None:
            raise RuntimeError("ddgs not installed. Run: pip install ddgs")
        results = []
        try:
            ddgs_results = DDGS().text(query, max_results=max_results)
            for item in ddgs_results:
                results.append({
                    "url": item.get("href", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                    "query": query,
                })
        except Exception as e:
            self.progress(f"  DuckDuckGo search error: {e}")
        return results

    def _search_google(self, query, max_results):
        """Search using googlesearch-python (free, may get rate-limited)."""
        if google_search is None:
            raise RuntimeError(
                "googlesearch-python not installed. "
                "Run: pip install googlesearch-python"
            )
        results = []
        try:
            for url in google_search(query, num_results=max_results):
                results.append({
                    "url": url,
                    "title": "",
                    "snippet": "",
                    "query": query,
                })
        except Exception as e:
            self.progress(f"  Google search error: {e}")
        return results

    def _search_serpapi(self, query, max_results):
        """Search using SerpAPI (requires API key, more reliable)."""
        if SerpApiSearch is None:
            raise RuntimeError(
                "SerpAPI not installed. Run: pip install google-search-results"
            )
        api_key = self.config.get("search", "serpapi_key", default="")
        if not api_key:
            raise RuntimeError("SerpAPI key not configured")

        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": max_results,
        }
        search = SerpApiSearch(params)
        data = search.get_dict()

        results = []
        for item in data.get("organic_results", []):
            results.append({
                "url": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "query": query,
            })
        return results

    def _extract_companies(self, raw_results):
        """Extract company information from search results."""
        companies = {}

        for result in raw_results:
            url = result.get("url", "")
            if not url:
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Skip irrelevant domains
            if any(skip in domain for skip in SKIP_DOMAINS):
                continue
            # Skip our own domain
            if domain == self.domain:
                continue

            if domain not in companies:
                companies[domain] = {
                    "name": self._domain_to_company_name(domain),
                    "website": f"https://{domain}",
                    "website_domain": domain,
                    "url_found": url,
                    "title": result.get("title", ""),
                    "snippet": result.get("snippet", ""),
                    "matched_queries": [result.get("query", "")],
                    "emails": [],
                    "social": {},
                    "description": "",
                    "meta_title": "",
                }
            else:
                q = result.get("query", "")
                if q and q not in companies[domain]["matched_queries"]:
                    companies[domain]["matched_queries"].append(q)
                # Update title/snippet if we have better data
                if result.get("title") and not companies[domain]["title"]:
                    companies[domain]["title"] = result["title"]
                if result.get("snippet") and not companies[domain]["snippet"]:
                    companies[domain]["snippet"] = result["snippet"]

        return list(companies.values())

    def _enrich_companies(self, companies):
        """Enrich company data by visiting their websites."""
        timeout = self.config.get("enrichment", "request_timeout", default=10)
        enriched = []

        for company in companies:
            try:
                url = company["website"]
                self.progress(f"    Scraping {company['website_domain']}...")
                resp = self._session.get(url, timeout=timeout, allow_redirects=True)
                resp.raise_for_status()

                soup = BeautifulSoup(resp.text, "lxml")

                # Extract title
                if soup.title and soup.title.string:
                    company["meta_title"] = soup.title.string.strip()[:200]

                # Extract meta description
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    company["description"] = meta["content"].strip()[:500]

                # Extract emails from page
                page_emails = set(EMAIL_RE.findall(resp.text))
                # Filter junk emails and only keep emails from the company's domain
                good_emails = []
                for email in page_emails:
                    prefix = email.split("@")[0].lower()
                    email_domain = email.split("@")[1].lower()
                    if prefix in JUNK_EMAIL_PREFIXES:
                        continue
                    # Prefer emails from the same domain
                    if email_domain == company["website_domain"] or email_domain.endswith(
                        "." + company["website_domain"]
                    ):
                        good_emails.insert(0, email)
                    elif not email_domain.endswith((".png", ".jpg", ".gif", ".svg")):
                        good_emails.append(email)
                company["emails"] = good_emails[:5]

                # Extract social links
                social = {}
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if "linkedin.com/company" in href:
                        social["linkedin"] = href
                    elif "twitter.com/" in href or "x.com/" in href:
                        social["twitter"] = href
                company["social"] = social

                # Try to get a better company name from the page
                if company["meta_title"]:
                    # Often: "Company Name - Tagline" or "Company Name | Description"
                    title_parts = re.split(r"\s*[\|–\-—]\s*", company["meta_title"])
                    if title_parts:
                        candidate = title_parts[0].strip()
                        if 2 < len(candidate) < 60:
                            company["name"] = candidate

            except Exception:
                pass  # Keep the company with whatever data we have

            enriched.append(company)
            time.sleep(0.5)  # Be polite

        return enriched

    def _check_similar_domains(self):
        """Check who owns similar domain names (other TLDs)."""
        name = self.analysis["name"]
        tld = self.analysis["tld"]
        alt_tlds = ["com", "net", "org", "io", "co", "ai", "app", "dev"]
        similar = []

        for alt_tld in alt_tlds:
            if alt_tld == tld:
                continue
            alt_domain = f"{name}.{alt_tld}"
            try:
                # Quick DNS check to see if the domain is active
                dns_answers = None
                import dns.resolver
                try:
                    dns_answers = dns.resolver.resolve(alt_domain, "A")
                except Exception:
                    continue

                if dns_answers:
                    # Domain is active - try to get info
                    try:
                        resp = self._session.get(
                            f"https://{alt_domain}",
                            timeout=5,
                            allow_redirects=True,
                        )
                        soup = BeautifulSoup(resp.text, "lxml")
                        title = ""
                        desc = ""
                        if soup.title and soup.title.string:
                            title = soup.title.string.strip()[:200]
                        meta = soup.find("meta", attrs={"name": "description"})
                        if meta and meta.get("content"):
                            desc = meta["content"].strip()[:500]

                        final_domain = urlparse(resp.url).netloc.lower()
                        if final_domain.startswith("www."):
                            final_domain = final_domain[4:]

                        company_name = self._domain_to_company_name(final_domain)
                        if title:
                            parts = re.split(r"\s*[\|–\-—]\s*", title)
                            if parts and 2 < len(parts[0].strip()) < 60:
                                company_name = parts[0].strip()

                        similar.append({
                            "name": company_name,
                            "website": f"https://{final_domain}",
                            "website_domain": final_domain,
                            "url_found": f"https://{alt_domain}",
                            "title": title,
                            "snippet": desc,
                            "matched_queries": [f"Similar domain: {alt_domain}"],
                            "emails": [],
                            "social": {},
                            "description": desc,
                            "meta_title": title,
                            "is_similar_domain": True,
                        })
                    except Exception:
                        similar.append({
                            "name": self._domain_to_company_name(alt_domain),
                            "website": f"https://{alt_domain}",
                            "website_domain": alt_domain,
                            "url_found": f"https://{alt_domain}",
                            "title": "",
                            "snippet": "",
                            "matched_queries": [f"Similar domain: {alt_domain}"],
                            "emails": [],
                            "social": {},
                            "description": "",
                            "meta_title": "",
                            "is_similar_domain": True,
                        })
            except Exception:
                continue

        return similar

    @staticmethod
    def _domain_to_company_name(domain):
        """Convert a domain like 'health-track.io' to 'Health Track'."""
        # Remove TLD
        ext = tldextract.extract(domain)
        name = ext.domain
        # Split on hyphens, underscores
        parts = re.split(r"[-_]", name)
        # Title case each part
        return " ".join(p.capitalize() for p in parts if p)
