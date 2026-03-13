# Domain Seller v2

A CLI tool that analyzes domain names from your portfolio and identifies **real potential buyers** using live data from WHOIS, DNS, DuckDuckGo search, and web scraping.

## Features

- **Domain Analysis** — Extracts keywords, identifies industries, checks WHOIS/DNS, estimates value
- **Deep Buyer Research** — 30+ search queries per domain across DuckDuckGo, Google, or SerpAPI
- **Similar Domain Detection** — Checks who owns the same name under 10 alternate TLDs
- **Company Enrichment** — Scrapes homepages, /about, /contact for emails, phone, social, tech stack
- **Contact Discovery** — Probes MX records and common pages to find real email addresses
- **Technology Detection** — Identifies WordPress, Shopify, React, Next.js, and 15+ other stacks
- **Lead Scoring** — 0-100 relevance scoring with name match, keyword overlap, domain signals
- **Outreach Templates** — 4 personalized email templates (standard, premium, startup, similar domain)
- **Batch Mode** — Process multiple domains in one run
- **Interactive Mode** — Browse, inspect, and email leads after results
- **HTML Reports** — Beautiful standalone dark-themed report with filtering and stats
- **Search Caching** — File-based TTL cache to avoid redundant lookups
- **Export** — CSV or JSON with all lead data

## Quick Start

### 1. Install Dependencies

```bash
cd sellerdomain
pip install -r requirements.txt
```

### 2. Run It

```bash
python run.py healthtrack.com
```

That's it. No API keys required for basic usage.

### 3. (Optional) Better Results with SerpAPI

For more reliable search results, get a free SerpAPI key at [serpapi.com](https://serpapi.com) (100 free searches/month):

```bash
python run.py healthtrack.com --serpapi-key YOUR_KEY
```

Or set it as an environment variable:

```bash
set SERPAPI_KEY=your_key_here
python run.py healthtrack.com
```

## Usage

```
Usage: python run.py [OPTIONS] DOMAINS...

Arguments:
  DOMAINS  One or more domain names to sell (e.g., healthtrack.com cloudpay.io)

Options:
  --analyze-only       Only analyze the domain, skip buyer research
  --max-leads N        Maximum number of leads per domain
  --export-file FILE   Export results to file (.csv or .json)
  --html FILE          Generate standalone HTML report
  --serpapi-key KEY    SerpAPI key for better search results
  --config FILE        Path to config.yaml file
  --verbose            Show detailed progress during research
  --show-email         Show sample outreach email for top lead
  --interactive, -i    Enter interactive mode after results
  --no-cache           Disable search result caching
  --clear-cache        Clear all cached data and exit
  --help               Show help message
```

## Examples

```bash
# Basic usage - analyze and find buyers
python run.py cloudpay.com

# Just analyze the domain (no buyer search)
python run.py cloudpay.com --analyze-only

# Find buyers with detailed progress and outreach email
python run.py cloudpay.com --verbose --show-email

# Export results to CSV + HTML report
python run.py cloudpay.com --export-file leads.csv --html report.html

# Batch mode - process multiple domains at once
python run.py cloudpay.com healthtrack.com databridge.io

# Interactive mode - browse, inspect, email leads
python run.py cloudpay.com -i

# Limit results
python run.py cloudpay.com --max-leads 10

# Use SerpAPI for better results
python run.py cloudpay.com --serpapi-key sk-xxxxx

# Clear search cache
python run.py --clear-cache dummy.com
```

### Interactive Mode Commands

Once in interactive mode (`-i`), use:
- `view N` — Show detailed info for lead #N
- `email N` — Generate outreach email for lead #N
- `emails N` — Show all 4 email templates for lead #N
- `list` — Re-display the leads table
- `export FILE` — Export to CSV/JSON
- `html FILE` — Generate HTML report
- `quit` — Exit

## Configuration

Copy `config.yaml.example` to `config.yaml` for persistent settings:

```bash
copy config.yaml.example config.yaml
```

Edit `config.yaml` to set:
- Search engine and API keys
- Scraping settings and timeouts
- Lead scoring thresholds
- Auto-export preferences

## How It Works

1. **Domain Analysis**: Parses the domain name, extracts keywords using word segmentation (e.g., `healthtrack` → `health` + `track`), identifies matching industries, pulls WHOIS/DNS data, and estimates value based on length, TLD, keyword quality, industry demand, and domain age.

2. **Buyer Research**: Constructs 30+ smart search queries based on keywords and industries (e.g., "health tracking company", "health track startup", "healthcare startup funding", "health track series A"), executes them via DuckDuckGo, and extracts unique company results. Searches are cached to speed up repeat runs.

3. **Similar Domain Check**: Checks if the same domain name exists under 10 alternate TLDs (.net, .io, .ai, .co, .dev, .app, etc.) — companies using those are strong buyer candidates.

4. **Company Enrichment**: Visits each company's homepage, /about, and /contact pages to extract business name, description, contact emails, phone numbers, social media links, location, and technology stack.

5. **Contact Discovery**: For companies without emails, probes MX records and scrapes common contact paths to find real email addresses.

6. **Lead Scoring**: Scores each lead 0-100 based on domain name match (30pts), keyword relevance (25pts), query breadth (15pts), similar domain ownership (15pts), and contact availability (15pts).

7. **Report & Outreach**: Displays ranked results in a rich table, generates HTML reports with filtering, and creates personalized email templates based on each lead's profile.

## Data Sources

All data comes from **real, live sources**:
- **WHOIS** — Domain registration data via `python-whois`
- **DNS** — Active DNS records via `dnspython`
- **DuckDuckGo** — Live search results via `ddgs` (free, no API key needed)
- **SerpAPI** — Optional premium search via Google (100 free searches/month)
- **Web Scraping** — Company websites scraped for contact info, tech stack, social links
- **Domain Resolution** — Direct DNS/HTTP checks on similar domains

## Project Structure

```
sellerdomain/
├── run.py                 # Entry point
├── requirements.txt       # Python dependencies
├── config.yaml.example    # Example configuration
├── README.md
└── core/
    ├── __init__.py
    ├── config.py          # Configuration management
    ├── analyzer.py        # Domain analysis (WHOIS, DNS, keywords, value)
    ├── researcher_v2.py   # Buyer research (search, scraping, caching)
    ├── lead_scorer.py     # Lead scoring and ranking
    ├── exporter.py        # CSV/JSON export
    ├── outreach.py        # Email template generation
    ├── cache.py           # File-based search result caching
    ├── html_report.py     # Standalone HTML report generator
    └── cli_v2.py          # Rich CLI with progress, batch, interactive
```

## Requirements

- Python 3.8+
- Internet connection (for live data lookups)
- No API keys required for basic usage (optional SerpAPI key for better results)
