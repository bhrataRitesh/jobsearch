"""
careers_finder/locate_careers_page.py

Phase 2: For each company in ``companies.csv``, finds the actual
careers/jobs page URL and detects the ATS provider.

Algorithm:
1. Fetch the company homepage HTML.
2. Parse all <a> tags and score them by career-related keywords in
   both ``href`` and visible text.
3. Pick the highest-scoring link, resolve to absolute URL.
4. If no match, try common fallback paths (``/careers``, ``/jobs``, etc.)
   with HEAD requests.
5. If still nothing, mark ``careers_url = "NOT_FOUND"``.
6. Follow redirects to get the final URL.
7. Detect ATS provider by matching the final URL against known patterns
   from ``config/ats_patterns.yaml``.
8. Extract ATS-specific company token (for API calls in Phase 3).
"""
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import yaml
from tqdm import tqdm

logger = logging.getLogger(__name__)


def run_phase2_careers_finder(
    companies_df: pd.DataFrame, config: dict
) -> pd.DataFrame:
    """
    Find careers URLs and detect ATS type for all companies.

    Args:
        companies_df: DataFrame from Phase 1 (or loaded from
            ``output/companies.csv``).
        config: Parsed ``settings.yaml`` dict.

    Returns:
        DataFrame with added columns: ``careers_url``, ``ats_type``,
        ``ats_token``. Also saved to ``output/companies_with_careers_url.csv``.
    """
    # ── Load ATS patterns ──
    ats_patterns_path = Path("config/ats_patterns.yaml")
    with open(ats_patterns_path, "r") as f:
        ats_config = yaml.safe_load(f)

    careers_keywords = config.get("careers_page", {}).get(
        "url_keywords",
        ["career", "careers", "jobs", "join-us", "hiring"],
    )
    fallback_paths = config.get("careers_page", {}).get(
        "fallback_paths",
        ["/careers", "/jobs", "/careers/", "/about/careers"],
    )

    timeout = config.get("http", {}).get("timeout_seconds", 15)
    user_agent = config.get("http", {}).get(
        "user_agent", "JobSearchBot/1.0"
    )
    headers = {"User-Agent": user_agent}

    results: list[dict] = []

    for _, row in tqdm(
        companies_df.iterrows(),
        total=len(companies_df),
        desc="Phase 2: Finding careers pages",
    ):
        website = row.get("website", "")
        company_name = row.get("company_name", "")

        if not website or website == "NOT_FOUND":
            result = row.to_dict()
            result["careers_url"] = "NOT_FOUND"
            result["ats_type"] = "unknown"
            result["ats_token"] = ""
            results.append(result)
            continue

        # Ensure website has a scheme
        if not website.startswith("http"):
            website = f"https://{website}"

        careers_url = "NOT_FOUND"

        # ── Step 1: Fetch homepage and look for career links ──
        try:
            resp = requests.get(
                website,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )
            resp.raise_for_status()

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "lxml")

            best_score = 0
            best_link = None

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].lower()
                text = a_tag.get_text(strip=True).lower()

                score = 0
                for keyword in careers_keywords:
                    if keyword in href:
                        score += 2  # href match is stronger signal
                    if keyword in text:
                        score += 1

                if score > best_score:
                    best_score = score
                    best_link = a_tag["href"]

            if best_link and best_score >= 2:
                careers_url = urljoin(website, best_link)

        except Exception as e:
            logger.debug(f"Failed to fetch {website}: {e}")

        # ── Step 2: Try fallback paths if no link found ──
        if careers_url == "NOT_FOUND":
            for path in fallback_paths:
                test_url = urljoin(website, path)
                try:
                    resp = requests.head(
                        test_url,
                        headers=headers,
                        timeout=10,
                        allow_redirects=True,
                    )
                    if resp.status_code == 200:
                        careers_url = resp.url  # final redirected URL
                        break
                except Exception:
                    continue

        # ── Step 3: Follow redirects to get the final URL ──
        if careers_url != "NOT_FOUND":
            try:
                resp = requests.head(
                    careers_url,
                    headers=headers,
                    timeout=10,
                    allow_redirects=True,
                )
                careers_url = resp.url  # final URL after redirects
            except Exception:
                pass

        # ── Step 4: Detect ATS type ──
        ats_type = ats_config.get("default_ats_type", "generic")
        for pattern in ats_config.get("patterns", []):
            if pattern["substring"] in careers_url.lower():
                ats_type = pattern["ats_type"]
                break

        # ── Step 5: Extract ATS token ──
        ats_token = _extract_ats_token(careers_url, ats_type)

        result = row.to_dict()
        result["careers_url"] = careers_url
        result["ats_type"] = (
            ats_type if careers_url != "NOT_FOUND" else "unknown"
        )
        result["ats_token"] = ats_token
        results.append(result)

    result_df = pd.DataFrame(results)

    # ── Save ──
    output_path = Path("output/companies_with_careers_url.csv")
    output_path.parent.mkdir(exist_ok=True)
    result_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # ── Log stats ──
    logger.info(
        f"Phase 2 complete: {len(result_df)} companies processed, "
        f"saved to {output_path}"
    )
    found = result_df[result_df["careers_url"] != "NOT_FOUND"]
    total = len(result_df)
    logger.info(
        f"  Careers URL found: {len(found)}/{total} "
        f"({len(found) / max(total, 1) * 100:.0f}%)"
    )
    for ats_name, count in result_df["ats_type"].value_counts().items():
        logger.info(f"  ATS type '{ats_name}': {count} companies")

    return result_df


def _extract_ats_token(url: str, ats_type: str) -> str:
    """
    Extract the company-specific token from an ATS URL.

    Examples::

        "https://boards.greenhouse.io/companyname"  → "companyname"
        "https://jobs.lever.co/companyname"          → "companyname"
        "https://company.wd1.myworkdayjobs.com/..."  → "company"
    """
    parsed = urlparse(url)

    if ats_type == "greenhouse":
        # Pattern: boards.greenhouse.io/{token}
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return path_parts[0]

    elif ats_type == "lever":
        # Pattern: jobs.lever.co/{token}
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            return path_parts[0]

    elif ats_type == "workday":
        # Pattern: {token}.wd{N}.myworkdayjobs.com/...
        match = re.match(
            r"^([^.]+)\.wd\d+\.myworkdayjobs\.com", parsed.netloc
        )
        if match:
            return match.group(1)

    return ""
