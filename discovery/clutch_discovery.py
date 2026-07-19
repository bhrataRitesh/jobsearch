"""
discovery/clutch_discovery.py

Scrapes Clutch.co company listings for a given city.

IMPORTANT: Clutch.co has aggressive anti-bot detection and returns 403 errors
for plain HTTP requests. This module MUST use Playwright (headless browser)
to bypass the bot protection.

CSS selectors may break if Clutch redesigns their pages — the code logs
clear warnings when selectors fail so a developer can update them.
"""
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def discover_companies_clutch(
    city: str, max_pages: int = 5
) -> list[dict]:
    """
    Scrape Clutch.co for software development companies in a city.

    Args:
        city: Target city name, e.g. ``"Mumbai"``.
        max_pages: Maximum number of listing pages to scrape
            (each page has ~15 companies).

    Returns:
        List of dicts matching the ``companies.csv`` schema.
    """
    # Clutch URL slug: lowercase, spaces → hyphens
    city_slug = city.lower().strip().replace(" ", "-")
    base_url = f"https://clutch.co/developers/{city_slug}"

    companies: list[dict] = []

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
            url = (
                base_url
                if page_num == 0
                else f"{base_url}?page={page_num}"
            )
            logger.info(f"Clutch: fetching {url}")

            try:
                page.goto(
                    url, timeout=20000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(2000)  # let dynamic content load
            except Exception as e:
                logger.warning(f"Clutch page load failed: {e}")
                break

            # ── Extract company cards ──
            # NOTE: Clutch frequently changes class names. These selectors
            # are current as of early 2025. If they break, inspect the page
            # in a browser and update the selectors below.
            cards = page.query_selector_all(
                "li[data-content='provider'], .provider-row"
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
                    name = (
                        name_el.inner_text().strip() if name_el else ""
                    )

                    # Website link
                    website_el = card.query_selector(
                        "a[href*='website'], a[class*='website']"
                    )
                    website = ""
                    if website_el:
                        website = (
                            website_el.get_attribute("href") or ""
                        )
                    elif name_el:
                        # Fall back to company profile URL on Clutch
                        profile_href = (
                            name_el.get_attribute("href") or ""
                        )
                        if profile_href and not profile_href.startswith(
                            "http"
                        ):
                            profile_href = (
                                f"https://clutch.co{profile_href}"
                            )
                        website = profile_href

                    # Location text
                    loc_el = card.query_selector(
                        ".locality, [class*='location']"
                    )
                    address = (
                        loc_el.inner_text().strip() if loc_el else city
                    )

                    # Employee count
                    emp_el = card.query_selector(
                        "[class*='employees'], [class*='size']"
                    )
                    employee_count = (
                        emp_el.inner_text().strip() if emp_el else ""
                    )

                    if name:
                        companies.append(
                            {
                                "company_name": name,
                                "website": website.rstrip("/"),
                                "domain": (
                                    _extract_domain(website)
                                    if website
                                    else ""
                                ),
                                "city": city,
                                "address": address,
                                "industry": "Software Development",
                                "employee_count": employee_count,
                                "rating": None,
                                "source": "clutch",
                                "discovered_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            }
                        )
                except Exception as e:
                    logger.debug(f"Error parsing Clutch card: {e}")
                    continue

            # Check if there's a next page link
            next_btn = page.query_selector(
                "a[rel='next'], .page-link-next, [class*='next']"
            )
            if not next_btn:
                break

        browser.close()

    logger.info(f"Clutch: found {len(companies)} companies in {city}")
    return companies


def _extract_domain(url: str) -> str:
    """Extract normalized domain from a URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
