"""
scrapers/base_scraper.py

Abstract base class that all ATS-specific scrapers must inherit.
Defines the common interface and shared helper for building job dicts.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers.

    Every concrete scraper must implement the ``scrape()`` method, which
    takes a careers URL and an ATS token and returns a list of job dicts.
    """

    def __init__(
        self,
        company_name: str,
        company_website: str,
        company_city: str,
    ):
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
                - employment_type (str) — Full-time / Part-time / Intern / Contract / ""
                - skills_required (str) — comma-separated or empty string
                - job_description_full (str) — full text description
                - posted_date (str) — ISO format YYYY-MM-DD or empty string
                - apply_link (str) — direct URL to apply
                - ats_type (str) — greenhouse / lever / workday / generic
                - scraped_at (str) — ISO 8601 timestamp
        """
        pass

    def _build_job_dict(self, **kwargs) -> dict:
        """
        Helper to build a standardized job dict with all required fields.

        Pass any field as a keyword argument; missing fields default to
        empty string. ``company_name``, ``company_website``, ``company_city``,
        and ``scraped_at`` are set automatically from the instance.
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
