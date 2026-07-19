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


# Dictionary of known geona_ids for major cities to bypass autocomplete complexity
GEONA_IDS = {
    "noida": "11429",
    "mumbai": "11342",
    "bangalore": "11355",
    "bengaluru": "11355",
    "pune": "11347",
    "hyderabad": "11345",
    "chennai": "11341",
    "gurgaon": "11364",
    "gurugram": "11364",
    "delhi": "11340",
}


def discover_companies_clutch(
    city: str, max_pages: int = 5
) -> list[dict]:
    """
    Scrape Clutch.co for software development companies in a city.

    Args:
        city: Target city name, e.g. ``"Mumbai"``.
        max_pages: Maximum number of listing pages to scrape
            (each page has ~50-100 companies).

    Returns:
        List of dicts matching the ``companies.csv`` schema.
    """
    city_clean = city.lower().strip()
    geona_id = GEONA_IDS.get(city_clean)
    
    if geona_id:
        base_url = f"https://clutch.co/developers?geona_id={geona_id}"
    else:
        # Fall back to slug format if geona_id is not predefined
        city_slug = city_clean.replace(" ", "-")
        base_url = f"https://clutch.co/developers/{city_slug}"

    companies: list[dict] = []

    with sync_playwright() as p:
        # Launch headed browser to bypass Cloudflare protection
        browser = p.chromium.launch(headless=False)
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
                else f"{base_url}&page={page_num}" if geona_id else f"{base_url}?page={page_num}"
            )
            logger.info(f"Clutch: fetching {url}")

            try:
                page.goto(
                    url, timeout=30000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(3000)  # let content render
            except Exception as e:
                logger.warning(f"Clutch page load failed: {e}")
                break

            # ── Extract company cards ──
            # Only match .provider-row to prevent duplicate sub-element matches
            cards = page.query_selector_all(".provider-row")

            if not cards:
                # Try alternative list-item selector if classes changed
                cards = page.query_selector_all("[class*='provider-list-item']")

            if not cards:
                logger.warning(
                    f"No company cards found on {url} — Clutch may have "
                    "changed their HTML structure. Inspect manually."
                )
                break

            for card in cards:
                try:
                    # Company name
                    name_el = card.query_selector("h3 a, .company-name a")
                    name = (
                        name_el.inner_text().strip() if name_el else ""
                    )

                    # Website link
                    website_el = card.query_selector("a[href*='redirect'], a[href*='website']")
                    website = ""
                    if website_el:
                        website = (
                            website_el.get_attribute("href") or ""
                        )
                        # Extract the destination URL from Clutch redirect if needed
                        if "u=" in website:
                            from urllib.parse import parse_qs
                            parsed_web = urlparse(website)
                            query_params = parse_qs(parsed_web.query)
                            if "u" in query_params:
                                website = query_params["u"][0]

                    if not website and name_el:
                        profile_href = name_el.get_attribute("href") or ""
                        if profile_href and not profile_href.startswith("http"):
                            profile_href = f"https://clutch.co{profile_href}"
                        website = profile_href

                    # Location text
                    loc_el = card.query_selector(".locality, [class*='location']")
                    address = (
                        loc_el.inner_text().strip() if loc_el else city
                    )

                    # Employee count
                    emp_el = card.query_selector(".sg-rate, [class*='employees']")
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

    # Deduplicate companies by name just in case
    seen_names = set()
    deduped_companies = []
    for c in companies:
        name_lower = c["company_name"].lower().strip()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            deduped_companies.append(c)

    logger.info(f"Clutch: found {len(deduped_companies)} unique companies in {city}")
    return deduped_companies


def _extract_domain(url: str) -> str:
    """Extract normalized domain from a URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
