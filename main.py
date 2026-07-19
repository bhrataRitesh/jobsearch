"""
main.py — Pipeline Orchestrator

Orchestrates all 5 phases of the job scraper pipeline:
    Phase 1: Company Discovery
    Phase 2: Careers Page Locator
    Phase 3: Job Scraping
    Phase 4: Filter + Normalize + Dedup
    Phase 5: Final CSV Export

Each phase reads from the previous phase's output file (not just in-memory),
so any phase can be re-run independently using the ``--phase`` flag.

Usage::

    python main.py                        # Interactive: prompts for city
    python main.py --city Mumbai          # Specify city directly
    python main.py --city Mumbai --phase 3  # Re-run from Phase 3 onward
    python main.py --city Bangalore --log-level DEBUG  # Verbose logging
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from careers_finder.locate_careers_page import run_phase2_careers_finder
from discovery import run_phase1_discovery
from processing import run_phase4_processing
from scrapers import run_phase3_scrapers
from utils.csv_writer import export_final_csv
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


def load_config() -> dict:
    """
    Load and return the settings.yaml configuration.

    Raises:
        SystemExit: If the config file is not found.
    """
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def main() -> None:
    """Main entry point — parse args and run the pipeline."""

    # ── Parse CLI arguments ──
    parser = argparse.ArgumentParser(
        description=(
            "Job Listings Aggregator — discovers software companies "
            "in a city and scrapes their job listings into a CSV."
        )
    )
    parser.add_argument(
        "--city",
        type=str,
        help="Target city name (e.g. 'Mumbai')",
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=1,
        choices=[1, 2, 3, 4, 5],
        help=(
            "Start from this phase (default: 1). "
            "Phases 2+ read from the previous phase's output file."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    args = parser.parse_args()

    # ── Setup ──
    load_dotenv()
    setup_logging(log_level=args.log_level, log_file="output/scraper.log")
    config = load_config()

    city = args.city or config.get("city")
    if not city:
        city = input("Enter target city: ").strip()
    if not city:
        logger.error("No city provided. Exiting.")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info(f"Job Scraper starting for city: {city}")
    logger.info(f"Starting from Phase {args.phase}")
    logger.info("=" * 60)

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: Company Discovery
    # ═══════════════════════════════════════════════════════════
    if args.phase <= 1:
        logger.info(
            "=" * 20 + " PHASE 1: Company Discovery " + "=" * 20
        )
        companies_df = run_phase1_discovery(city, config)
    else:
        companies_path = output_dir / "companies.csv"
        if not companies_path.exists():
            logger.error(
                f"Phase 1 output not found: {companies_path}. "
                "Run Phase 1 first."
            )
            sys.exit(1)
        companies_df = pd.read_csv(companies_path)
        logger.info(
            f"Loaded {len(companies_df)} companies from {companies_path}"
        )

    if companies_df.empty:
        logger.error("No companies found. Cannot proceed.")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: Careers Page Locator
    # ═══════════════════════════════════════════════════════════
    if args.phase <= 2:
        logger.info(
            "=" * 20 + " PHASE 2: Careers Page Locator " + "=" * 20
        )
        companies_with_urls = run_phase2_careers_finder(
            companies_df, config
        )
    else:
        careers_path = output_dir / "companies_with_careers_url.csv"
        if not careers_path.exists():
            logger.error(
                f"Phase 2 output not found: {careers_path}. "
                "Run Phase 2 first."
            )
            sys.exit(1)
        companies_with_urls = pd.read_csv(careers_path)
        logger.info(
            f"Loaded {len(companies_with_urls)} companies "
            f"from {careers_path}"
        )

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: Job Scraping
    # ═══════════════════════════════════════════════════════════
    if args.phase <= 3:
        logger.info(
            "=" * 20 + " PHASE 3: Job Scraping " + "=" * 20
        )
        raw_jobs = run_phase3_scrapers(companies_with_urls, config)
    else:
        raw_jobs_path = output_dir / "raw_jobs.json"
        if not raw_jobs_path.exists():
            logger.error(
                f"Phase 3 output not found: {raw_jobs_path}. "
                "Run Phase 3 first."
            )
            sys.exit(1)
        with open(raw_jobs_path, "r", encoding="utf-8") as f:
            raw_jobs = json.load(f)
        logger.info(
            f"Loaded {len(raw_jobs)} raw jobs from {raw_jobs_path}"
        )

    # ═══════════════════════════════════════════════════════════
    # PHASE 4: Filter, Normalize, Dedup
    # ═══════════════════════════════════════════════════════════
    if args.phase <= 4:
        logger.info(
            "=" * 20 + " PHASE 4: Processing " + "=" * 20
        )
        processed_jobs = run_phase4_processing(raw_jobs, config)
    else:
        # No intermediate file for Phase 4 — reprocess from raw_jobs.json
        raw_jobs_path = output_dir / "raw_jobs.json"
        if not raw_jobs_path.exists():
            logger.error(
                f"Phase 3 output not found: {raw_jobs_path}. "
                "Run Phase 3 first."
            )
            sys.exit(1)
        with open(raw_jobs_path, "r", encoding="utf-8") as f:
            raw_jobs = json.load(f)
        processed_jobs = run_phase4_processing(raw_jobs, config)

    # ═══════════════════════════════════════════════════════════
    # PHASE 5: Final CSV Export
    # ═══════════════════════════════════════════════════════════
    logger.info("=" * 20 + " PHASE 5: CSV Export " + "=" * 20)
    output_file = export_final_csv(processed_jobs, city)

    logger.info("=" * 60)
    logger.info(f"DONE! Final output: {output_file}")
    logger.info(f"Total jobs in final CSV: {len(processed_jobs)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
