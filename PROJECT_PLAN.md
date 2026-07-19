# Project Plan: Software Company & Job Listings Aggregator

## 1. Project Goal

Build a Python CLI tool that:

1. Takes a **city name** as input (e.g., `"Mumbai"`).
2. Discovers **software development companies** located in that city using Google Places API, Clutch.co scraping, and Naukri.com scraping.
3. For each discovered company, finds their **careers/jobs page** URL automatically.
4. Scrapes **software engineering / developer job listings** from each careers page (using ATS-specific scrapers for Greenhouse, Lever, Workday, and a generic fallback).
5. Filters, normalizes, de-duplicates, and exports everything into a structured **CSV file** with enough detail to actually apply (title, description, skills, apply link, etc.).

**Explicitly out of scope:** Direct LinkedIn scraping (against ToS, aggressive bot detection, legal risk). Use LinkedIn only manually/for verification, never automate it.

---

## 2. High-Level Architecture

```
City Name Input (CLI argument or interactive prompt)
      │
      ▼
[Phase 1] Company Discovery ──► output/companies.csv
      │
      ▼
[Phase 2] Careers Page Locator ──► output/companies_with_careers_url.csv
      │
      ▼
[Phase 3] Job Scraper (ATS-based + generic) ──► output/raw_jobs.json
      │
      ▼
[Phase 4] Filter + Normalize + Dedup
      │
      ▼
[Phase 5] Final CSV Export ──► output/jobs_<city>_<YYYY-MM-DD>.csv
```

Each phase is a separate, independently runnable module. Every phase reads its input from the previous phase's saved file (not just in-memory), so any phase can be re-run in isolation during development/debugging.

---

## 3. Folder Structure

```
jobsearch/
├── config/
│   ├── settings.yaml              # city, keywords, rate limits, API keys reference
│   └── ats_patterns.yaml          # known ATS URL patterns (Greenhouse, Lever, Workday)
│
├── discovery/
│   ├── __init__.py
│   ├── google_places_discovery.py # Phase 1 - Google Places API method
│   ├── clutch_discovery.py        # Phase 1 - Clutch.co scraper (Playwright-based)
│   └── naukri_discovery.py        # Phase 1 - Naukri companies scraper
│
├── careers_finder/
│   ├── __init__.py
│   └── locate_careers_page.py     # Phase 2 - find careers URL + detect ATS type
│
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py            # abstract base class all scrapers inherit
│   ├── greenhouse_scraper.py      # Phase 3 - Greenhouse JSON API scraper
│   ├── lever_scraper.py           # Phase 3 - Lever JSON API scraper
│   ├── workday_scraper.py         # Phase 3 - Workday hidden JSON API scraper
│   └── generic_scraper.py         # Phase 3 - fallback BS4 + Playwright scraper
│
├── processing/
│   ├── __init__.py
│   ├── filter_jobs.py             # Phase 4 - keyword filter for dev roles
│   ├── dedup.py                   # Phase 4 - remove duplicate entries
│   └── normalize.py               # Phase 4 - clean/standardize fields
│
├── utils/
│   ├── __init__.py
│   ├── rate_limiter.py            # sleep/backoff between requests
│   ├── http_client.py             # requests wrapper with retries + headers
│   ├── logger.py                  # centralized logging
│   └── csv_writer.py              # final CSV export logic
│
├── output/                        # all intermediate + final outputs go here
│   ├── companies.csv
│   ├── companies_with_careers_url.csv
│   ├── raw_jobs.json
│   ├── failed_scrapes.csv         # companies that failed scraping (for manual review)
│   └── jobs_<city>_<date>.csv     # FINAL DELIVERABLE
│
├── main.py                        # orchestrates all phases end-to-end
├── requirements.txt
├── .env                           # API keys (gitignored)
├── .gitignore
└── README.md
```

---

## 4. Tech Stack & Dependencies

### requirements.txt

```txt
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.2.2
pandas==2.2.2
playwright==1.45.0
tenacity==8.3.0
pyyaml==6.0.1
python-dotenv==1.0.1
tqdm==4.66.4
googlemaps==4.10.0
```

### Post-install step

```bash
pip install -r requirements.txt
playwright install chromium
```

### .gitignore

```
.env
output/
__pycache__/
*.pyc
.venv/
```

---

## 5. Configuration Files (Exact Content)

### config/settings.yaml

```yaml
# Target city — overridden by CLI argument if provided
city: "Mumbai"

# Keywords used to filter job titles in Phase 4
job_title_keywords:
  - "software engineer"
  - "software developer"
  - "backend"
  - "back-end"
  - "frontend"
  - "front-end"
  - "full stack"
  - "fullstack"
  - "sde"
  - "python developer"
  - "java developer"
  - "node developer"
  - "devops"
  - "site reliability"
  - "sre"
  - "mobile developer"
  - "android developer"
  - "ios developer"
  - "data engineer"
  - "qa engineer"
  - "sdet"
  - "cloud engineer"
  - "machine learning engineer"
  - "platform engineer"

# Google Places API query templates (used in Phase 1)
discovery_queries:
  - "software development company in {city}"
  - "IT company in {city}"
  - "technology startup in {city}"

# Rate limiting
rate_limit:
  min_delay_seconds: 1.5
  max_delay_seconds: 3.0

# Retry config (used by tenacity)
retry:
  max_attempts: 3
  initial_wait_seconds: 2
  max_wait_seconds: 30

# HTTP client
http:
  timeout_seconds: 15
  user_agent: "JobSearchBot/1.0 (Educational project; contact: your-email@example.com)"

# Phase 2 - Careers page detection
careers_page:
  url_keywords:
    - "career"
    - "careers"
    - "jobs"
    - "join-us"
    - "join"
    - "work-with-us"
    - "hiring"
    - "openings"
    - "opportunities"
  fallback_paths:
    - "/careers"
    - "/jobs"
    - "/careers/"
    - "/about/careers"
    - "/join-us"
    - "/work-with-us"
    - "/en/careers"

# Job description summary truncation length
description_summary_max_chars: 300
```

### config/ats_patterns.yaml

```yaml
# Maps URL substrings to ATS type identifiers.
# Used in Phase 2 to detect which scraper to route each company to in Phase 3.
# Order matters — first match wins.

patterns:
  - substring: "greenhouse.io"
    ats_type: "greenhouse"
  - substring: "boards.greenhouse.io"
    ats_type: "greenhouse"
  - substring: "lever.co"
    ats_type: "lever"
  - substring: "jobs.lever.co"
    ats_type: "lever"
  - substring: "myworkdayjobs.com"
    ats_type: "workday"
  - substring: ".wd1.myworkdayjobs.com"
    ats_type: "workday"
  - substring: ".wd5.myworkdayjobs.com"
    ats_type: "workday"
  - substring: "workday.com"
    ats_type: "workday"
  - substring: "ashbyhq.com"
    ats_type: "generic"
  - substring: "recruitee.com"
    ats_type: "generic"
  - substring: "breezy.hr"
    ats_type: "generic"
  - substring: "smartrecruiters.com"
    ats_type: "generic"
  - substring: "bamboohr.com"
    ats_type: "generic"

# Default if no pattern matches
default_ats_type: "generic"
```

### .env

```
GOOGLE_PLACES_API_KEY=your_google_places_api_key_here
GOOGLE_CSE_API_KEY=your_google_cse_api_key_here
GOOGLE_CSE_ID=your_google_cse_cx_id_here
```

---

## 6. Data Schemas (Exact Column Definitions)

### 6a. `output/companies.csv` (Phase 1 output)

| Column           | Type   | Description                                      | Example                         |
|------------------|--------|--------------------------------------------------|---------------------------------|
| `company_name`   | str    | Name of the company                              | `"Infosys"`                     |
| `website`        | str    | Company website URL (normalized, no trailing `/`)| `"https://infosys.com"`         |
| `domain`         | str    | Extracted domain for dedup (lowercase, no `www.`)| `"infosys.com"`                 |
| `city`           | str    | Target city                                      | `"Mumbai"`                      |
| `address`        | str    | Full address if available, else empty string      | `"Plot 1, Hinjawadi, Pune"`     |
| `industry`       | str    | Industry/category if available                   | `"IT Services"`                 |
| `employee_count` | str    | Employee count range if available                | `"10,000+"`                     |
| `rating`         | float  | Google rating if from Places API, else `NaN`     | `4.2`                           |
| `source`         | str    | Which discovery method found this company        | `"google_places"` / `"clutch"` / `"naukri"` |
| `discovered_at`  | str    | ISO 8601 timestamp                               | `"2025-01-15T10:30:00Z"`       |

### 6b. `output/companies_with_careers_url.csv` (Phase 2 output)

All columns from `companies.csv` plus:

| Column          | Type   | Description                                              | Example                                      |
|-----------------|--------|----------------------------------------------------------|----------------------------------------------|
| `careers_url`   | str    | Absolute URL to careers/jobs page, or `"NOT_FOUND"`      | `"https://boards.greenhouse.io/infosys"`     |
| `ats_type`      | str    | Detected ATS type                                        | `"greenhouse"` / `"lever"` / `"workday"` / `"generic"` |
| `ats_token`     | str    | Extracted ATS-specific company token (for API calls)     | `"infosys"` (from greenhouse URL slug)       |

### 6c. `output/raw_jobs.json` (Phase 3 output)

A JSON file containing a flat list of job dicts. Each dict has:

```json
{
  "company_name": "Infosys",
  "company_website": "https://infosys.com",
  "company_city": "Mumbai",
  "job_title": "Senior Software Engineer",
  "job_department": "Engineering",
  "experience_required": "",
  "job_location": "Mumbai, India",
  "employment_type": "Full-time",
  "skills_required": "Python, AWS, Kubernetes",
  "job_description_full": "We are looking for a Senior Software Engineer...",
  "posted_date": "2025-01-10",
  "apply_link": "https://boards.greenhouse.io/infosys/jobs/12345",
  "ats_type": "greenhouse",
  "scraped_at": "2025-01-15T10:45:00Z"
}
```

### 6d. `output/jobs_<city>_<date>.csv` (Phase 5 — FINAL OUTPUT)

| Column                    | Type   | Description                                  |
|---------------------------|--------|----------------------------------------------|
| `company_name`            | str    | Company name                                 |
| `company_website`         | str    | Company homepage URL                         |
| `company_city`            | str    | City the company is in                       |
| `company_industry`        | str    | Industry if available                        |
| `job_title`               | str    | Job title                                    |
| `job_department`          | str    | Department/team name                         |
| `experience_required`     | str    | Experience requirement if listed             |
| `job_location`            | str    | Job location (may differ from company HQ)    |
| `employment_type`         | str    | Full-time / Intern / Contract / Part-time    |
| `skills_required`         | str    | Comma-separated skills if listed             |
| `job_description_summary` | str    | Truncated to 300 chars                       |
| `job_description_full`    | str    | Full description text                        |
| `posted_date`             | str    | ISO date (YYYY-MM-DD) or empty               |
| `apply_link`              | str    | Direct URL to apply                          |
| `ats_type`                | str    | greenhouse / lever / workday / generic       |
| `scraped_at`              | str    | ISO 8601 timestamp of when we scraped it     |

### 6e. `output/failed_scrapes.csv`

| Column          | Type | Description                        |
|-----------------|------|------------------------------------|
| `company_name`  | str  | Company that failed                |
| `careers_url`   | str  | URL we tried to scrape             |
| `ats_type`      | str  | ATS type we attempted              |
| `error_message` | str  | The exception/error message        |
| `failed_at`     | str  | ISO 8601 timestamp                 |

---

## 7. Phase-by-Phase Implementation (Complete Code Specifications)

---

### PHASE 1 — Company Discovery (`discovery/`)

**Goal:** Produce `output/companies.csv`.

#### 7.1a. `discovery/google_places_discovery.py`

**Purpose:** Use the Google Places API (Text Search) to find software companies in a city.

**Exact implementation:**

```python
"""
discovery/google_places_discovery.py

Uses the googlemaps Python client to search for software companies via
Google Places Text Search API.
"""
import os
import time
import logging
from datetime import datetime, timezone

import googlemaps
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def discover_companies_google_places(city: str, queries: list[str]) -> list[dict]:
    """
    Discover software companies in the given city using Google Places API.

    Args:
        city: Target city name, e.g. "Mumbai"
        queries: List of query templates with {city} placeholder,
                 e.g. ["software development company in {city}"]

    Returns:
        List of dicts matching the companies.csv schema.

    Raises:
        ValueError: If GOOGLE_PLACES_API_KEY env var is not set.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY not found in .env file")

    gmaps = googlemaps.Client(key=api_key)
    all_companies = []
    seen_place_ids = set()  # dedup within this source

    for query_template in queries:
        query = query_template.format(city=city)
        logger.info(f"Google Places search: '{query}'")

        try:
            results = gmaps.places(query=query)
        except Exception as e:
            logger.error(f"Google Places API error for query '{query}': {e}")
            continue

        places = results.get("results", [])

        # Paginate — Google returns up to 60 results across 3 pages
        while "next_page_token" in results:
            time.sleep(2)  # REQUIRED: token needs ~2s to become valid
            try:
                results = gmaps.places(
                    query=query, page_token=results["next_page_token"]
                )
                places.extend(results.get("results", []))
            except Exception as e:
                logger.warning(f"Pagination error: {e}")
                break

        for place in places:
            place_id = place.get("place_id", "")
            if place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)

            # Extract website from Place Details (not in Text Search response)
            website = ""
            try:
                detail = gmaps.place(place_id, fields=["website"])
                website = detail.get("result", {}).get("website", "")
            except Exception:
                pass

            if not website:
                continue  # Skip companies without a website

            company = {
                "company_name": place.get("name", ""),
                "website": website.rstrip("/"),
                "domain": _extract_domain(website),
                "city": city,
                "address": place.get("formatted_address", ""),
                "industry": "Software / IT",  # Places API doesn't give fine industry
                "employee_count": "",
                "rating": place.get("rating", None),
                "source": "google_places",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
            all_companies.append(company)

    logger.info(
        f"Google Places: found {len(all_companies)} companies in {city}"
    )
    return all_companies


def _extract_domain(url: str) -> str:
    """
    Extract a normalized domain from a URL.
    'https://www.infosys.com/about/' -> 'infosys.com'
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
```

**Key notes:**
- The `googlemaps` Python client handles auth + URL encoding automatically.
- `gmaps.places()` uses the Text Search endpoint which costs $0.032/call (well within the free $200/month credit).
- The `place()` call to get website costs an additional $0.017/call — needed because Text Search does not return `website` by default.
- Rate: ~2s between pagination calls is a Google hard requirement.

---

#### 7.1b. `discovery/clutch_discovery.py`

**Purpose:** Scrape Clutch.co for software development companies in a city.

**Critical note from research:** Clutch.co has aggressive anti-bot detection (403 errors with plain `requests`). **Must use Playwright** with a realistic browser fingerprint.

```python
"""
discovery/clutch_discovery.py

Scrapes Clutch.co company listings for a city.
Uses Playwright because Clutch blocks plain HTTP requests (403).
"""
import logging
import re
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def discover_companies_clutch(city: str, max_pages: int = 5) -> list[dict]:
    """
    Scrape Clutch.co for software development companies in a city.

    Args:
        city: Target city name, e.g. "Mumbai"
        max_pages: Maximum number of listing pages to scrape (each page has ~15 companies)

    Returns:
        List of dicts matching the companies.csv schema.
    """
    # Clutch URL slug: lowercase, spaces -> hyphens
    city_slug = city.lower().strip().replace(" ", "-")
    base_url = f"https://clutch.co/developers/{city_slug}"

    companies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for page_num in range(max_pages):
            url = base_url if page_num == 0 else f"{base_url}?page={page_num}"
            logger.info(f"Clutch: fetching {url}")

            try:
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)  # let dynamic content load
            except Exception as e:
                logger.warning(f"Clutch page load failed: {e}")
                break

            # Extract company cards
            # Clutch uses provider cards with class patterns like:
            #   .provider-row, .provider-info, .company_info
            # NOTE: Clutch frequently changes class names. The selectors below
            # are current as of early 2025. If they break, inspect the page
            # in a browser and update the selectors.
            cards = page.query_selector_all(
                "li[data-content='provider'] , .provider-row"
            )

            if not cards:
                # Try alternative selector
                cards = page.query_selector_all("[class*='provider']")

            if not cards:
                logger.warning(
                    f"No company cards found on {url} — Clutch may have "
                    "changed their HTML structure. Inspect manually."
                )
                break

            for card in cards:
                try:
                    # Company name
                    name_el = card.query_selector(
                        "h3 a, .company_info a, [class*='company-name'] a"
                    )
                    name = name_el.inner_text().strip() if name_el else ""

                    # Website link (Clutch links to company profile, not their site)
                    # We'll get the actual website from the profile or skip
                    website_el = card.query_selector(
                        "a[href*='website'], a[class*='website']"
                    )
                    website = ""
                    if website_el:
                        website = website_el.get_attribute("href") or ""
                    elif name_el:
                        # Often the company profile page has the website
                        profile_href = name_el.get_attribute("href") or ""
                        if profile_href and not profile_href.startswith("http"):
                            profile_href = f"https://clutch.co{profile_href}"
                        website = profile_href  # We'll resolve to real site in Phase 2

                    # Location
                    loc_el = card.query_selector(
                        ".locality, [class*='location']"
                    )
                    address = loc_el.inner_text().strip() if loc_el else city

                    # Employee count
                    emp_el = card.query_selector(
                        "[class*='employees'], [class*='size']"
                    )
                    employee_count = emp_el.inner_text().strip() if emp_el else ""

                    if name:
                        companies.append({
                            "company_name": name,
                            "website": website.rstrip("/"),
                            "domain": _extract_domain(website) if website else "",
                            "city": city,
                            "address": address,
                            "industry": "Software Development",
                            "employee_count": employee_count,
                            "rating": None,
                            "source": "clutch",
                            "discovered_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as e:
                    logger.debug(f"Error parsing Clutch card: {e}")
                    continue

            # Check if there's a next page
            next_btn = page.query_selector(
                "a[rel='next'], .page-link-next, [class*='next']"
            )
            if not next_btn:
                break

        browser.close()

    logger.info(f"Clutch: found {len(companies)} companies in {city}")
    return companies


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
```

---

#### 7.1c. `discovery/naukri_discovery.py`

**Purpose:** Scrape Naukri.com company directory for IT companies hiring in a city.

```python
"""
discovery/naukri_discovery.py

Scrapes Naukri.com company directory filtered by IT/Software + city.
Naukri is useful because it lists companies actively hiring.
Uses Playwright since Naukri renders content dynamically.
"""
import logging
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def discover_companies_naukri(city: str, max_pages: int = 5) -> list[dict]:
    """
    Discover software companies from Naukri.com company directory.

    Args:
        city: Target city name
        max_pages: Max pages to scrape

    Returns:
        List of dicts matching companies.csv schema.
    """
    # Naukri company search URL with IT industry filter
    city_slug = city.lower().replace(" ", "-")
    base_url = (
        f"https://www.naukri.com/companies-hiring-in-{city_slug}"
        f"?industryType=IT+-+Software"
    )

    companies = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"{base_url}&pageNo={page_num}" if page_num > 1 else base_url
            logger.info(f"Naukri: fetching {url}")

            try:
                page.goto(url, timeout=20000, wait_until="networkidle")
                page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"Naukri page load failed: {e}")
                break

            # Company cards on Naukri use patterns like:
            #   .comp-card, .company-card, article[class*='company']
            cards = page.query_selector_all(
                ".comp-card, [class*='companyCard'], article"
            )

            if not cards:
                logger.warning(f"No cards found on Naukri page {page_num}")
                break

            for card in cards:
                try:
                    name_el = card.query_selector(
                        "a[class*='title'], h2, [class*='compName']"
                    )
                    name = name_el.inner_text().strip() if name_el else ""

                    # Naukri shows company profile links, not direct websites
                    link_el = card.query_selector("a[href]")
                    profile_url = ""
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        if not href.startswith("http"):
                            href = f"https://www.naukri.com{href}"
                        profile_url = href

                    if name:
                        companies.append({
                            "company_name": name,
                            "website": profile_url,  # Will resolve in Phase 2
                            "domain": "",
                            "city": city,
                            "address": city,
                            "industry": "IT / Software",
                            "employee_count": "",
                            "rating": None,
                            "source": "naukri",
                            "discovered_at": datetime.now(timezone.utc).isoformat(),
                        })
                except Exception as e:
                    logger.debug(f"Error parsing Naukri card: {e}")
                    continue

        browser.close()

    logger.info(f"Naukri: found {len(companies)} companies in {city}")
    return companies
```

#### 7.1d. `discovery/__init__.py` — Phase 1 Orchestrator

```python
"""
discovery/__init__.py

Orchestrates all discovery methods, merges + deduplicates results,
and saves to output/companies.csv.
"""
import logging
import os
from pathlib import Path

import pandas as pd

from .google_places_discovery import discover_companies_google_places
from .clutch_discovery import discover_companies_clutch
from .naukri_discovery import discover_companies_naukri

logger = logging.getLogger(__name__)


def run_phase1_discovery(city: str, config: dict) -> pd.DataFrame:
    """
    Run all discovery methods, merge, dedup by domain, save CSV.

    Args:
        city: Target city name
        config: Parsed settings.yaml dict

    Returns:
        DataFrame of discovered companies.
    """
    all_companies = []

    # Method A: Google Places
    try:
        queries = config.get("discovery_queries", [
            "software development company in {city}"
        ])
        gp_companies = discover_companies_google_places(city, queries)
        all_companies.extend(gp_companies)
    except Exception as e:
        logger.error(f"Google Places discovery failed: {e}")

    # Method B: Clutch
    try:
        clutch_companies = discover_companies_clutch(city)
        all_companies.extend(clutch_companies)
    except Exception as e:
        logger.error(f"Clutch discovery failed: {e}")

    # Method C: Naukri
    try:
        naukri_companies = discover_companies_naukri(city)
        all_companies.extend(naukri_companies)
    except Exception as e:
        logger.error(f"Naukri discovery failed: {e}")

    if not all_companies:
        logger.warning("No companies discovered from any source!")
        return pd.DataFrame()

    df = pd.DataFrame(all_companies)

    # Deduplicate by normalized domain (keep first occurrence)
    # Companies from Naukri/Clutch may not have a domain yet — keep them all
    df_with_domain = df[df["domain"] != ""].drop_duplicates(
        subset=["domain"], keep="first"
    )
    df_without_domain = df[df["domain"] == ""]
    df = pd.concat([df_with_domain, df_without_domain], ignore_index=True)

    # Save
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "companies.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"Phase 1 complete: {len(df)} companies saved to {output_path}")

    return df
```

---

### PHASE 2 — Careers Page Locator (`careers_finder/`)

**Goal:** For every company in `companies.csv`, find the actual careers/jobs URL and detect the ATS provider.

#### 7.2. `careers_finder/locate_careers_page.py`

```python
"""
careers_finder/locate_careers_page.py

For each company, finds the careers/jobs page URL and detects ATS type.

Algorithm:
1. Fetch the company homepage HTML.
2. Parse all <a> tags and score them by career-related keywords in href and text.
3. Pick the highest-scoring link, resolve to absolute URL.
4. If no match, try common fallback paths (/careers, /jobs, etc.) with HEAD requests.
5. If still nothing, mark careers_url = "NOT_FOUND".
6. Detect ATS provider by matching the final URL against known patterns.
7. Extract ATS-specific company token (for API calls in Phase 3).
"""
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import yaml
from tqdm import tqdm

logger = logging.getLogger(__name__)


def run_phase2_careers_finder(
    companies_df: pd.DataFrame, config: dict
) -> pd.DataFrame:
    """
    Find careers URLs for all companies.

    Args:
        companies_df: DataFrame from Phase 1 (or loaded from output/companies.csv)
        config: Parsed settings.yaml dict

    Returns:
        DataFrame with added columns: careers_url, ats_type, ats_token
    """
    # Load ATS patterns
    ats_patterns_path = Path("config/ats_patterns.yaml")
    with open(ats_patterns_path, "r") as f:
        ats_config = yaml.safe_load(f)

    careers_keywords = config.get("careers_page", {}).get("url_keywords", [
        "career", "careers", "jobs", "join-us", "hiring"
    ])
    fallback_paths = config.get("careers_page", {}).get("fallback_paths", [
        "/careers", "/jobs", "/careers/", "/about/careers"
    ])

    timeout = config.get("http", {}).get("timeout_seconds", 15)
    user_agent = config.get("http", {}).get(
        "user_agent", "JobSearchBot/1.0"
    )
    headers = {"User-Agent": user_agent}

    results = []

    for _, row in tqdm(
        companies_df.iterrows(),
        total=len(companies_df),
        desc="Phase 2: Finding careers pages",
    ):
        website = row.get("website", "")
        company_name = row.get("company_name", "")

        if not website or website == "NOT_FOUND":
            result = row.to_dict()
            result["careers_url"] = "NOT_FOUND"
            result["ats_type"] = "unknown"
            result["ats_token"] = ""
            results.append(result)
            continue

        # Ensure website has a scheme
        if not website.startswith("http"):
            website = f"https://{website}"

        careers_url = "NOT_FOUND"

        # ── Step 1: Fetch homepage and look for career links ──
        try:
            resp = requests.get(
                website, headers=headers, timeout=timeout, allow_redirects=True
            )
            resp.raise_for_status()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            best_score = 0
            best_link = None

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].lower()
                text = a_tag.get_text(strip=True).lower()

                score = 0
                for keyword in careers_keywords:
                    if keyword in href:
                        score += 2  # href match is stronger signal
                    if keyword in text:
                        score += 1

                if score > best_score:
                    best_score = score
                    best_link = a_tag["href"]

            if best_link and best_score >= 2:
                careers_url = urljoin(website, best_link)

        except Exception as e:
            logger.debug(f"Failed to fetch {website}: {e}")

        # ── Step 2: Try fallback paths if no link found ──
        if careers_url == "NOT_FOUND":
            for path in fallback_paths:
                test_url = urljoin(website, path)
                try:
                    resp = requests.head(
                        test_url,
                        headers=headers,
                        timeout=10,
                        allow_redirects=True,
                    )
                    if resp.status_code == 200:
                        careers_url = resp.url  # use final redirected URL
                        break
                except Exception:
                    continue

        # ── Step 3: Follow redirects to get the final URL ──
        if careers_url != "NOT_FOUND":
            try:
                resp = requests.head(
                    careers_url,
                    headers=headers,
                    timeout=10,
                    allow_redirects=True,
                )
                careers_url = resp.url  # final URL after redirects
            except Exception:
                pass

        # ── Step 4: Detect ATS type ──
        ats_type = ats_config.get("default_ats_type", "generic")
        for pattern in ats_config.get("patterns", []):
            if pattern["substring"] in careers_url.lower():
                ats_type = pattern["ats_type"]
                break

        # ── Step 5: Extract ATS token ──
        ats_token = _extract_ats_token(careers_url, ats_type)

        result = row.to_dict()
        result["careers_url"] = careers_url
        result["ats_type"] = ats_type if careers_url != "NOT_FOUND" else "unknown"
        result["ats_token"] = ats_token
        results.append(result)

    result_df = pd.DataFrame(results)

    # Save
    output_path = Path("output/companies_with_careers_url.csv")
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(
        f"Phase 2 complete: {len(result_df)} companies processed, "
        f"saved to {output_path}"
    )

    # Log stats
    found = result_df[result_df["careers_url"] != "NOT_FOUND"]
    logger.info(
        f"  Careers URL found: {len(found)}/{len(result_df)} "
        f"({len(found)/len(result_df)*100:.0f}%)"
    )
    for ats in result_df["ats_type"].value_counts().items():
        logger.info(f"  ATS type '{ats[0]}': {ats[1]} companies")

    return result_df


def _extract_ats_token(url: str, ats_type: str) -> str:
    """
    Extract the company-specific token from an ATS URL.

    Examples:
        "https://boards.greenhouse.io/companyname" -> "companyname"
        "https://jobs.lever.co/companyname" -> "companyname"
        "https://company.wd1.myworkdayjobs.com/en-US/External" -> "company"
    """
    parsed = urlparse(url)

    if ats_type == "greenhouse":
        # Pattern: boards.greenhouse.io/{token} or boards.greenhouse.io/{token}/jobs
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return path_parts[0]

    elif ats_type == "lever":
        # Pattern: jobs.lever.co/{token}
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return path_parts[0]

    elif ats_type == "workday":
        # Pattern: {token}.wd1.myworkdayjobs.com/...
        # The subdomain before .wd*.myworkdayjobs.com is the token
        match = re.match(r"^([^.]+)\.wd\d+\.myworkdayjobs\.com", parsed.netloc)
        if match:
            return match.group(1)

    return ""
```

---

### PHASE 3 — Job Scrapers (`scrapers/`)

**Goal:** For each company in `companies_with_careers_url.csv`, scrape actual job listings based on `ats_type`. Output to `output/raw_jobs.json`.

#### 7.3a. `scrapers/base_scraper.py`

```python
"""
scrapers/base_scraper.py

Abstract base class that all ATS-specific scrapers must inherit.
Defines the common interface and shared utilities.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers.

    Every concrete scraper must implement the `scrape()` method.
    """

    def __init__(self, company_name: str, company_website: str, company_city: str):
        """
        Args:
            company_name: Name of the company being scraped.
            company_website: Company's homepage URL.
            company_city: City where the company is located.
        """
        self.company_name = company_name
        self.company_website = company_website
        self.company_city = company_city

    @abstractmethod
    def scrape(
        self, careers_url: str, ats_token: str, **kwargs
    ) -> list[dict]:
        """
        Scrape job listings from the given careers URL.

        Args:
            careers_url: The careers page URL to scrape.
            ats_token: The ATS-specific company identifier/slug.

        Returns:
            List of job dicts. Each dict MUST have these keys:
                - company_name (str)
                - company_website (str)
                - company_city (str)
                - job_title (str)
                - job_department (str) — empty string if not available
                - experience_required (str) — empty string if not available
                - job_location (str)
                - employment_type (str) — "Full-time" / "Part-time" / "Intern" / "Contract" / ""
                - skills_required (str) — comma-separated or empty string
                - job_description_full (str) — full text description
                - posted_date (str) — ISO format YYYY-MM-DD or empty string
                - apply_link (str) — direct URL to apply
                - ats_type (str) — "greenhouse" / "lever" / "workday" / "generic"
                - scraped_at (str) — ISO 8601 timestamp
        """
        pass

    def _build_job_dict(self, **kwargs) -> dict:
        """
        Helper to build a job dict with all required fields populated.
        Missing fields default to empty string.
        """
        return {
            "company_name": self.company_name,
            "company_website": self.company_website,
            "company_city": self.company_city,
            "job_title": kwargs.get("job_title", ""),
            "job_department": kwargs.get("job_department", ""),
            "experience_required": kwargs.get("experience_required", ""),
            "job_location": kwargs.get("job_location", ""),
            "employment_type": kwargs.get("employment_type", ""),
            "skills_required": kwargs.get("skills_required", ""),
            "job_description_full": kwargs.get("job_description_full", ""),
            "posted_date": kwargs.get("posted_date", ""),
            "apply_link": kwargs.get("apply_link", ""),
            "ats_type": kwargs.get("ats_type", "generic"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
```

---

#### 7.3b. `scrapers/greenhouse_scraper.py`

**API details (from research):**
- **Endpoint:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
- **Authentication:** None required (public read-only API).
- **Response:** JSON with a `jobs` array. Each job has: `id`, `title`, `location.name`, `absolute_url`, `content` (HTML), `departments[].name`, `offices[].name`, `updated_at`, `metadata`.
- **No pagination needed** — the API returns ALL jobs in a single response.

```python
"""
scrapers/greenhouse_scraper.py

Scrapes job listings from Greenhouse Job Board API.
No authentication required. Returns structured JSON.
"""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Greenhouse boards API base URL
GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseScraper(BaseScraper):
    """Scraper for companies using Greenhouse ATS."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def scrape(
        self, careers_url: str, ats_token: str, **kwargs
    ) -> list[dict]:
        """
        Fetch all jobs from Greenhouse boards API.

        Args:
            careers_url: The Greenhouse careers page URL (for reference).
            ats_token: The board token (slug from the URL, e.g. "twitch").

        Returns:
            List of job dicts.
        """
        if not ats_token:
            logger.warning(
                f"No ATS token for {self.company_name}, cannot call Greenhouse API"
            )
            return []

        api_url = f"{GREENHOUSE_API_BASE}/{ats_token}/jobs?content=true"
        logger.info(f"Greenhouse API: GET {api_url}")

        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get("jobs", [])
        results = []

        for job in jobs:
            # Extract department names
            departments = job.get("departments", [])
            dept_names = ", ".join(d.get("name", "") for d in departments)

            # Extract location
            location = job.get("location", {}).get("name", "")

            # Parse HTML content to plain text
            content_html = job.get("content", "")
            description_text = ""
            if content_html:
                soup = BeautifulSoup(content_html, "lxml")
                description_text = soup.get_text(separator="\n", strip=True)

            # Extract posted/updated date
            updated_at = job.get("updated_at", "")
            posted_date = ""
            if updated_at:
                try:
                    dt = datetime.fromisoformat(
                        updated_at.replace("Z", "+00:00")
                    )
                    posted_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    posted_date = updated_at[:10] if len(updated_at) >= 10 else ""

            results.append(
                self._build_job_dict(
                    job_title=job.get("title", ""),
                    job_department=dept_names,
                    job_location=location,
                    job_description_full=description_text,
                    posted_date=posted_date,
                    apply_link=job.get("absolute_url", ""),
                    ats_type="greenhouse",
                )
            )

        logger.info(
            f"Greenhouse: {len(results)} jobs found for {self.company_name}"
        )
        return results
```

---

#### 7.3c. `scrapers/lever_scraper.py`

**API details (from research):**
- **Endpoint:** `GET https://api.lever.co/v0/postings/{company_slug}?mode=json`
- **Authentication:** None required (public endpoint).
- **Response:** A JSON array of posting objects. Each has: `id`, `text` (title), `categories.location`, `categories.commitment`, `categories.team`, `categories.department`, `descriptionPlain`, `hostedUrl`, `applyUrl`, `createdAt`, `workplaceType`, `salaryRange`, `lists[]`.
- **No pagination** — returns all active postings.

```python
"""
scrapers/lever_scraper.py

Scrapes job listings from Lever Postings API.
No authentication required. Returns structured JSON.
"""
import logging
from datetime import datetime

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

LEVER_API_BASE = "https://api.lever.co/v0/postings"


class LeverScraper(BaseScraper):
    """Scraper for companies using Lever ATS."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def scrape(
        self, careers_url: str, ats_token: str, **kwargs
    ) -> list[dict]:
        """
        Fetch all job postings from Lever API.

        Args:
            careers_url: The Lever careers page URL (for reference).
            ats_token: The company slug (from URL, e.g. "netflix").

        Returns:
            List of job dicts.
        """
        if not ats_token:
            logger.warning(
                f"No ATS token for {self.company_name}, cannot call Lever API"
            )
            return []

        api_url = f"{LEVER_API_BASE}/{ats_token}?mode=json"
        logger.info(f"Lever API: GET {api_url}")

        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        postings = resp.json()

        if not isinstance(postings, list):
            logger.warning(f"Lever returned unexpected format: {type(postings)}")
            return []

        results = []

        for posting in postings:
            categories = posting.get("categories", {})

            # Extract commitment (Full-time, Internship, etc.)
            commitment = categories.get("commitment", "")
            employment_type = commitment if commitment else ""

            # Location
            location = categories.get("location", "")

            # Department / team
            team = categories.get("team", "")
            department = categories.get("department", "")
            dept_str = department if department else team

            # Description — prefer plain text version
            description = posting.get("descriptionPlain", "")
            if not description:
                description = posting.get("description", "")

            # Additional content from 'lists' (requirements, qualifications, etc.)
            lists_content = []
            for lst in posting.get("lists", []):
                list_name = lst.get("text", "")
                # Content is HTML — extract text
                list_html = lst.get("content", "")
                if list_html:
                    from bs4 import BeautifulSoup
                    list_text = BeautifulSoup(
                        list_html, "lxml"
                    ).get_text(separator="\n", strip=True)
                    lists_content.append(f"{list_name}:\n{list_text}")
            if lists_content:
                description += "\n\n" + "\n\n".join(lists_content)

            # Posted date from createdAt (milliseconds timestamp)
            created_at = posting.get("createdAt")
            posted_date = ""
            if created_at:
                try:
                    dt = datetime.fromtimestamp(created_at / 1000)
                    posted_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            results.append(
                self._build_job_dict(
                    job_title=posting.get("text", ""),
                    job_department=dept_str,
                    job_location=location,
                    employment_type=employment_type,
                    job_description_full=description.strip(),
                    posted_date=posted_date,
                    apply_link=posting.get("applyUrl", "")
                        or posting.get("hostedUrl", ""),
                    ats_type="lever",
                )
            )

        logger.info(
            f"Lever: {len(results)} jobs found for {self.company_name}"
        )
        return results
```

---

#### 7.3d. `scrapers/workday_scraper.py`

**API details (from research):**
- **No official public API.** Workday uses a hidden JSON endpoint per tenant.
- **Endpoint pattern:** `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site_name}/jobs`
- **Request body:** `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`
- **Response:** JSON with `jobPostings[]` array, each containing `title`, `locationsText`, `postedOn`, `bulletFields[]`, and a `externalPath` for the apply URL.
- **Must include headers:** `Content-Type: application/json`, `Origin`, `Referer`.
- **Pagination:** Use `offset` parameter, increment by `limit` each call. Total available in `total` field.

```python
"""
scrapers/workday_scraper.py

Scrapes job listings from Workday career sites using the hidden JSON API.

Workday career sites load data via an internal POST endpoint.
This scraper mimics those API calls directly (faster than browser automation).

Endpoint pattern:
    POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site_id}/jobs

If the hidden API approach fails (some tenants have extra protections),
this scraper falls back to returning an empty list and logging the failure.
"""
import logging
import re
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseScraper):
    """Scraper for companies using Workday ATS."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def scrape(
        self, careers_url: str, ats_token: str, **kwargs
    ) -> list[dict]:
        """
        Scrape Workday hidden API for job listings.

        Args:
            careers_url: Full Workday careers URL.
            ats_token: Tenant name extracted from URL subdomain.

        Returns:
            List of job dicts.
        """
        if not careers_url or careers_url == "NOT_FOUND":
            return []

        # ── Parse the Workday URL to construct API endpoint ──
        parsed = urlparse(careers_url)
        # Host: {tenant}.wd{N}.myworkdayjobs.com
        host = parsed.netloc

        # Extract site_id from URL path
        # Path pattern: /en-US/{site_id}  or  /{site_id}
        path_parts = [p for p in parsed.path.split("/") if p]
        # Filter out language codes like "en-US", "en"
        site_parts = [
            p for p in path_parts
            if not re.match(r'^[a-z]{2}(-[A-Z]{2})?$', p)
        ]
        site_id = site_parts[0] if site_parts else "External"

        api_url = f"https://{host}/wday/cxs/{ats_token}/{site_id}/jobs"
        logger.info(f"Workday API: POST {api_url}")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": f"https://{host}",
            "Referer": careers_url,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        all_jobs = []
        limit = 20
        offset = 0
        total = None

        while True:
            payload = {
                "appliedFacets": {},
                "limit": limit,
                "offset": offset,
                "searchText": "",
            }

            try:
                resp = requests.post(
                    api_url, json=payload, headers=headers, timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.HTTPError as e:
                if resp.status_code in (403, 429):
                    logger.warning(
                        f"Workday blocked request for {self.company_name}: {e}"
                    )
                    break
                raise
            except Exception as e:
                logger.error(f"Workday API error for {self.company_name}: {e}")
                break

            if total is None:
                total = data.get("total", 0)
                logger.info(
                    f"Workday: {total} total jobs for {self.company_name}"
                )

            postings = data.get("jobPostings", [])
            if not postings:
                break

            for posting in postings:
                title = posting.get("title", "")
                location = posting.get("locationsText", "")
                posted_on = posting.get("postedOn", "")

                # bulletFields contains things like "Full time", "Entry Level", etc.
                bullet_fields = posting.get("bulletFields", [])
                employment_type = ""
                experience = ""
                for field in bullet_fields:
                    field_lower = field.lower() if isinstance(field, str) else ""
                    if any(
                        kw in field_lower
                        for kw in ["full time", "part time", "intern", "contract"]
                    ):
                        employment_type = field
                    elif any(
                        kw in field_lower
                        for kw in ["entry", "senior", "mid", "junior", "experienced"]
                    ):
                        experience = field

                # Build apply link from externalPath
                external_path = posting.get("externalPath", "")
                apply_link = ""
                if external_path:
                    apply_link = f"https://{host}{external_path}"

                all_jobs.append(
                    self._build_job_dict(
                        job_title=title,
                        job_location=location,
                        employment_type=employment_type,
                        experience_required=experience,
                        posted_date=posted_on,
                        apply_link=apply_link,
                        ats_type="workday",
                    )
                )

            offset += limit
            if offset >= (total or 0):
                break

        logger.info(
            f"Workday: {len(all_jobs)} jobs scraped for {self.company_name}"
        )
        return all_jobs
```

---

#### 7.3e. `scrapers/generic_scraper.py`

**Purpose:** Fallback scraper for companies NOT using a recognized ATS. Uses a two-tier approach:
1. First try `requests` + BeautifulSoup (fast, for static HTML pages).
2. If no job listings found in raw HTML (common with React/Angular/Vue SPAs), fall back to Playwright to render JavaScript.

```python
"""
scrapers/generic_scraper.py

Fallback scraper for custom career pages that don't use a recognized ATS.

Strategy:
1. Fetch page HTML with requests + BeautifulSoup.
2. Look for repeated elements that look like job listings (heuristic matching).
3. If nothing found in static HTML, use Playwright to render the page and try again.

Expected success rate: ~40-60%. Companies that fail are logged to
output/failed_scrapes.csv for manual review.
"""
import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Patterns that commonly appear in job listing elements
JOB_ELEMENT_PATTERNS = [
    r"job",
    r"posting",
    r"opening",
    r"position",
    r"listing",
    r"vacancy",
    r"career",
    r"opportunity",
    r"role",
]

# Compiled regex for matching job-related CSS classes/IDs
JOB_CLASS_REGEX = re.compile(
    "|".join(JOB_ELEMENT_PATTERNS), re.IGNORECASE
)


class GenericScraper(BaseScraper):
    """Fallback scraper for custom career pages."""

    def scrape(
        self, careers_url: str, ats_token: str = "", **kwargs
    ) -> list[dict]:
        """
        Attempt to scrape job listings from a generic careers page.

        First tries static HTML parsing, then falls back to Playwright.
        """
        if not careers_url or careers_url == "NOT_FOUND":
            return []

        # ── Tier 1: Static HTML (requests + BeautifulSoup) ──
        jobs = self._scrape_static(careers_url)
        if jobs:
            logger.info(
                f"Generic (static): {len(jobs)} jobs for {self.company_name}"
            )
            return jobs

        # ── Tier 2: Playwright (JavaScript rendering) ──
        logger.info(
            f"No jobs in static HTML for {self.company_name}, "
            "trying Playwright..."
        )
        jobs = self._scrape_playwright(careers_url)
        if jobs:
            logger.info(
                f"Generic (Playwright): {len(jobs)} jobs for {self.company_name}"
            )
        else:
            logger.warning(
                f"Generic scraper found 0 jobs for {self.company_name} "
                f"at {careers_url}"
            )

        return jobs

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _scrape_static(self, url: str) -> list[dict]:
        """Attempt to find job listings in static HTML."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        return self._extract_jobs_from_html(resp.text, url)

    def _scrape_playwright(self, url: str) -> list[dict]:
        """Use Playwright to render the page and extract jobs."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Cannot render JS pages.")
            return []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = context.new_page()
                page.goto(url, timeout=20000, wait_until="networkidle")
                page.wait_for_timeout(3000)  # extra time for lazy-loaded content
                html = page.content()
                browser.close()

            return self._extract_jobs_from_html(html, url)

        except Exception as e:
            logger.error(f"Playwright scraping failed for {url}: {e}")
            return []

    def _extract_jobs_from_html(self, html: str, base_url: str) -> list[dict]:
        """
        Heuristic extraction of job listings from HTML.

        Strategy:
        1. Find all elements whose class or id contains job-related keywords.
        2. Among those, look for elements that repeat (suggesting a list).
        3. From each repeated element, extract a title (text) and link.
        """
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        # ── Strategy A: Find job-like container elements ──
        # Look for <a> tags whose href or text suggests a job link
        job_links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)
            parent_classes = " ".join(a_tag.parent.get("class", []))

            # Score this link as a potential job listing
            is_job_link = (
                JOB_CLASS_REGEX.search(href)
                or JOB_CLASS_REGEX.search(parent_classes)
                or JOB_CLASS_REGEX.search(" ".join(a_tag.get("class", [])))
            )

            # Must have meaningful text (not just "Apply" or icons)
            has_title = len(text) > 5 and len(text) < 200

            if is_job_link and has_title:
                job_links.append((text, href))

        # ── Strategy B: Look for repeated list items ──
        if not job_links:
            # Find all list items or divs with job-related parent
            for parent in soup.find_all(
                class_=JOB_CLASS_REGEX
            ):
                child_links = parent.find_all("a", href=True)
                for a in child_links:
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    if len(text) > 5 and len(text) < 200:
                        job_links.append((text, href))

        # Deduplicate
        seen = set()
        for title, href in job_links:
            key = (title.lower(), href)
            if key in seen:
                continue
            seen.add(key)

            apply_link = urljoin(base_url, href)

            jobs.append(
                self._build_job_dict(
                    job_title=title,
                    apply_link=apply_link,
                    ats_type="generic",
                )
            )

        return jobs
```

---

#### 7.3f. `scrapers/__init__.py` — Phase 3 Orchestrator

```python
"""
scrapers/__init__.py

Orchestrates Phase 3: routes each company to the correct scraper
based on ats_type, collects results, saves to output/raw_jobs.json.
"""
import json
import logging
import time
import random
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from tqdm import tqdm

from .greenhouse_scraper import GreenhouseScraper
from .lever_scraper import LeverScraper
from .workday_scraper import WorkdayScraper
from .generic_scraper import GenericScraper

logger = logging.getLogger(__name__)


def run_phase3_scrapers(
    companies_df: pd.DataFrame, config: dict
) -> list[dict]:
    """
    Scrape job listings for all companies.

    Args:
        companies_df: DataFrame from Phase 2 with careers_url, ats_type, ats_token.
        config: Parsed settings.yaml dict.

    Returns:
        List of all job dicts (flat list).
    """
    min_delay = config.get("rate_limit", {}).get("min_delay_seconds", 1.5)
    max_delay = config.get("rate_limit", {}).get("max_delay_seconds", 3.0)

    all_jobs = []
    failed_scrapes = []

    for _, row in tqdm(
        companies_df.iterrows(),
        total=len(companies_df),
        desc="Phase 3: Scraping jobs",
    ):
        company_name = row.get("company_name", "")
        company_website = row.get("website", "")
        company_city = row.get("city", "")
        careers_url = row.get("careers_url", "")
        ats_type = row.get("ats_type", "generic")
        ats_token = row.get("ats_token", "")

        if careers_url == "NOT_FOUND" or ats_type == "unknown":
            logger.debug(f"Skipping {company_name}: no careers URL")
            continue

        # Select the right scraper
        scraper_map = {
            "greenhouse": GreenhouseScraper,
            "lever": LeverScraper,
            "workday": WorkdayScraper,
            "generic": GenericScraper,
        }
        scraper_class = scraper_map.get(ats_type, GenericScraper)
        scraper = scraper_class(
            company_name=company_name,
            company_website=company_website,
            company_city=company_city,
        )

        try:
            jobs = scraper.scrape(
                careers_url=careers_url, ats_token=ats_token
            )
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error(f"Scraping failed for {company_name}: {e}")
            failed_scrapes.append({
                "company_name": company_name,
                "careers_url": careers_url,
                "ats_type": ats_type,
                "error_message": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            })

        # Rate limit between companies
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    # Save raw jobs
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    raw_jobs_path = output_dir / "raw_jobs.json"
    with open(raw_jobs_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    logger.info(
        f"Phase 3 complete: {len(all_jobs)} jobs saved to {raw_jobs_path}"
    )

    # Save failed scrapes
    if failed_scrapes:
        failed_df = pd.DataFrame(failed_scrapes)
        failed_path = output_dir / "failed_scrapes.csv"
        failed_df.to_csv(failed_path, index=False, encoding="utf-8-sig")
        logger.warning(
            f"{len(failed_scrapes)} companies failed scraping — "
            f"see {failed_path}"
        )

    return all_jobs
```

---

### PHASE 4 — Filter, Normalize, Dedup (`processing/`)

#### 7.4a. `processing/filter_jobs.py`

```python
"""
processing/filter_jobs.py

Filters raw job listings to keep only software/developer relevant roles.
Uses case-insensitive substring matching on job_title (and optionally department).
"""
import logging

logger = logging.getLogger(__name__)


def filter_jobs(jobs: list[dict], keywords: list[str]) -> list[dict]:
    """
    Filter jobs to keep only those matching software/dev keywords.

    Args:
        jobs: List of job dicts from Phase 3.
        keywords: List of keyword strings to match against job_title.
                  Loaded from config/settings.yaml -> job_title_keywords.

    Returns:
        Filtered list of job dicts.
    """
    filtered = []
    for job in jobs:
        title = job.get("job_title", "").lower()
        department = job.get("job_department", "").lower()

        matched = any(
            kw.lower() in title or kw.lower() in department
            for kw in keywords
        )

        if matched:
            filtered.append(job)

    logger.info(
        f"Filter: kept {len(filtered)}/{len(jobs)} jobs "
        f"({len(filtered)/max(len(jobs),1)*100:.0f}%)"
    )
    return filtered
```

#### 7.4b. `processing/normalize.py`

```python
"""
processing/normalize.py

Normalizes and cleans job data fields:
- Strips HTML remnants from descriptions.
- Standardizes experience strings.
- Trims whitespace.
- Truncates job_description_summary to max_chars.
"""
import logging
import re

logger = logging.getLogger(__name__)


def normalize_jobs(jobs: list[dict], max_summary_chars: int = 300) -> list[dict]:
    """
    Normalize and clean all job fields.

    Args:
        jobs: List of job dicts.
        max_summary_chars: Max characters for job_description_summary field.

    Returns:
        List of normalized job dicts (same list, mutated + summary added).
    """
    for job in jobs:
        # ── Clean whitespace ──
        for key in job:
            if isinstance(job[key], str):
                job[key] = job[key].strip()
                # Collapse multiple whitespace/newlines
                job[key] = re.sub(r"\s+", " ", job[key])

        # ── Strip HTML remnants from description ──
        desc = job.get("job_description_full", "")
        desc = re.sub(r"<[^>]+>", "", desc)  # remove any remaining HTML tags
        desc = re.sub(r"&[a-zA-Z]+;", " ", desc)  # remove HTML entities
        desc = re.sub(r"\s+", " ", desc).strip()
        job["job_description_full"] = desc

        # ── Create summary (truncated description) ──
        if len(desc) > max_summary_chars:
            job["job_description_summary"] = desc[:max_summary_chars].rsplit(
                " ", 1
            )[0] + "..."
        else:
            job["job_description_summary"] = desc

        # ── Standardize experience field ──
        exp = job.get("experience_required", "")
        if exp:
            # Normalize patterns like "2-4 yrs", "2 to 4 years" -> "2-4 years"
            exp = re.sub(r"\s*to\s*", "-", exp, flags=re.IGNORECASE)
            exp = re.sub(r"\s*yrs?\b", " years", exp, flags=re.IGNORECASE)
            exp = re.sub(r"\s+", " ", exp).strip()
            job["experience_required"] = exp

        # ── Normalize employment type ──
        emp_type = job.get("employment_type", "").lower()
        type_map = {
            "full-time": "Full-time",
            "full time": "Full-time",
            "fulltime": "Full-time",
            "part-time": "Part-time",
            "part time": "Part-time",
            "parttime": "Part-time",
            "intern": "Intern",
            "internship": "Intern",
            "contract": "Contract",
            "contractor": "Contract",
            "temporary": "Contract",
        }
        for pattern, canonical in type_map.items():
            if pattern in emp_type:
                job["employment_type"] = canonical
                break

    logger.info(f"Normalize: processed {len(jobs)} jobs")
    return jobs
```

#### 7.4c. `processing/dedup.py`

```python
"""
processing/dedup.py

Removes duplicate job entries based on (company_name, job_title, apply_link).
"""
import logging

logger = logging.getLogger(__name__)


def dedup_jobs(jobs: list[dict]) -> list[dict]:
    """
    Remove duplicate jobs.

    Dedup key: (company_name.lower(), job_title.lower(), apply_link)

    Args:
        jobs: List of job dicts.

    Returns:
        Deduplicated list.
    """
    seen = set()
    unique = []

    for job in jobs:
        key = (
            job.get("company_name", "").lower().strip(),
            job.get("job_title", "").lower().strip(),
            job.get("apply_link", "").strip(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)

    removed = len(jobs) - len(unique)
    if removed > 0:
        logger.info(f"Dedup: removed {removed} duplicates, {len(unique)} remain")
    else:
        logger.info(f"Dedup: no duplicates found in {len(jobs)} jobs")

    return unique
```

#### 7.4d. `processing/__init__.py`

```python
"""
processing/__init__.py

Orchestrates Phase 4: filter → normalize → dedup.
"""
import logging

from .filter_jobs import filter_jobs
from .normalize import normalize_jobs
from .dedup import dedup_jobs

logger = logging.getLogger(__name__)


def run_phase4_processing(jobs: list[dict], config: dict) -> list[dict]:
    """
    Run the full Phase 4 pipeline: filter, normalize, dedup.

    Args:
        jobs: Raw job list from Phase 3.
        config: Parsed settings.yaml dict.

    Returns:
        Cleaned, filtered, deduplicated list of job dicts.
    """
    keywords = config.get("job_title_keywords", [])
    max_summary = config.get("description_summary_max_chars", 300)

    logger.info(f"Phase 4: processing {len(jobs)} raw jobs...")

    # Step 1: Filter by keywords
    jobs = filter_jobs(jobs, keywords)

    # Step 2: Normalize fields
    jobs = normalize_jobs(jobs, max_summary_chars=max_summary)

    # Step 3: Remove duplicates
    jobs = dedup_jobs(jobs)

    logger.info(f"Phase 4 complete: {len(jobs)} jobs after processing")
    return jobs
```

---

### PHASE 5 — Final CSV Export (`utils/csv_writer.py`)

```python
"""
utils/csv_writer.py

Exports the final processed job list to a CSV file.
"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Column order for the final CSV
FINAL_COLUMNS = [
    "company_name",
    "company_website",
    "company_city",
    "company_industry",
    "job_title",
    "job_department",
    "experience_required",
    "job_location",
    "employment_type",
    "skills_required",
    "job_description_summary",
    "job_description_full",
    "posted_date",
    "apply_link",
    "ats_type",
    "scraped_at",
]


def export_final_csv(jobs: list[dict], city: str) -> str:
    """
    Export jobs to final CSV.

    Args:
        jobs: Processed list of job dicts from Phase 4.
        city: City name (used in filename).

    Returns:
        Path to the exported CSV file.
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    city_slug = city.lower().replace(" ", "_")
    filename = f"jobs_{city_slug}_{date_str}.csv"
    output_path = output_dir / filename

    df = pd.DataFrame(jobs)

    # Ensure all expected columns exist (fill missing with empty string)
    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Reorder columns
    df = df[FINAL_COLUMNS]

    # Export with utf-8-sig encoding so Excel opens it correctly
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(
        f"Phase 5 complete: {len(df)} jobs exported to {output_path}"
    )
    return str(output_path)
```

---

## 8. Utility Modules

### 8a. `utils/http_client.py`

```python
"""
utils/http_client.py

A pre-configured requests Session wrapper with:
- Custom User-Agent header
- Automatic retries with exponential backoff (via tenacity)
- Configurable timeout
"""
import logging

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def create_http_session(user_agent: str, timeout: int = 15) -> requests.Session:
    """
    Create a requests Session with default headers and retry adapter.

    Args:
        user_agent: User-Agent string.
        timeout: Default timeout in seconds.

    Returns:
        Configured requests.Session instance.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    # Mount retry adapter
    adapter = requests.adapters.HTTPAdapter(
        max_retries=requests.adapters.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def fetch_url(url: str, session: requests.Session = None, timeout: int = 15) -> str:
    """
    Fetch a URL and return the response text.

    Args:
        url: URL to fetch.
        session: Optional pre-configured session.
        timeout: Request timeout in seconds.

    Returns:
        Response text content.

    Raises:
        requests.exceptions.HTTPError: On non-2xx status codes.
    """
    if session is None:
        session = create_http_session("JobSearchBot/1.0")

    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text
```

### 8b. `utils/rate_limiter.py`

```python
"""
utils/rate_limiter.py

Simple rate limiter that sleeps for a random duration between min and max seconds.
Used between HTTP requests to the same domain to avoid hammering servers.
"""
import random
import time
import logging

logger = logging.getLogger(__name__)


def rate_limit_sleep(
    min_seconds: float = 1.5,
    max_seconds: float = 3.0,
    domain: str = "",
) -> None:
    """
    Sleep for a random duration between min_seconds and max_seconds.

    Args:
        min_seconds: Minimum sleep time.
        max_seconds: Maximum sleep time.
        domain: Optional domain name (for logging purposes).
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Rate limiting: sleeping {delay:.1f}s" +
                 (f" for {domain}" if domain else ""))
    time.sleep(delay)
```

### 8c. `utils/logger.py`

```python
"""
utils/logger.py

Centralized logging configuration.
Sets up both console (colored) and file logging.
"""
import logging
import sys
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = None) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to a log file. If provided, logs are also
                  written to this file.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers (prevents duplicate logs on re-init)
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        file_format = logging.Formatter(
            fmt="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)

    logging.info(f"Logging initialized at level {log_level}")
```

### 8d. `utils/__init__.py`

```python
"""utils package — shared utilities."""
```

---

## 9. Main Orchestrator (`main.py`)

```python
"""
main.py

Orchestrates all 5 phases of the job scraper pipeline.
Each phase reads from the previous phase's output file,
so any phase can be re-run independently.

Usage:
    python main.py                    # Interactive: prompts for city
    python main.py --city Mumbai      # Direct city input
    python main.py --phase 3          # Re-run from Phase 3 onward
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from utils.logger import setup_logging
from discovery import run_phase1_discovery
from careers_finder.locate_careers_page import run_phase2_careers_finder
from scrapers import run_phase3_scrapers
from processing import run_phase4_processing
from utils.csv_writer import export_final_csv

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load settings.yaml configuration."""
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main():
    # ── Parse CLI arguments ──
    parser = argparse.ArgumentParser(
        description="Job Listings Aggregator — scrapes software jobs from a city"
    )
    parser.add_argument(
        "--city",
        type=str,
        help="Target city name (e.g., 'Mumbai')",
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5],
        help="Start from this phase (default: 1). "
             "Phases 2+ read from previous phase's output file.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    # ── Setup ──
    load_dotenv()
    setup_logging(
        log_level=args.log_level, log_file="output/scraper.log"
    )
    config = load_config()

    city = args.city or config.get("city")
    if not city:
        city = input("Enter target city: ").strip()
    if not city:
        logger.error("No city provided. Exiting.")
        sys.exit(1)

    logger.info(f"{'='*60}")
    logger.info(f"Job Scraper starting for city: {city}")
    logger.info(f"Starting from Phase {args.phase}")
    logger.info(f"{'='*60}")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # ═════════════════════════════════════════════
    # PHASE 1: Company Discovery
    # ═════════════════════════════════════════════
    if args.phase <= 1:
        logger.info("=" * 40 + " PHASE 1: Company Discovery " + "=" * 40)
        companies_df = run_phase1_discovery(city, config)
    else:
        companies_path = output_dir / "companies.csv"
        if not companies_path.exists():
            logger.error(f"Phase 1 output not found: {companies_path}")
            sys.exit(1)
        companies_df = pd.read_csv(companies_path)
        logger.info(
            f"Loaded {len(companies_df)} companies from {companies_path}"
        )

    # ═════════════════════════════════════════════
    # PHASE 2: Careers Page Locator
    # ═════════════════════════════════════════════
    if args.phase <= 2:
        logger.info("=" * 40 + " PHASE 2: Careers Page Locator " + "=" * 40)
        companies_with_urls = run_phase2_careers_finder(companies_df, config)
    else:
        careers_path = output_dir / "companies_with_careers_url.csv"
        if not careers_path.exists():
            logger.error(f"Phase 2 output not found: {careers_path}")
            sys.exit(1)
        companies_with_urls = pd.read_csv(careers_path)
        logger.info(
            f"Loaded {len(companies_with_urls)} companies from {careers_path}"
        )

    # ═════════════════════════════════════════════
    # PHASE 3: Job Scraping
    # ═════════════════════════════════════════════
    if args.phase <= 3:
        logger.info("=" * 40 + " PHASE 3: Job Scraping " + "=" * 40)
        raw_jobs = run_phase3_scrapers(companies_with_urls, config)
    else:
        raw_jobs_path = output_dir / "raw_jobs.json"
        if not raw_jobs_path.exists():
            logger.error(f"Phase 3 output not found: {raw_jobs_path}")
            sys.exit(1)
        with open(raw_jobs_path, "r", encoding="utf-8") as f:
            raw_jobs = json.load(f)
        logger.info(f"Loaded {len(raw_jobs)} raw jobs from {raw_jobs_path}")

    # ═════════════════════════════════════════════
    # PHASE 4: Filter, Normalize, Dedup
    # ═════════════════════════════════════════════
    if args.phase <= 4:
        logger.info("=" * 40 + " PHASE 4: Processing " + "=" * 40)
        processed_jobs = run_phase4_processing(raw_jobs, config)
    else:
        # No intermediate file for Phase 4 — reprocess from raw_jobs.json
        raw_jobs_path = output_dir / "raw_jobs.json"
        with open(raw_jobs_path, "r", encoding="utf-8") as f:
            raw_jobs = json.load(f)
        processed_jobs = run_phase4_processing(raw_jobs, config)

    # ═════════════════════════════════════════════
    # PHASE 5: Final CSV Export
    # ═════════════════════════════════════════════
    logger.info("=" * 40 + " PHASE 5: CSV Export " + "=" * 40)
    output_file = export_final_csv(processed_jobs, city)

    logger.info(f"{'='*60}")
    logger.info(f"DONE! Final output: {output_file}")
    logger.info(f"Total jobs in final CSV: {len(processed_jobs)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
```

---

## 10. Build Order (Recommended Implementation Sequence)

Follow this order to get a working end-to-end pipeline as quickly as possible:

| Step | Files to Create | Why This Order |
|------|----------------|----------------|
| **1** | `utils/__init__.py`, `utils/logger.py`, `utils/rate_limiter.py`, `utils/http_client.py` | Foundational utilities used by every other module. |
| **2** | `config/settings.yaml`, `config/ats_patterns.yaml`, `.env`, `.gitignore`, `requirements.txt` | Configuration files that all modules read from. |
| **3** | `scrapers/base_scraper.py` | Abstract base class — must exist before any scraper. |
| **4** | `scrapers/greenhouse_scraper.py`, `scrapers/lever_scraper.py` | Fastest to get working (clean JSON APIs, no HTML parsing). Test with known tokens: `greenhouse→ "twitch"`, `lever→ "netflix"`. |
| **5** | `discovery/google_places_discovery.py` | Gets a real company list for a test city. Requires API key. |
| **6** | `discovery/clutch_discovery.py`, `discovery/naukri_discovery.py` | Additional discovery sources. |
| **7** | `discovery/__init__.py` | Phase 1 orchestrator (merge + dedup). |
| **8** | `careers_finder/locate_careers_page.py` | Connects discovery to scrapers. |
| **9** | `scrapers/workday_scraper.py` | More complex ATS scraper (hidden API). |
| **10** | `scrapers/generic_scraper.py` | Hardest scraper (heuristic HTML parsing + Playwright). Do last. |
| **11** | `scrapers/__init__.py` | Phase 3 orchestrator. |
| **12** | `processing/filter_jobs.py`, `processing/normalize.py`, `processing/dedup.py`, `processing/__init__.py` | Phase 4 pipeline — straightforward data processing. |
| **13** | `utils/csv_writer.py` | Final CSV export. |
| **14** | `main.py` | Wire everything together. |

---

## 11. Testing & Validation

### Quick smoke tests during development:

```bash
# Test Greenhouse scraper with a known company
python -c "
from scrapers.greenhouse_scraper import GreenhouseScraper
s = GreenhouseScraper('Twitch', 'https://twitch.tv', 'San Francisco')
jobs = s.scrape('https://boards.greenhouse.io/twitch', 'twitch')
print(f'Found {len(jobs)} jobs')
if jobs: print(jobs[0]['job_title'])
"

# Test Lever scraper with a known company
python -c "
from scrapers.lever_scraper import LeverScraper
s = LeverScraper('Netflix', 'https://netflix.com', 'Los Gatos')
jobs = s.scrape('https://jobs.lever.co/netflix', 'netflix')
print(f'Found {len(jobs)} jobs')
if jobs: print(jobs[0]['job_title'])
"

# Full pipeline test
python main.py --city "Bangalore" --log-level DEBUG
```

### Expected output for a successful run:

```
12:00:01 │ INFO     │ root │ Logging initialized at level INFO
12:00:01 │ INFO     │ __main__ │ ============================================================
12:00:01 │ INFO     │ __main__ │ Job Scraper starting for city: Bangalore
12:00:01 │ INFO     │ __main__ │ Starting from Phase 1
12:00:01 │ INFO     │ __main__ │ ============================================================
12:00:01 │ INFO     │ __main__ │ ======== PHASE 1: Company Discovery ========
12:00:05 │ INFO     │ discovery │ Google Places: found 45 companies in Bangalore
12:00:15 │ INFO     │ discovery │ Clutch: found 30 companies in Bangalore
12:00:25 │ INFO     │ discovery │ Naukri: found 20 companies in Bangalore
12:00:25 │ INFO     │ discovery │ Phase 1 complete: 72 companies saved to output/companies.csv
...
12:05:00 │ INFO     │ __main__ │ DONE! Final output: output/jobs_bangalore_2025-01-15.csv
12:05:00 │ INFO     │ __main__ │ Total jobs in final CSV: 234
```

---

## 12. Practical Notes & Constraints

1. **User-Agent:** Always set a descriptive User-Agent header. See `config/settings.yaml` for the default.
2. **Rate limiting:** 1.5–3s random delay between requests to the same domain. Never hammer a single server.
3. **robots.txt:** Respect it where feasible. The ATS APIs (Greenhouse, Lever) are explicitly public.
4. **Generic scraper failures:** Expected ~40-60% success rate. Failed companies go to `output/failed_scrapes.csv` for manual review — don't try to perfect every edge case.
5. **LinkedIn:** NEVER automate. Violates ToS, causes account bans, carries legal risk.
6. **API keys:** Store in `.env`, never commit. The `.gitignore` must include `.env`.
7. **Clutch anti-bot:** Must use Playwright, not plain requests (403 errors). Selectors may break if Clutch changes their HTML — log warnings and skip.
8. **Workday anti-bot:** Some tenants have TLS fingerprinting. The hidden API approach works for most, but some will return 403. Log and skip.
9. **Phase independence:** Every phase reads from the previous phase's file. Use `--phase N` to re-run from phase N onward without re-doing earlier phases.

---

## 13. Environment Variables Summary

| Variable               | Required | Used By          | How to Get                                        |
|------------------------|----------|------------------|---------------------------------------------------|
| `GOOGLE_PLACES_API_KEY`| Yes      | Phase 1 (Google) | [Google Cloud Console](https://console.cloud.google.com/) → Enable Places API |
| `GOOGLE_CSE_API_KEY`   | Optional | Future use       | Google Cloud Console → Enable Custom Search API   |
| `GOOGLE_CSE_ID`        | Optional | Future use       | [Programmable Search Engine](https://programmablesearchengine.google.com/) |

---

## 14. README.md Content

```markdown
# Job Search Aggregator

A Python tool that discovers software companies in a city and scrapes their job listings.

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Create a `.env` file with your API keys:
   ```
   GOOGLE_PLACES_API_KEY=your_key_here
   ```

3. Run the tool:
   ```bash
   python main.py --city "Mumbai"
   ```

## Options

| Flag          | Description                          | Default |
|---------------|--------------------------------------|---------|
| `--city`      | Target city name                     | From config/settings.yaml |
| `--phase`     | Start from this phase (1-5)          | 1       |
| `--log-level` | Logging verbosity                    | INFO    |

## Output

Final CSV is saved to `output/jobs_<city>_<date>.csv` with columns:
company_name, job_title, job_location, apply_link, and more.
```
