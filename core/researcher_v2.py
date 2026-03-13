"""Buyer research module v3 - robust retry, deeper search, contact discovery, enrichment."""

import json as _json
import re
import time
from urllib.parse import urlparse

import dns.resolver
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import tldextract
from bs4 import BeautifulSoup

from core.cache import SearchCache

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


# Domains to skip — big platforms, news, government, directories, etc.
SKIP_DOMAINS = {
    # Search engines & big tech
    "google.com", "google.co", "youtube.com", "facebook.com", "twitter.com",
    "x.com", "instagram.com", "linkedin.com", "pinterest.com", "reddit.com",
    "wikipedia.org", "wikimedia.org", "amazon.com", "ebay.com", "craigslist.org",
    "yelp.com", "bbb.org", "glassdoor.com", "indeed.com", "github.com",
    "stackoverflow.com", "medium.com", "quora.com", "tiktok.com",
    "apple.com", "microsoft.com", "wordpress.com", "blogspot.com",
    # Domain marketplaces
    "godaddy.com", "namecheap.com", "sedo.com", "dan.com", "afternic.com",
    "hugedomains.com", "domainmarket.com", "spaceship.com",
    # CDN / infrastructure
    "w3.org", "schema.org", "cloudflare.com", "gstatic.com", "googleapis.com",
    "googletagmanager.com", "doubleclick.net", "cdn.jsdelivr.net", "unpkg.com",
    # News / media / publications
    "techcrunch.com", "fortune.com", "forbes.com", "bloomberg.com", "cnbc.com",
    "reuters.com", "nytimes.com", "wsj.com", "bbc.com", "bbc.co.uk",
    "theverge.com", "wired.com", "arstechnica.com", "cnn.com", "businessinsider.com",
    "fastcompany.com", "inc.com", "entrepreneur.com", "venturebeat.com",
    "zdnet.com", "mashable.com", "huffpost.com", "engadget.com",
    "fiercehealthcare.com", "healthcaredive.com", "mobihealthnews.com",
    "medcitynews.com", "statnews.com", "healthcareweekly.com",
    "hitconsultant.net", "healthlawinformer.com", "healthdatapalooza.org",
    "prnewswire.com", "businesswire.com", "pymnts.com", "capitalbrief.com",
    "siliconprairienews.com", "thesaasnews.com", "businessden.com",
    "macrumors.com",
    # Investment / directory / listing sites
    "crunchbase.com", "news.crunchbase.com", "pitchbook.com", "tracxn.com",
    "ycombinator.com", "builtin.com", "builtinboston.com", "angellist.com",
    "cbinsights.com", "growthlist.co", "seedtable.com", "fundraiseinsider.com",
    "startupblink.com", "startupsavant.com", "ventureradar.com",
    # Government & academic
    "cdc.gov", "nih.gov", "ncbi.nlm.nih.gov", "pubmed.ncbi.nlm.nih.gov",
    "hhs.gov", "telehealth.hhs.gov", "who.int", "gov.uk",
    "edu", "ac.uk", "berkeley.edu",
    # Design / dev / aggregate sites
    "dribbble.com", "figma.com", "devpost.com", "softonic.com",
    "producthunt.com", "g2.com", "capterra.com", "trustpilot.com",
    # Big retailers / generic
    "walmart.com", "target.com", "bestbuy.com",
    # Other large / irrelevant
    "mayoclinic.org", "sxsw.com", "consumer.huawei.com", "garmin.com",
    "myfitnesspal.com", "ouraring.com", "whoop.com", "fitbit.com",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# File/image extensions that look like TLDs but aren't valid emails
_FAKE_EMAIL_TLDS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "ico",
    "css", "js", "json", "xml", "html", "htm", "pdf", "doc",
    "zip", "tar", "gz", "mp3", "mp4", "avi", "mov", "exe",
    "woff", "woff2", "ttf", "eot", "map", "min",
}
PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    r"|(?:\+\d{1,3}[-.\s]?)?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)

JUNK_EMAIL_PREFIXES = {
    "noreply", "no-reply", "mailer-daemon", "postmaster", "webmaster",
    "donotreply", "do-not-reply", "bounce", "daemon", "nobody",
}

# Technology detection patterns (check HTML/headers)
TECH_PATTERNS = {
    "WordPress": [r"wp-content", r"wp-includes"],
    "Shopify": [r"cdn\.shopify\.com", r"shopify\.com"],
    "React": [r"react", r"__next"],
    "Vue.js": [r"vue\.", r"__vue__"],
    "Angular": [r"ng-version", r"angular"],
    "Next.js": [r"_next/", r"__NEXT_DATA__"],
    "Wix": [r"wix\.com", r"parastorage"],
    "Squarespace": [r"squarespace", r"sqsp"],
    "HubSpot": [r"hubspot", r"hs-scripts"],
    "Webflow": [r"webflow"],
    "Laravel": [r"laravel"],
    "Django": [r"csrfmiddlewaretoken", r"django"],
    "Ruby on Rails": [r"csrf-token.*authenticity"],
    "Bootstrap": [r"bootstrap"],
    "Tailwind": [r"tailwindcss"],
}


class BuyerResearcher:
    """Enhanced buyer researcher with retry logic, caching, contact discovery, and deep enrichment."""

    _MAX_HTTP_RETRIES = 3
    _BACKOFF_FACTOR = 0.5

    def __init__(self, config, analysis, progress_callback=None):
        self.config = config
        self.analysis = analysis
        self.domain = analysis["domain"]
        self.keywords = analysis["keywords"]
        self.industries = analysis["industries"]
        self.geo_targets = analysis.get("geo_targets", [])
        self.search_phrases = analysis.get("search_phrases", [])
        self.interpretations = analysis.get("interpretations", [])
        self.niche_context = analysis.get("niche_context", "")
        self.progress = progress_callback or (lambda msg, **kw: None)

        # --- Robust session with retry adapter ---
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        retry_strategy = Retry(
            total=self._MAX_HTTP_RETRIES,
            backoff_factor=self._BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_maxsize=10, pool_connections=10)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self.cache = SearchCache(
            enabled=config.get("cache", "enabled", default=True),
            ttl_hours=config.get("cache", "ttl_hours", default=24),
        )

    # ── Helpers ───────────────────────────────────────────────────

    def _safe_get(self, url, timeout=10, **kwargs):
        """GET with graceful degradation — returns None on failure."""
        try:
            resp = self._session.get(url, timeout=timeout, allow_redirects=True, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException:
            return None

    def research(self):
        """Run the full buyer research pipeline. Returns list of lead dicts."""
        try:
            return self._run_pipeline()
        finally:
            self._session.close()

    def _run_pipeline(self):
        """Internal pipeline — always called via research() for cleanup."""
        self.progress("Building search queries...", step="queries")
        queries = self._build_queries()

        self.progress(f"Searching with {len(queries)} queries...", step="search", total=len(queries))
        raw_results = self._execute_searches(queries)

        self.progress(f"Extracting companies from {len(raw_results)} results...", step="extract")
        companies = self._extract_companies(raw_results)

        if self.config.get("enrichment", "scrape_websites", default=True):
            max_enrich = self.config.get("enrichment", "max_enrich", default=20)
            to_enrich = companies[:max_enrich]
            self.progress(f"Enriching {len(to_enrich)} companies...", step="enrich", total=len(to_enrich))
            companies = self._enrich_companies(to_enrich) + companies[max_enrich:]

        self.progress("Checking similar domains...", step="similar")
        similar = self._check_similar_domains()
        companies.extend(similar)

        self.progress("Checking domain name variations...", step="variations")
        variations = self._check_domain_variations()
        companies.extend(variations)

        self.progress("Discovering contact information...", step="contacts", total=len(companies))
        companies = self._discover_contacts(companies)

        # Deduplicate by base domain (cross-TLD aware)
        seen = set()
        unique = []
        for c in companies:
            raw = c.get("website_domain", c.get("website", "")).lower()
            if raw:
                ext = tldextract.extract(raw)
                root = ext.domain.lower()  # normalize acme.com & acme.net → "acme"
                if root not in seen:
                    seen.add(root)
                    unique.append(c)
            else:
                unique.append(c)

        return unique

    def _build_queries(self):
        """Build extensive, industry-aware search queries."""
        queries = []
        kw_phrase = " ".join(self.keywords)
        name = self.analysis["name"]

        # --- Exact match queries ---
        queries.append(f'"{name}" company')
        queries.append(f'"{name}" startup')
        queries.append(f'"{name}" brand')

        # --- Keyword industry queries ---
        queries.append(f"{kw_phrase} company")
        queries.append(f"{kw_phrase} startup")
        queries.append(f"{kw_phrase} software")
        queries.append(f"{kw_phrase} platform")
        queries.append(f"{kw_phrase} SaaS")
        queries.append(f"{kw_phrase} business")
        queries.append(f"{kw_phrase} app")

        # --- Funding/investment queries (funded startups are buyers) ---
        queries.append(f"{kw_phrase} startup funding")
        queries.append(f"{kw_phrase} seed round")
        queries.append(f"{kw_phrase} series A")
        queries.append(f'"{kw_phrase}" raises funding')

        # --- Per-industry deep queries ---
        industry_queries = {
            "technology": [
                f"{kw_phrase} tech startup",
                f"{kw_phrase} software company",
                f"{kw_phrase} API platform",
                f"{kw_phrase} developer tools",
            ],
            "health": [
                f"{kw_phrase} healthcare startup",
                f"{kw_phrase} health tech company",
                f"{kw_phrase} digital health platform",
                f"{kw_phrase} medical device company",
                f"{kw_phrase} telehealth",
                f"{kw_phrase} wellness app",
            ],
            "finance": [
                f"{kw_phrase} fintech startup",
                f"{kw_phrase} financial services company",
                f"{kw_phrase} payment platform",
                f"{kw_phrase} investment firm",
                f"{kw_phrase} neobank",
            ],
            "education": [
                f"{kw_phrase} edtech startup",
                f"{kw_phrase} online learning platform",
                f"{kw_phrase} education company",
                f"{kw_phrase} e-learning",
            ],
            "ecommerce": [
                f"{kw_phrase} ecommerce company",
                f"{kw_phrase} online store",
                f"{kw_phrase} D2C brand",
                f"{kw_phrase} marketplace",
                f"{kw_phrase} retail tech",
            ],
            "travel": [
                f"{kw_phrase} travel tech startup",
                f"{kw_phrase} booking platform",
                f"{kw_phrase} tourism company",
            ],
            "food": [
                f"{kw_phrase} food tech company",
                f"{kw_phrase} restaurant tech",
                f"{kw_phrase} meal delivery",
                f"{kw_phrase} food startup",
            ],
            "real_estate": [
                f"{kw_phrase} proptech startup",
                f"{kw_phrase} real estate tech",
                f"{kw_phrase} property management software",
            ],
            "marketing": [
                f"{kw_phrase} marketing agency",
                f"{kw_phrase} martech company",
                f"{kw_phrase} SEO agency",
                f"{kw_phrase} digital marketing",
            ],
            "gaming": [
                f"{kw_phrase} gaming company",
                f"{kw_phrase} game studio",
                f"{kw_phrase} esports",
            ],
            "automotive": [
                f"{kw_phrase} automotive tech",
                f"{kw_phrase} EV startup",
                f"{kw_phrase} mobility company",
            ],
            "energy": [
                f"{kw_phrase} cleantech startup",
                f"{kw_phrase} energy company",
                f"{kw_phrase} renewable energy",
            ],
            "security": [
                f"{kw_phrase} cybersecurity company",
                f"{kw_phrase} security startup",
                f"{kw_phrase} infosec",
            ],
            "logistics": [
                f"{kw_phrase} logistics company",
                f"{kw_phrase} supply chain startup",
                f"{kw_phrase} shipping tech",
            ],
        }
        for ind in self.industries:
            for q in industry_queries.get(ind, []):
                queries.append(q)

        # --- Competitor / rebrand queries ---
        queries.append(f"{kw_phrase} competitors")
        queries.append(f"best {kw_phrase} companies")
        queries.append(f"top {kw_phrase} startups 2025")
        queries.append(f"top {kw_phrase} startups 2026")

        # --- Buyer intent queries ---
        queries.append(f"buy {kw_phrase} domain")
        queries.append(f"{kw_phrase} brand name")
        queries.append(f"{name} rebrand")

        # --- Branded variation queries (who uses "get/my/use/go + name") ---
        for prefix in ("get", "my", "use", "go", "try", "the"):
            queries.append(f'"{prefix}{name}" company')
        queries.append(f'"{name}hq" company')
        queries.append(f'"{name}app" OR "{name}io"')

        # --- LinkedIn / Crunchbase discovery ---
        queries.append(f'site:linkedin.com/company "{kw_phrase}"')
        queries.append(f'site:crunchbase.com "{kw_phrase}"')

        # --- Interpretation-aware queries (geo-expanded abbreviations) ---
        for phrase in self.search_phrases:
            queries.append(f'"{phrase}" company')
            queries.append(f'"{phrase}" business')
        # Location-specific queries when geo targets detected
        for geo in self.geo_targets:
            for kw in self.keywords:
                if kw.lower() != geo.lower() and len(kw) > 3:
                    queries.append(f"{kw} in {geo}")
                    queries.append(f"{kw} {geo} company")
                    queries.append(f"{kw} business {geo}")
            queries.append(f'"{geo}" {kw_phrase} business')
            queries.append(f'"{geo}" {kw_phrase} startup')
            # Tourism / local-oriented queries if travel or food industries
            if any(ind in self.industries for ind in ("travel", "food")):
                queries.append(f"best {kw_phrase} {geo}")
                queries.append(f"{geo} {kw_phrase} guide")

        # --- Individual keyword queries (if multiple keywords) ---
        if len(self.keywords) > 1:
            for kw in self.keywords:
                queries.append(f"{kw} startup company")

        # --- Expanded keyword queries (from abbreviation expansion) ---
        expanded = self.analysis.get("expanded_keywords", [])
        for exp_kw in expanded[:5]:
            queries.append(f"{exp_kw} company")
            queries.append(f"{exp_kw} startup")

        # Deduplicate
        seen = set()
        unique = []
        for q in queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique.append(q)

        return unique

    def _execute_searches(self, queries):
        """Execute search queries with caching."""
        engine = self.config.get("search", "engine", default="auto")
        max_per_query = self.config.get("search", "max_results_per_query", default=10)
        delay = self.config.get("search", "delay_between_searches", default=2)

        all_results = []

        for i, query in enumerate(queries):
            # Check cache first
            cached = self.cache.get("search", f"{engine}:{query}")
            if cached is not None:
                self.progress(f"  Query {i + 1}/{len(queries)}: {query} [cached]",
                              step="search", current=i + 1)
                all_results.extend(cached)
                continue

            self.progress(f"  Query {i + 1}/{len(queries)}: {query}",
                          step="search", current=i + 1)
            try:
                if engine == "serpapi":
                    results = self._search_serpapi(query, max_per_query)
                elif engine == "google":
                    results = self._search_google(query, max_per_query)
                elif engine == "ddgs":
                    results = self._search_ddgs(query, max_per_query)
                else:
                    results = self._search_auto(query, max_per_query)

                all_results.extend(results)
                self.cache.set("search", f"{engine}:{query}", results)
            except Exception as e:
                self.progress(f"  Search failed for '{query}': {e}", step="search")

            if i < len(queries) - 1:
                time.sleep(delay)

        return all_results

    def _search_auto(self, query, max_results):
        if DDGS is not None:
            try:
                results = self._search_ddgs(query, max_results)
                if results:
                    return results
            except Exception:
                pass
        if google_search is not None:
            try:
                results = self._search_google(query, max_results)
                if results:
                    return results
            except Exception:
                pass
        self.progress("  No search engine available.", step="search")
        return []

    def _search_ddgs(self, query, max_results):
        if DDGS is None:
            raise RuntimeError("ddgs not installed")
        results = []
        try:
            for item in DDGS().text(query, max_results=max_results):
                results.append({
                    "url": item.get("href", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("body", ""),
                    "query": query,
                })
        except Exception as e:
            self.progress(f"  DuckDuckGo error: {e}", step="search")
        return results

    def _search_google(self, query, max_results):
        if google_search is None:
            raise RuntimeError("googlesearch-python not installed")
        results = []
        try:
            for url in google_search(query, num_results=max_results):
                results.append({
                    "url": url, "title": "", "snippet": "", "query": query,
                })
        except Exception as e:
            self.progress(f"  Google error: {e}", step="search")
        return results

    def _search_serpapi(self, query, max_results):
        if SerpApiSearch is None:
            raise RuntimeError("SerpAPI not installed")
        api_key = self.config.get("search", "serpapi_key", default="")
        if not api_key:
            raise RuntimeError("SerpAPI key not configured")
        params = {"q": query, "api_key": api_key, "engine": "google", "num": max_results}
        data = SerpApiSearch(params).get_dict()
        return [
            {"url": item.get("link", ""), "title": item.get("title", ""),
             "snippet": item.get("snippet", ""), "query": query}
            for item in data.get("organic_results", [])
        ]

    def _extract_companies(self, raw_results):
        """Extract company information from search results."""
        companies = {}

        for result in raw_results:
            url = result.get("url", "")
            if not url:
                continue

            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Skip known irrelevant domains (check base domain too)
            ext = tldextract.extract(domain)
            base_domain = f"{ext.domain}.{ext.suffix}"
            if base_domain in SKIP_DOMAINS or domain in SKIP_DOMAINS:
                continue
            # Also skip subdomains of skip-listed sites
            if any(domain.endswith("." + skip) for skip in SKIP_DOMAINS):
                continue
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
                    "phone": "",
                    "social": {},
                    "description": "",
                    "meta_title": "",
                    "location": "",
                    "employee_count": "",
                    "technologies": [],
                }
            else:
                q = result.get("query", "")
                if q and q not in companies[domain]["matched_queries"]:
                    companies[domain]["matched_queries"].append(q)
                if result.get("title") and not companies[domain]["title"]:
                    companies[domain]["title"] = result["title"]
                if result.get("snippet") and not companies[domain]["snippet"]:
                    companies[domain]["snippet"] = result["snippet"]

        return list(companies.values())

    def _enrich_companies(self, companies):
        """Enrich company data by visiting their websites — deeper scraping with retry."""
        timeout = self.config.get("enrichment", "request_timeout", default=10)
        enriched = []

        for idx, company in enumerate(companies):
            domain_key = company["website_domain"]
            cached = self.cache.get("enrich", domain_key)
            if cached is not None:
                company.update(cached)
                enriched.append(company)
                self.progress(f"    {domain_key} [cached]", step="enrich", current=idx + 1)
                continue

            self.progress(f"    Scraping {domain_key}...", step="enrich", current=idx + 1)
            enrichment_data = {}

            resp = self._safe_get(company["website"], timeout=timeout)
            if resp is not None:
                html_text = resp.text
                soup = BeautifulSoup(html_text, "lxml")

                # --- Title ---
                if soup.title and soup.title.string:
                    enrichment_data["meta_title"] = soup.title.string.strip()[:200]

                # --- Meta description ---
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    enrichment_data["description"] = meta["content"].strip()[:500]

                # --- OG metadata ---
                og_desc = soup.find("meta", attrs={"property": "og:description"})
                if og_desc and og_desc.get("content") and not enrichment_data.get("description"):
                    enrichment_data["description"] = og_desc["content"].strip()[:500]

                # --- Emails ---
                page_emails = set(EMAIL_RE.findall(html_text))
                good_emails = []
                for email_addr in page_emails:
                    prefix = email_addr.split("@")[0].lower()
                    email_domain = email_addr.split("@")[1].lower()
                    tld_part = email_domain.rsplit(".", 1)[-1]
                    if prefix in JUNK_EMAIL_PREFIXES:
                        continue
                    if tld_part in _FAKE_EMAIL_TLDS:
                        continue
                    if ".." in email_domain:
                        continue
                    if email_domain == domain_key or email_domain.endswith("." + domain_key):
                        good_emails.insert(0, email_addr)
                    else:
                        good_emails.append(email_addr)
                enrichment_data["emails"] = good_emails[:5]

                # --- Phone numbers ---
                phones = PHONE_RE.findall(html_text)
                if phones:
                    valid_phones = [p.strip() for p in phones
                                    if len(re.sub(r'\D', '', p)) >= 10]
                    if valid_phones:
                        enrichment_data["phone"] = valid_phones[0]

                # --- Social links ---
                social = {}
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].lower()
                    if "linkedin.com/company" in href or "linkedin.com/in/" in href:
                        social["linkedin"] = a_tag["href"]
                    elif "twitter.com/" in href or "x.com/" in href:
                        if not any(skip in href for skip in ["/share", "/intent", "/widgets"]):
                            social["twitter"] = a_tag["href"]
                    elif "facebook.com/" in href:
                        if not any(skip in href for skip in ["/sharer", "/share", "/plugins"]):
                            social["facebook"] = a_tag["href"]
                enrichment_data["social"] = social

                # --- Location ---
                location = self._extract_location(soup, html_text)
                if location:
                    enrichment_data["location"] = location

                # --- Technology detection ---
                techs = self._detect_technologies(html_text, resp.headers)
                if techs:
                    enrichment_data["technologies"] = techs

                # --- Company name from title ---
                title_text = enrichment_data.get("meta_title", "")
                if title_text:
                    title_parts = re.split(r"\s*[\|–\-—:]\s*", title_text)
                    if title_parts:
                        candidate = title_parts[0].strip()
                        if 2 < len(candidate) < 60:
                            enrichment_data["name"] = candidate

                # --- /about page ---
                about_resp = self._safe_get(f"https://{domain_key}/about", timeout=5)
                if about_resp and len(about_resp.text) > 500:
                    about_soup = BeautifulSoup(about_resp.text, "lxml")
                    about_meta = about_soup.find("meta", attrs={"name": "description"})
                    if about_meta and about_meta.get("content"):
                        about_desc = about_meta["content"].strip()[:500]
                        if len(about_desc) > len(enrichment_data.get("description", "")):
                            enrichment_data["description"] = about_desc
                    about_emails = set(EMAIL_RE.findall(about_resp.text))
                    for e in about_emails:
                        p = e.split("@")[0].lower()
                        ed = e.split("@")[1].lower()
                        tld_part = ed.rsplit(".", 1)[-1]
                        if p not in JUNK_EMAIL_PREFIXES and tld_part not in _FAKE_EMAIL_TLDS and ".." not in ed and ed == domain_key:
                            if e not in enrichment_data.get("emails", []):
                                enrichment_data.setdefault("emails", []).append(e)

                # --- /contact page ---
                contact_resp = self._safe_get(f"https://{domain_key}/contact", timeout=5)
                if contact_resp:
                    contact_emails = set(EMAIL_RE.findall(contact_resp.text))
                    for e in contact_emails:
                        p = e.split("@")[0].lower()
                        ed = e.split("@")[1].lower()
                        tld_part = ed.rsplit(".", 1)[-1]
                        if p not in JUNK_EMAIL_PREFIXES and tld_part not in _FAKE_EMAIL_TLDS and ".." not in ed and ed == domain_key:
                            if e not in enrichment_data.get("emails", []):
                                enrichment_data.setdefault("emails", []).append(e)
                    contact_phones = PHONE_RE.findall(contact_resp.text)
                    if contact_phones and not enrichment_data.get("phone"):
                        valid = [p.strip() for p in contact_phones
                                 if len(re.sub(r'\D', '', p)) >= 10]
                        if valid:
                            enrichment_data["phone"] = valid[0]

            company.update(enrichment_data)
            self.cache.set("enrich", domain_key, enrichment_data)
            enriched.append(company)
            time.sleep(0.3)

        return enriched

    def _extract_location(self, soup, html_text):
        """Try to extract company location from structured data or page content."""
        # JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                addr = data.get("address", {})
                if isinstance(addr, dict):
                    parts = [
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                        addr.get("addressCountry", ""),
                    ]
                    loc = ", ".join(p for p in parts if p)
                    if loc:
                        return loc
            except Exception:
                pass

        # Schema.org itemprop
        locality = soup.find(attrs={"itemprop": "addressLocality"})
        region = soup.find(attrs={"itemprop": "addressRegion"})
        if locality:
            parts = [locality.get_text(strip=True)]
            if region:
                parts.append(region.get_text(strip=True))
            return ", ".join(parts)

        return ""

    def _detect_technologies(self, html_text, headers):
        """Detect technologies used on the website."""
        techs = []
        lower_html = html_text.lower()

        for tech_name, patterns in TECH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lower_html):
                    techs.append(tech_name)
                    break

        # Server header
        server = headers.get("server", "").lower()
        if "nginx" in server:
            techs.append("Nginx")
        elif "apache" in server:
            techs.append("Apache")
        elif "cloudflare" in server:
            techs.append("Cloudflare")

        # X-Powered-By
        powered_by = headers.get("x-powered-by", "")
        if powered_by:
            techs.append(powered_by.split("/")[0].strip())

        return list(set(techs))

    def _check_similar_domains(self):
        """Check who owns similar domain names across TLDs."""
        name = self.analysis["name"]
        tld = self.analysis["tld"]
        alt_tlds = ["com", "net", "org", "io", "co", "ai", "app", "dev", "tech", "us"]
        similar = []

        for alt_tld in alt_tlds:
            if alt_tld == tld:
                continue
            alt_domain = f"{name}.{alt_tld}"

            cached = self.cache.get("similar", alt_domain)
            if cached is not None:
                if cached:  # non-empty means we found something
                    similar.append(cached)
                continue

            try:
                try:
                    dns.resolver.resolve(alt_domain, "A")
                except Exception:
                    self.cache.set("similar", alt_domain, {})
                    continue

                result = {
                    "name": self._domain_to_company_name(alt_domain),
                    "website": f"https://{alt_domain}",
                    "website_domain": alt_domain,
                    "url_found": f"https://{alt_domain}",
                    "title": "", "snippet": "",
                    "matched_queries": [f"Similar domain: {alt_domain}"],
                    "emails": [], "phone": "",
                    "social": {}, "description": "",
                    "meta_title": "", "location": "",
                    "employee_count": "", "technologies": [],
                    "is_similar_domain": True,
                }

                try:
                    resp = self._session.get(f"https://{alt_domain}", timeout=5, allow_redirects=True)
                    soup = BeautifulSoup(resp.text, "lxml")
                    if soup.title and soup.title.string:
                        result["title"] = soup.title.string.strip()[:200]
                        result["meta_title"] = result["title"]
                    meta = soup.find("meta", attrs={"name": "description"})
                    if meta and meta.get("content"):
                        result["description"] = meta["content"].strip()[:500]
                        result["snippet"] = result["description"]

                    final_domain = urlparse(resp.url).netloc.lower()
                    if final_domain.startswith("www."):
                        final_domain = final_domain[4:]
                    result["website"] = f"https://{final_domain}"
                    result["website_domain"] = final_domain

                    if result["title"]:
                        parts = re.split(r"\s*[\|–\-—]\s*", result["title"])
                        if parts and 2 < len(parts[0].strip()) < 60:
                            result["name"] = parts[0].strip()
                except Exception:
                    pass

                similar.append(result)
                self.cache.set("similar", alt_domain, result)

            except Exception:
                continue

        return similar

    def _check_domain_variations(self):
        """Check branded domain variations (getX, myX, useX, etc.)."""
        name = self.analysis["name"]
        prefixes = ["get", "my", "use", "go", "try", "the", "hey", "one", "meet", "join"]
        suffixes = ["app", "hq", "io", "now", "hub", "labs", "tech", "ai", "dev", "pro", "plus", "world"]
        check_tld = "com"
        results = []

        variations = []
        for pfx in prefixes:
            variations.append(f"{pfx}{name}.{check_tld}")
        for sfx in suffixes:
            variations.append(f"{name}{sfx}.{check_tld}")
        # Hyphenated
        if len(self.keywords) >= 2:
            variations.append(f"{'-'.join(self.keywords)}.{check_tld}")

        for var_domain in variations:
            cached = self.cache.get("variation", var_domain)
            if cached is not None:
                if cached:
                    results.append(cached)
                continue

            try:
                dns.resolver.resolve(var_domain, "A")
            except Exception:
                self.cache.set("variation", var_domain, {})
                continue

            result = {
                "name": self._domain_to_company_name(var_domain),
                "website": f"https://{var_domain}",
                "website_domain": var_domain,
                "url_found": f"https://{var_domain}",
                "title": "", "snippet": "",
                "matched_queries": [f"Domain variation: {var_domain}"],
                "emails": [], "phone": "",
                "social": {}, "description": "",
                "meta_title": "", "location": "",
                "employee_count": "", "technologies": [],
                "is_similar_domain": True,
            }

            resp = self._safe_get(f"https://{var_domain}", timeout=5)
            if resp is not None:
                soup = BeautifulSoup(resp.text, "lxml")
                if soup.title and soup.title.string:
                    result["title"] = soup.title.string.strip()[:200]
                    result["meta_title"] = result["title"]
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    result["description"] = meta["content"].strip()[:500]
                    result["snippet"] = result["description"]

                final_domain = urlparse(resp.url).netloc.lower()
                if final_domain.startswith("www."):
                    final_domain = final_domain[4:]
                result["website"] = f"https://{final_domain}"
                result["website_domain"] = final_domain

                if result["title"]:
                    parts = re.split(r"\s*[\|–\-—]\s*", result["title"])
                    if parts and 2 < len(parts[0].strip()) < 60:
                        result["name"] = parts[0].strip()

            results.append(result)
            self.cache.set("variation", var_domain, result)

        return results

    def _discover_contacts(self, companies):
        """Try to find contact emails by checking common email patterns against MX.
        Only probes top candidates to avoid excessive HTTP requests."""
        max_probe = min(20, len(companies))
        to_probe = companies[:max_probe]
        rest = companies[max_probe:]

        for idx, company in enumerate(to_probe):
            domain_key = company.get("website_domain", "")
            if not domain_key or company.get("emails"):
                continue

            self.progress(f"    Probing contacts for {domain_key}...",
                          step="contacts", current=idx + 1)

            # Check if domain has MX records (accepts email)
            try:
                dns.resolver.resolve(domain_key, "MX")
            except Exception:
                continue

            # Try common contact page paths
            for path in ["/contact", "/contact-us", "/about", "/about-us", "/team"]:
                resp = self._safe_get(f"https://{domain_key}{path}", timeout=5)
                if resp is not None:
                    found = set(EMAIL_RE.findall(resp.text))
                    for email_addr in found:
                        prefix = email_addr.split("@")[0].lower()
                        email_domain = email_addr.split("@")[1].lower()
                        tld_part = email_domain.rsplit(".", 1)[-1]
                        if prefix not in JUNK_EMAIL_PREFIXES and tld_part not in _FAKE_EMAIL_TLDS and ".." not in email_domain and email_domain == domain_key:
                            if email_addr not in company["emails"]:
                                company["emails"].append(email_addr)
                    if company["emails"]:
                        break

                    # Also grab phones
                    if not company.get("phone"):
                        phones = PHONE_RE.findall(resp.text)
                        valid = [p.strip() for p in phones
                                 if len(re.sub(r'\D', '', p)) >= 10]
                        if valid:
                            company["phone"] = valid[0]

        return to_probe + rest

    @staticmethod
    def _domain_to_company_name(domain):
        ext = tldextract.extract(domain)
        name = ext.domain
        parts = re.split(r"[-_]", name)
        return " ".join(p.capitalize() for p in parts if p)
