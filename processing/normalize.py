"""
processing/normalize.py

Normalizes and cleans job data fields:
- Strips HTML remnants from descriptions.
- Standardizes experience strings (e.g. "2-4 yrs" → "2-4 years").
- Trims/collapses whitespace.
- Normalizes employment type to canonical values.
- Creates ``job_description_summary`` (truncated to max_chars).
"""
import logging
import re

logger = logging.getLogger(__name__)

# Canonical employment type mappings
_EMPLOYMENT_TYPE_MAP = {
    "full-time": "Full-time",
    "full time": "Full-time",
    "fulltime": "Full-time",
    "part-time": "Part-time",
    "part time": "Part-time",
    "parttime": "Part-time",
    "intern": "Intern",
    "internship": "Intern",
    "contract": "Contract",
    "contractor": "Contract",
    "temporary": "Contract",
}


def normalize_jobs(
    jobs: list[dict], max_summary_chars: int = 300
) -> list[dict]:
    """
    Normalize and clean all job fields in-place.

    Args:
        jobs: List of job dicts (mutated in-place).
        max_summary_chars: Max characters for the
            ``job_description_summary`` field.

    Returns:
        The same list of job dicts, now cleaned and with
        ``job_description_summary`` added.
    """
    for job in jobs:
        # ── Clean whitespace on all string fields ──
        for key in job:
            if isinstance(job[key], str):
                job[key] = job[key].strip()
                job[key] = re.sub(r"\s+", " ", job[key])

        # ── Strip HTML remnants from description ──
        desc = job.get("job_description_full", "")
        desc = re.sub(r"<[^>]+>", "", desc)  # remove HTML tags
        desc = re.sub(r"&[a-zA-Z]+;", " ", desc)  # remove HTML entities
        desc = re.sub(r"\s+", " ", desc).strip()
        job["job_description_full"] = desc

        # ── Create summary (truncated description) ──
        if len(desc) > max_summary_chars:
            # Truncate at last space before the limit to avoid cutting words
            job["job_description_summary"] = (
                desc[:max_summary_chars].rsplit(" ", 1)[0] + "..."
            )
        else:
            job["job_description_summary"] = desc

        # ── Standardize experience field ──
        exp = job.get("experience_required", "")
        if exp:
            exp = re.sub(r"\s*to\s*", "-", exp, flags=re.IGNORECASE)
            exp = re.sub(
                r"\s*yrs?\b", " years", exp, flags=re.IGNORECASE
            )
            exp = re.sub(r"\s+", " ", exp).strip()
            job["experience_required"] = exp

        # ── Normalize employment type ──
        emp_type = job.get("employment_type", "").lower()
        for pattern, canonical in _EMPLOYMENT_TYPE_MAP.items():
            if pattern in emp_type:
                job["employment_type"] = canonical
                break

    logger.info(f"Normalize: processed {len(jobs)} jobs")
    return jobs
