"""
scrapers/naukri_scraper.py

Scrapes job listings from a company's Naukri.com profile page using Playwright.
Bypasses Cloudflare protection by running in headed mode.
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class NaukriScraper(BaseScraper):
    """Scraper for companies using Naukri company profile pages."""

    def scrape(
        self, careers_url: str, ats_token: str = "", **kwargs
    ) -> list[dict]:
        """
        Scrape job postings listed on Naukri profile page.

        Args:
            careers_url: Naukri profile URL
                (e.g. ``"https://www.naukri.com/liangtuang-technologies-jobs-careers-6835803"``).
            ats_token: Unused.

        Returns:
            List of job dicts matching the BaseScraper schema.
        """
        if not careers_url or "naukri.com" not in careers_url:
            return []

        logger.info(f"Naukri Scraper: fetching {careers_url} (headed mode)")
        results = []

        with sync_playwright() as p:
            # headed mode is required to pass Cloudflare challenge
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            try:
                page.goto(
                    careers_url, timeout=30000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(5000) # wait for elements to render
                
                html = page.content()
                if "Access Denied" in page.title() or "Cloudflare" in html:
                    logger.warning(
                        f"Naukri Scraper blocked by Cloudflare for "
                        f"{self.company_name}"
                    )
                    return []

                # Find all links containing job listings
                links = page.query_selector_all("a[href*='/job-listings-']")
                seen_links = set()

                for link in links:
                    try:
                        title = link.inner_text().strip()
                        href = link.get_attribute("href") or ""
                        
                        if not href.startswith("http") and href:
                            href = f"https://www.naukri.com{href}"
                            
                        if not href or href in seen_links:
                            continue
                        seen_links.add(href)

                        # Extract experience and location heuristics from Naukri URL slug
                        # e.g., ...-noida-0-to-2-years-141125501336
                        experience = ""
                        location = self.company_city
                        
                        exp_match = re.search(r"(\d+-to-\d+-years?)", href)
                        if exp_match:
                            experience = exp_match.group(1).replace("-", " ")

                        results.append(
                            self._build_job_dict(
                                job_title=title,
                                job_location=location,
                                experience_required=experience,
                                apply_link=href,
                                ats_type="naukri",
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Error parsing job link on Naukri: {e}")
                        continue
                        
            except Exception as e:
                logger.error(
                    f"Naukri Scraper failed to scrape {careers_url}: {e}"
                )
            finally:
                browser.close()

        logger.info(
            f"Naukri Scraper: found {len(results)} jobs for "
            f"{self.company_name}"
        )
        return results
