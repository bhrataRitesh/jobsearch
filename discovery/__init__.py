"""
discovery — Phase 1: Company Discovery.

Orchestrates all discovery methods (Google Places, Clutch, Naukri),
merges results, deduplicates by domain, and saves to ``output/companies.csv``.
"""
import logging
from pathlib import Path

import pandas as pd

from .clutch_discovery import discover_companies_clutch
from .google_places_discovery import discover_companies_google_places
from .naukri_discovery import discover_companies_naukri

logger = logging.getLogger(__name__)


def run_phase1_discovery(city: str, config: dict) -> pd.DataFrame:
    """
    Run all discovery methods, merge, dedup by domain, and save CSV.

    Each discovery method runs independently — if one fails, the others
    still contribute results. Errors are logged but do not stop the pipeline.

    Args:
        city: Target city name, e.g. ``"Mumbai"``.
        config: Parsed ``settings.yaml`` dict.

    Returns:
        DataFrame of discovered companies (also saved to
        ``output/companies.csv``).
    """
    all_companies: list[dict] = []

    # ── Method A: Google Places API ──
    try:
        queries = config.get(
            "discovery_queries",
            ["software development company in {city}"],
        )
        gp_companies = discover_companies_google_places(city, queries)
        all_companies.extend(gp_companies)
    except Exception as e:
        logger.error(f"Google Places discovery failed: {e}")

    # ── Method B: Clutch.co ──
    try:
        clutch_companies = discover_companies_clutch(city)
        all_companies.extend(clutch_companies)
    except Exception as e:
        logger.error(f"Clutch discovery failed: {e}")

    # ── Method C: Naukri.com ──
    try:
        naukri_companies = discover_companies_naukri(city)
        all_companies.extend(naukri_companies)
    except Exception as e:
        logger.error(f"Naukri discovery failed: {e}")

    if not all_companies:
        logger.warning("No companies discovered from any source!")
        return pd.DataFrame()

    df = pd.DataFrame(all_companies)

    # ── Deduplicate by normalized domain ──
    # Companies from Naukri/Clutch may not have a domain yet — keep them all
    df_with_domain = df[df["domain"] != ""].drop_duplicates(
        subset=["domain"], keep="first"
    )
    df_without_domain = df[df["domain"] == ""]
    df = pd.concat(
        [df_with_domain, df_without_domain], ignore_index=True
    )

    # ── Save to CSV ──
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "companies.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(
        f"Phase 1 complete: {len(df)} companies saved to {output_path}"
    )
    return df
