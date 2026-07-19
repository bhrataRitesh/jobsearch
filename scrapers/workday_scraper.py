"""
scrapers/workday_scraper.py

Scrapes job listings from Workday career sites using the hidden JSON API.

Workday career sites load job data via an internal POST endpoint.
This scraper mimics those API calls directly (much faster than browser automation).

Endpoint pattern:
    POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site_id}/jobs

Request body:
    {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

Required headers: Content-Type, Origin, Referer, realistic User-Agent.

Pagination: Increment ``offset`` by ``limit`` until offset >= total.
"""
import logging
import re
from urllib.parse import urlparse

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class WorkdayScraper(BaseScraper):
    """Scraper for companies using Workday ATS (hidden JSON API approach)."""

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
            careers_url: Full Workday careers URL
                (e.g. ``"https://acme.wd1.myworkdayjobs.com/en-US/External"``).
            ats_token: Tenant name extracted from the URL subdomain
                (e.g. ``"acme"``).

        Returns:
            List of job dicts matching the BaseScraper schema.
        """
        if not careers_url or careers_url == "NOT_FOUND":
            return []

        # ── Parse the Workday URL to construct the API endpoint ──
        parsed = urlparse(careers_url)
        host = parsed.netloc  # e.g. acme.wd1.myworkdayjobs.com

        # Extract site_id from the URL path.
        # Typical paths: /en-US/External, /External, /en-US/External_Careers
        path_parts = [p for p in parsed.path.split("/") if p]
        # Filter out language codes like "en-US", "en"
        site_parts = [
            p
            for p in path_parts
            if not re.match(r"^[a-z]{2}(-[A-Z]{2})?$", p)
        ]
        site_id = site_parts[0] if site_parts else "External"

        api_url = (
            f"https://{host}/wday/cxs/{ats_token}/{site_id}/jobs"
        )
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
            except requests.exceptions.HTTPError:
                if resp.status_code in (403, 429):
                    logger.warning(
                        f"Workday blocked request for {self.company_name} "
                        f"(HTTP {resp.status_code})"
                    )
                    break
                raise
            except Exception as e:
                logger.error(
                    f"Workday API error for {self.company_name}: {e}"
                )
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

                # bulletFields contains e.g. "Full time", "Entry Level"
                bullet_fields = posting.get("bulletFields", [])
                employment_type = ""
                experience = ""
                for field in bullet_fields:
                    if not isinstance(field, str):
                        continue
                    field_lower = field.lower()
                    if any(
                        kw in field_lower
                        for kw in [
                            "full time",
                            "part time",
                            "intern",
                            "contract",
                        ]
                    ):
                        employment_type = field
                    elif any(
                        kw in field_lower
                        for kw in [
                            "entry",
                            "senior",
                            "mid",
                            "junior",
                            "experienced",
                        ]
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
