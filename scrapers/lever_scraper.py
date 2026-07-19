"""
scrapers/lever_scraper.py

Scrapes job listings from the Lever Postings API.

API Details:
- Endpoint: GET https://api.lever.co/v0/postings/{company_slug}?mode=json
- Authentication: None required (public endpoint)
- Response: JSON array of posting objects
- Each posting has: id, text (title), categories.location, categories.commitment,
  categories.team, categories.department, descriptionPlain, hostedUrl, applyUrl,
  createdAt (ms timestamp), workplaceType, salaryRange, lists[]
- No pagination — returns all active postings in one response
"""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
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
            careers_url: The Lever careers page URL (for reference only).
            ats_token: The company slug (from URL, e.g. ``"netflix"``).

        Returns:
            List of job dicts matching the BaseScraper schema.
        """
        if not ats_token:
            logger.warning(
                f"No ATS token for {self.company_name}, "
                "cannot call Lever API"
            )
            return []

        api_url = f"{LEVER_API_BASE}/{ats_token}?mode=json"
        logger.info(f"Lever API: GET {api_url}")

        resp = requests.get(api_url, timeout=15)
        resp.raise_for_status()
        postings = resp.json()

        if not isinstance(postings, list):
            logger.warning(
                f"Lever returned unexpected format for {self.company_name}: "
                f"{type(postings)}"
            )
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

            # Additional content from 'lists' (requirements, benefits, etc.)
            lists_content = []
            for lst in posting.get("lists", []):
                list_name = lst.get("text", "")
                list_html = lst.get("content", "")
                if list_html:
                    list_text = BeautifulSoup(
                        list_html, "lxml"
                    ).get_text(separator="\n", strip=True)
                    lists_content.append(f"{list_name}:\n{list_text}")

            if lists_content:
                description += "\n\n" + "\n\n".join(lists_content)

            # Posted date from createdAt (milliseconds since epoch)
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
                    apply_link=(
                        posting.get("applyUrl", "")
                        or posting.get("hostedUrl", "")
                    ),
                    ats_type="lever",
                )
            )

        logger.info(
            f"Lever: {len(results)} jobs found for {self.company_name}"
        )
        return results
