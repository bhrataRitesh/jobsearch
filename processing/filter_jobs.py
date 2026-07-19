"""
processing/filter_jobs.py

Filters raw job listings to keep only software/developer relevant roles.
Uses case-insensitive substring matching on ``job_title`` and optionally
``job_department``.
"""
import logging

logger = logging.getLogger(__name__)


def filter_jobs(
    jobs: list[dict], keywords: list[str]
) -> list[dict]:
    """
    Filter jobs to keep only those matching software/dev keywords.

    A job is kept if ANY keyword appears as a substring in either the
    ``job_title`` or ``job_department`` field (case-insensitive).

    Args:
        jobs: List of job dicts from Phase 3.
        keywords: List of keyword strings to match against.
                  Loaded from ``config/settings.yaml`` →
                  ``job_title_keywords``.

    Returns:
        Filtered list of job dicts (subset of input).
    """
    filtered: list[dict] = []

    for job in jobs:
        title = job.get("job_title", "").lower()
        department = job.get("job_department", "").lower()

        matched = any(
            kw.lower() in title or kw.lower() in department
            for kw in keywords
        )

        if matched:
            filtered.append(job)

    total = len(jobs)
    kept = len(filtered)
    pct = kept / max(total, 1) * 100
    logger.info(f"Filter: kept {kept}/{total} jobs ({pct:.0f}%)")

    return filtered
