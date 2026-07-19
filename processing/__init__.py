"""
processing — Phase 4: Filter, Normalize, Dedup.

Orchestrates the full Phase 4 pipeline:
    filter by keywords → normalize fields → deduplicate entries.
"""
import logging

from .dedup import dedup_jobs
from .filter_jobs import filter_jobs
from .normalize import normalize_jobs

logger = logging.getLogger(__name__)


def run_phase4_processing(
    jobs: list[dict], config: dict
) -> list[dict]:
    """
    Run the full Phase 4 pipeline: filter → normalize → dedup.

    Args:
        jobs: Raw job list from Phase 3.
        config: Parsed ``settings.yaml`` dict.

    Returns:
        Cleaned, filtered, deduplicated list of job dicts.
    """
    keywords = config.get("job_title_keywords", [])
    max_summary = config.get("description_summary_max_chars", 300)

    logger.info(f"Phase 4: processing {len(jobs)} raw jobs...")

    # Step 1: Filter by keywords
    jobs = filter_jobs(jobs, keywords)

    # Step 2: Normalize fields
    jobs = normalize_jobs(jobs, max_summary_chars=max_summary)

    # Step 3: Remove duplicates
    jobs = dedup_jobs(jobs)

    logger.info(f"Phase 4 complete: {len(jobs)} jobs after processing")
    return jobs
