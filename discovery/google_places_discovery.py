"""
discovery/google_places_discovery.py

Uses the googlemaps Python client to search for software companies via
Google Places Text Search API.

API Details:
- Uses ``googlemaps.Client.places()`` (Text Search endpoint)
- Cost: ~$0.032 per text search call + ~$0.017 per place detail call
- Free tier: $200/month credit — sufficient for this use case
- Pagination: up to 60 results across 3 pages via ``next_page_token``
- IMPORTANT: 2-second delay required between pagination calls
"""
import logging
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import googlemaps
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def discover_companies_google_places(
    city: str, queries: list[str]
) -> list[dict]:
    """
    Discover software companies in the given city using Google Places API.

    Args:
        city: Target city name, e.g. ``"Mumbai"``.
        queries: List of query templates with ``{city}`` placeholder,
                 e.g. ``["software development company in {city}"]``.

    Returns:
        List of dicts matching the ``companies.csv`` schema.

    Raises:
        ValueError: If ``GOOGLE_PLACES_API_KEY`` env var is not set.
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_PLACES_API_KEY not found in .env file. "
            "Get one at https://console.cloud.google.com/"
        )

    gmaps = googlemaps.Client(key=api_key)
    all_companies: list[dict] = []
    seen_place_ids: set[str] = set()  # dedup within this source

    for query_template in queries:
        query = query_template.format(city=city)
        logger.info(f"Google Places search: '{query}'")

        try:
            results = gmaps.places(query=query)
        except Exception as e:
            logger.error(
                f"Google Places API error for query '{query}': {e}"
            )
            continue

        places = results.get("results", [])

        # Paginate — Google returns up to 60 results across 3 pages
        while "next_page_token" in results:
            # REQUIRED: token needs ~2 seconds to become valid on Google's side
            time.sleep(2)
            try:
                results = gmaps.places(
                    query=query,
                    page_token=results["next_page_token"],
                )
                places.extend(results.get("results", []))
            except Exception as e:
                logger.warning(f"Pagination error: {e}")
                break

        for place in places:
            place_id = place.get("place_id", "")
            if place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)

            # Fetch website from Place Details (not in Text Search response)
            website = ""
            try:
                detail = gmaps.place(place_id, fields=["website"])
                website = (
                    detail.get("result", {}).get("website", "")
                )
            except Exception:
                pass

            if not website:
                continue  # Skip companies without a website

            company = {
                "company_name": place.get("name", ""),
                "website": website.rstrip("/"),
                "domain": _extract_domain(website),
                "city": city,
                "address": place.get("formatted_address", ""),
                "industry": "Software / IT",
                "employee_count": "",
                "rating": place.get("rating", None),
                "source": "google_places",
                "discovered_at": datetime.now(timezone.utc).isoformat(),
            }
            all_companies.append(company)

    logger.info(
        f"Google Places: found {len(all_companies)} companies in {city}"
    )
    return all_companies


def _extract_domain(url: str) -> str:
    """
    Extract a normalized domain from a URL.

    Example: ``'https://www.infosys.com/about/'`` → ``'infosys.com'``
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain
