# 🔍 Job Search Aggregator

A Python CLI tool that discovers software companies in any city and scrapes their job listings into a single, actionable CSV file.

## ✨ Features

- **Multi-source company discovery** — Google Places API, Clutch.co, Naukri.com
- **Automatic careers page detection** — Crawls company websites to find careers/jobs pages
- **ATS-aware scraping** — Dedicated scrapers for Greenhouse, Lever, and Workday APIs
- **Generic fallback** — BeautifulSoup + Playwright for custom career pages
- **Smart filtering** — Keeps only software/dev-relevant roles
- **Deduplication & normalization** — Clean, consistent output
- **Phase-based pipeline** — Re-run any phase independently without redoing earlier work

## 📋 Prerequisites

- Python 3.10+
- A Google Places API key ([get one here](https://console.cloud.google.com/))

## 🚀 Setup

```bash
# Clone the repo
git clone <repo-url>
cd jobsearch

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Set up environment variables
cp .env.example .env
# Edit .env and add your Google Places API key
```

## 🎯 Usage

```bash
# Basic usage — interactive city prompt
python main.py

# Specify city directly
python main.py --city "Mumbai"

# Re-run from a specific phase (skips earlier phases)
python main.py --city "Mumbai" --phase 3

# Verbose logging
python main.py --city "Bangalore" --log-level DEBUG
```

### CLI Options

| Flag          | Description                              | Default                    |
|---------------|------------------------------------------|----------------------------|
| `--city`      | Target city name                         | From `config/settings.yaml`|
| `--phase`     | Start from this phase (1–5)              | `1`                        |
| `--log-level` | Logging verbosity (DEBUG/INFO/WARNING/ERROR) | `INFO`                 |

## 🏗️ Architecture

The pipeline runs in 5 sequential phases:

```
City Name Input
      │
      ▼
[Phase 1] Company Discovery ──────────► output/companies.csv
      │
      ▼
[Phase 2] Careers Page Locator ────────► output/companies_with_careers_url.csv
      │
      ▼
[Phase 3] Job Scraper (ATS-aware) ─────► output/raw_jobs.json
      │
      ▼
[Phase 4] Filter + Normalize + Dedup
      │
      ▼
[Phase 5] Final CSV Export ────────────► output/jobs_<city>_<date>.csv
```

Each phase reads from the previous phase's output file, so you can re-run any phase independently.

## 📂 Project Structure

```
jobsearch/
├── config/
│   ├── settings.yaml          # City, keywords, rate limits
│   └── ats_patterns.yaml      # ATS URL detection patterns
│
├── discovery/                 # Phase 1: Find companies
│   ├── google_places_discovery.py
│   ├── clutch_discovery.py
│   └── naukri_discovery.py
│
├── careers_finder/            # Phase 2: Find careers pages
│   └── locate_careers_page.py
│
├── scrapers/                  # Phase 3: Scrape job listings
│   ├── base_scraper.py        # Abstract base class
│   ├── greenhouse_scraper.py  # Greenhouse JSON API
│   ├── lever_scraper.py       # Lever JSON API
│   ├── workday_scraper.py     # Workday hidden API
│   └── generic_scraper.py     # BS4 + Playwright fallback
│
├── processing/                # Phase 4: Clean & filter
│   ├── filter_jobs.py
│   ├── normalize.py
│   └── dedup.py
│
├── utils/                     # Shared utilities
│   ├── http_client.py
│   ├── rate_limiter.py
│   ├── logger.py
│   └── csv_writer.py
│
├── output/                    # All outputs (gitignored)
├── main.py                    # Pipeline orchestrator
├── requirements.txt
└── .env                       # API keys (gitignored)
```

## 📊 Output

The final CSV (`output/jobs_<city>_<date>.csv`) includes:

| Column                    | Description                              |
|---------------------------|------------------------------------------|
| `company_name`            | Company name                             |
| `company_website`         | Company homepage URL                     |
| `company_city`            | City the company is in                   |
| `company_industry`        | Industry (if available)                  |
| `job_title`               | Job title                                |
| `job_department`          | Department / team                        |
| `experience_required`     | Experience requirement                   |
| `job_location`            | Job location (may differ from HQ)        |
| `employment_type`         | Full-time / Intern / Contract            |
| `skills_required`         | Comma-separated skills                   |
| `job_description_summary` | First 300 characters                     |
| `job_description_full`    | Complete description text                |
| `posted_date`             | When the job was posted                  |
| `apply_link`              | Direct URL to apply                      |
| `ats_type`                | ATS platform (greenhouse/lever/etc.)     |
| `scraped_at`              | When we scraped this listing             |

## ⚠️ Important Notes

- **LinkedIn** is explicitly not scraped (violates ToS, legal risk)
- **Rate limiting**: 1.5–3s delay between requests to respect servers
- **Generic scraper** has ~40–60% success rate — failures are logged to `output/failed_scrapes.csv`
- **API keys** are stored in `.env` and never committed to git

## 📝 License

MIT
