"""
scrapers/generic_scraper.py

Fallback scraper for custom career pages that don't use a recognized ATS.

Strategy (two tiers):
1. Fetch page HTML with requests + BeautifulSoup (fast, for static HTML).
2. If no job listings found in raw HTML (common with React/Angular/Vue SPAs),
   fall back to Playwright to render JavaScript and try again.

Heuristic job extraction:
- Look for <a> tags whose href or parent class contains job-related keywords.
- Look for repeated list elements inside job-related containers.

Expected success rate: ~40-60%. Companies that fail are logged to
output/failed_scrapes.csv for manual follow-up.
"""
import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Regex pattern matching common job-related CSS class/ID names
JOB_CLASS_REGEX = re.compile(
    r"job|posting|opening|position|listing|vacancy|career|opportunity|role",
    re.IGNORECASE,
)


class GenericScraper(BaseScraper):
    """Fallback scraper for custom career pages (non-ATS)."""

    def scrape(
        self, careers_url: str, ats_token: str = "", **kwargs
    ) -> list[dict]:
        """
        Attempt to scrape job listings from a generic careers page.

        First tries static HTML parsing, then falls back to Playwright
        if no jobs are found.

        Args:
            careers_url: URL of the career page to scrape.
            ats_token: Unused (generic pages have no token).

        Returns:
            List of job dicts matching the BaseScraper schema.
        """
        if not careers_url or careers_url == "NOT_FOUND":
            return []

        # ── Tier 1: Static HTML (requests + BeautifulSoup) ──
        jobs = self._scrape_static(careers_url)
        if jobs:
            logger.info(
                f"Generic (static): {len(jobs)} jobs for "
                f"{self.company_name}"
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
                f"Generic (Playwright): {len(jobs)} jobs for "
                f"{self.company_name}"
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
            logger.error(
                "Playwright not installed. Cannot render JS pages."
            )
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
                page.wait_for_timeout(3000)  # lazy-loaded content
                html = page.content()
                browser.close()

            return self._extract_jobs_from_html(html, url)

        except Exception as e:
            logger.error(f"Playwright scraping failed for {url}: {e}")
            return []

    def _extract_jobs_from_html(
        self, html: str, base_url: str
    ) -> list[dict]:
        """
        Heuristic extraction of job listings from raw HTML.

        Strategy:
        1. Find <a> tags whose href, class, or parent class contains
           job-related keywords.
        2. Keep only links with meaningful title text (5–200 chars).
        3. Fall back to looking inside job-related container elements.
        """
        soup = BeautifulSoup(html, "lxml")
        job_links: list[tuple[str, str]] = []

        # ── Strategy A: <a> tags with job-like hrefs or parents ──
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)
            parent_classes = " ".join(a_tag.parent.get("class", []))
            own_classes = " ".join(a_tag.get("class", []))

            is_job_link = (
                JOB_CLASS_REGEX.search(href)
                or JOB_CLASS_REGEX.search(parent_classes)
                or JOB_CLASS_REGEX.search(own_classes)
            )

            # Must have meaningful text (not just "Apply" or icons)
            has_title = 5 < len(text) < 200

            if is_job_link and has_title:
                job_links.append((text, href))

        # ── Strategy B: Elements inside job-related containers ──
        if not job_links:
            for parent in soup.find_all(class_=JOB_CLASS_REGEX):
                child_links = parent.find_all("a", href=True)
                for a in child_links:
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    if 5 < len(text) < 200:
                        job_links.append((text, href))

        # ── Deduplicate and build job dicts ──
        seen: set[tuple[str, str]] = set()
        jobs: list[dict] = []

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
