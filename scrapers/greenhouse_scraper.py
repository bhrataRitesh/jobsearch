"""
scrapers/greenhouse_scraper.py

Scrapes job listings from the Greenhouse Job Board API.

API Details:
- Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
- Authentication: None required (public read-only API)
- Response: JSON with a ``jobs`` array
- Each job has: id, title, location.name, absolute_url, content (HTML),
  departments[].name, offices[].name, updated_at, metadata
- No pagination — returns ALL jobs in a single response
"""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

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
            careers_url: The Greenhouse careers page URL (for reference only).
            ats_token: The board token (slug from the URL, e.g. ``"twitch"``).

        Returns:
            List of job dicts matching the BaseScraper schema.
        """
        if not ats_token:
            logger.warning(
                f"No ATS token for {self.company_name}, "
                "cannot call Greenhouse API"
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
            dept_names = ", ".join(
                d.get("name", "") for d in departments if d.get("name")
            )

            # Extract location
            location = job.get("location", {}).get("name", "")

            # Parse HTML content field to plain text
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
                    posted_date = (
                        updated_at[:10] if len(updated_at) >= 10 else ""
                    )

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
