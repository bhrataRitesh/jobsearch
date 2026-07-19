"""
processing/dedup.py

Removes duplicate job entries based on the composite key:
``(company_name, job_title, apply_link)`` (all lowercased/stripped).
"""
import logging

logger = logging.getLogger(__name__)


def dedup_jobs(jobs: list[dict]) -> list[dict]:
    """
    Remove duplicate jobs.

    Dedup key: ``(company_name.lower(), job_title.lower(), apply_link)``

    Args:
        jobs: List of job dicts.

    Returns:
        Deduplicated list (preserves first occurrence).
    """
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []

    for job in jobs:
        key = (
            job.get("company_name", "").lower().strip(),
            job.get("job_title", "").lower().strip(),
            job.get("apply_link", "").strip(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)

    removed = len(jobs) - len(unique)
    if removed > 0:
        logger.info(
            f"Dedup: removed {removed} duplicates, {len(unique)} remain"
        )
    else:
        logger.info(
            f"Dedup: no duplicates found in {len(jobs)} jobs"
        )

    return unique
