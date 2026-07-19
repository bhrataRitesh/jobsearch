"""
scrapers — ATS-specific and generic job scrapers.

This package orchestrates Phase 3: routes each company to the correct scraper
based on ``ats_type``, collects results, and saves to ``output/raw_jobs.json``.
"""
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from .generic_scraper import GenericScraper
from .greenhouse_scraper import GreenhouseScraper
from .lever_scraper import LeverScraper
from .workday_scraper import WorkdayScraper
from .naukri_scraper import NaukriScraper

logger = logging.getLogger(__name__)

# Maps ats_type string → scraper class
SCRAPER_MAP = {
    "greenhouse": GreenhouseScraper,
    "lever": LeverScraper,
    "workday": WorkdayScraper,
    "naukri": NaukriScraper,
    "generic": GenericScraper,
}


def run_phase3_scrapers(
    companies_df: pd.DataFrame,
    config: dict,
) -> list[dict]:
    """
    Scrape job listings for all companies (Phase 3).

    Routes each company to the appropriate scraper based on its ``ats_type``
    column, collects all job dicts, and saves the raw results to
    ``output/raw_jobs.json``. Companies that fail scraping are logged to
    ``output/failed_scrapes.csv``.

    Args:
        companies_df: DataFrame from Phase 2 with columns including
            ``company_name``, ``website``, ``city``, ``careers_url``,
            ``ats_type``, ``ats_token``.
        config: Parsed ``settings.yaml`` dict.

    Returns:
        Flat list of all scraped job dicts.
    """
    min_delay = config.get("rate_limit", {}).get("min_delay_seconds", 1.5)
    max_delay = config.get("rate_limit", {}).get("max_delay_seconds", 3.0)

    all_jobs: list[dict] = []
    failed_scrapes: list[dict] = []

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

        # Skip companies with no careers URL
        if careers_url == "NOT_FOUND" or ats_type == "unknown":
            logger.debug(f"Skipping {company_name}: no careers URL")
            continue

        # Select the right scraper class
        scraper_class = SCRAPER_MAP.get(ats_type, GenericScraper)
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
            failed_scrapes.append(
                {
                    "company_name": company_name,
                    "careers_url": careers_url,
                    "ats_type": ats_type,
                    "error_message": str(e),
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        # Rate limit between companies
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)

    # ── Save outputs ──
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Raw jobs JSON
    raw_jobs_path = output_dir / "raw_jobs.json"
    with open(raw_jobs_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    logger.info(
        f"Phase 3 complete: {len(all_jobs)} jobs saved to {raw_jobs_path}"
    )

    # Failed scrapes CSV
    if failed_scrapes:
        failed_df = pd.DataFrame(failed_scrapes)
        failed_path = output_dir / "failed_scrapes.csv"
        failed_df.to_csv(failed_path, index=False, encoding="utf-8-sig")
        logger.warning(
            f"{len(failed_scrapes)} companies failed scraping — "
            f"see {failed_path}"
        )

    return all_jobs
