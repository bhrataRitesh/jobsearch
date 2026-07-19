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
    Discover software companies from Naukri.com company directory.

    Args:
        city: Target city name, e.g. ``"Mumbai"``.
        max_pages: Maximum number of listing pages to scrape.

    Returns:
        List of dicts matching the ``companies.csv`` schema.
    """
    city_slug = city.lower().replace(" ", "-")
    base_url = (
        f"https://www.naukri.com/companies-hiring-in-{city_slug}"
        f"?industryType=IT+-+Software"
    )

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

        for page_num in range(1, max_pages + 1):
            url = (
                f"{base_url}&pageNo={page_num}"
                if page_num > 1
                else base_url
            )
            logger.info(f"Naukri: fetching {url}")

            try:
                page.goto(
                    url, timeout=20000, wait_until="networkidle"
                )
                page.wait_for_timeout(2000)
            except Exception as e:
                logger.warning(f"Naukri page load failed: {e}")
                break

            # ── Extract company cards ──
            # Naukri uses patterns like .comp-card, .company-card, article
            cards = page.query_selector_all(
                ".comp-card, [class*='companyCard'], article"
            )

            if not cards:
                logger.warning(
                    f"No cards found on Naukri page {page_num}"
                )
                break

            for card in cards:
                try:
                    name_el = card.query_selector(
                        "a[class*='title'], h2, [class*='compName']"
                    )
                    name = (
                        name_el.inner_text().strip() if name_el else ""
                    )

                    # Naukri shows company profile links, not direct websites
                    link_el = card.query_selector("a[href]")
                    profile_url = ""
                    if link_el:
                        href = link_el.get_attribute("href") or ""
                        if not href.startswith("http"):
                            href = f"https://www.naukri.com{href}"
                        profile_url = href

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
                    logger.debug(f"Error parsing Naukri card: {e}")
                    continue

        browser.close()

    logger.info(f"Naukri: found {len(companies)} companies in {city}")
    return companies
