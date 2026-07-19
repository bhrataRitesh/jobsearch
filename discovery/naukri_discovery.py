"""
discovery/naukri_discovery.py

Scrapes Naukri.com company directory for IT/Software companies in a city.
Naukri is useful because it lists companies that are actively hiring.

Uses Playwright since Naukri renders content dynamically (React SPA).
"""
import logging
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def discover_companies_naukri(
    city: str, max_pages: int = 5
) -> list[dict]:
    """
    Discover software companies from active Naukri.com job postings in a city.

    Args:
        city: Target city name, e.g. ``"Noida"``.
        max_pages: Maximum number of listing pages to scrape.

    Returns:
        List of dicts matching the ``companies.csv`` schema.
    """
    city_slug = city.lower().strip().replace(" ", "-")
    # Base URL using the query parameters for software developer jobs in Noida/city
    base_url = (
        f"https://www.naukri.com/software-developer-software-engineer-jobs-in-{city_slug}"
        f"?k=software%20developer%2C%20software%20engineer&l={city_slug}&experience=1"
    )

    companies: list[dict] = []

    with sync_playwright() as p:
        # Launch headed browser to bypass bot checks / Access Denied page
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"{base_url}&pageNo={page_num}" if page_num > 1 else base_url
            logger.info(f"Naukri: fetching {url}")

            try:
                page.goto(
                    url, timeout=30000, wait_until="domcontentloaded"
                )
                page.wait_for_timeout(5000)  # Wait for listings to render
            except Exception as e:
                logger.warning(f"Naukri page load failed: {e}")
                break

            # Naukri job lists have links for company profile and hiring company names
            # Specifically select links matching comp-name or companyName
            comp_links = page.query_selector_all("a.comp-name, a[href*='jobs-careers-']")

            if not comp_links:
                # Try a broader selector if classes changed
                comp_links = page.query_selector_all("[class*='companyName'], [class*='comp-name']")

            if not comp_links:
                logger.warning(
                    f"No company links found on Naukri page {page_num}"
                )
                break

            for link in comp_links:
                try:
                    name = link.inner_text().strip()
                    profile_url = link.get_attribute("href") or ""
                    
                    if not profile_url.startswith("http") and profile_url:
                        profile_url = f"https://www.naukri.com{profile_url}"

                    # Clean up common navigation words
                    if name.lower() in ("companies", "top companies", "featured companies"):
                        continue

                    if name:
                        companies.append(
                            {
                                "company_name": name,
                                "website": profile_url,
                                "domain": "",  # Resolved in Phase 2
                                "city": city,
                                "address": city,
                                "industry": "IT / Software",
                                "employee_count": "",
                                "rating": None,
                                "source": "naukri",
                                "discovered_at": datetime.now(
                                    timezone.utc
                                ).isoformat(),
                            }
                        )
                except Exception as e:
                    logger.debug(f"Error parsing Naukri company: {e}")
                    continue

        browser.close()

    # Deduplicate companies by name
    seen_names = set()
    deduped_companies = []
    for c in companies:
        name_lower = c["company_name"].lower().strip()
        if name_lower not in seen_names:
            seen_names.add(name_lower)
            deduped_companies.append(c)

    logger.info(f"Naukri: found {len(deduped_companies)} unique companies in {city}")
    return deduped_companies
