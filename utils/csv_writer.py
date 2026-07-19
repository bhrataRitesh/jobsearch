"""
utils/csv_writer.py

Exports the final processed job list to a CSV file.
Uses utf-8-sig encoding so the file opens correctly in Excel.
"""
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Column order for the final CSV
FINAL_COLUMNS = [
    "company_name",
    "company_website",
    "company_city",
    "company_industry",
    "job_title",
    "job_department",
    "experience_required",
    "job_location",
    "employment_type",
    "skills_required",
    "job_description_summary",
    "job_description_full",
    "posted_date",
    "apply_link",
    "ats_type",
    "scraped_at",
]


def export_final_csv(jobs: list[dict], city: str) -> str:
    """
    Export jobs to the final CSV file.

    Args:
        jobs: Processed list of job dicts from Phase 4.
        city: City name (used in the output filename).

    Returns:
        Absolute path to the exported CSV file as a string.
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    city_slug = city.lower().replace(" ", "_")
    filename = f"jobs_{city_slug}_{date_str}.csv"
    output_path = output_dir / filename

    df = pd.DataFrame(jobs)

    # Ensure all expected columns exist (fill missing with empty string)
    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    # Reorder columns to the canonical order
    df = df[FINAL_COLUMNS]

    # Export with utf-8-sig encoding so Excel opens it correctly
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    logger.info(f"Phase 5 complete: {len(df)} jobs exported to {output_path}")
    return str(output_path)
