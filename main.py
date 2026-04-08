"""
Google Maps Lead Scraper — Main Entry Point

Scrapes Google Maps for businesses without websites but with reviews.
These are digitally underserved leads ideal for outreach.

Usage:
    python main.py                          # Full run: all metros, all categories
    python main.py --metros 3 --categories 2  # Test run: first 3 metros, 2 categories
    python main.py --headless               # Run in headless mode
"""

import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.metros import METROS
from config.categories import CATEGORIES
from config import settings
from scraper.browser import BrowserManager
from scraper.maps_scraper import search_and_scrape
from scraper.anti_detect import is_blocked, random_delay, search_delay
from data.dedup import Deduplicator
from data.qualifier import filter_qualified
from data.exporter import export_raw, export_qualified, get_csv_row_count
from persistence.progress import ProgressTracker
from persistence.checkpoint import save_checkpoint, clear_checkpoint

logger = logging.getLogger("gmaps_scraper")


def setup_logging():
    """Configure logging to console and file."""
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console: INFO
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
    ))
    root_logger.addHandler(console)

    # File: DEBUG
    file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)-7s | %(message)s"
    ))
    root_logger.addHandler(file_handler)


def parse_args():
    parser = argparse.ArgumentParser(description="Google Maps Lead Scraper")
    parser.add_argument(
        "--metros", type=int, default=None,
        help="Limit to first N metros (for testing)"
    )
    parser.add_argument(
        "--categories", type=int, default=None,
        help="Limit to first N categories (for testing)"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless mode"
    )
    return parser.parse_args()


async def run():
    args = parse_args()
    setup_logging()

    if args.headless:
        settings.HEADLESS = True

    metros = METROS[:args.metros] if args.metros else METROS
    categories = CATEGORIES[:args.categories] if args.categories else CATEGORIES

    total_pairs = len(metros) * len(categories)
    logger.info(f"Starting scraper: {len(metros)} metros x {len(categories)} categories = {total_pairs} searches")

    progress = ProgressTracker()
    dedup = Deduplicator()
    browser = BrowserManager()

    detail_visits = 0  # Track for context refresh
    total_leads = 0

    try:
        page = await browser.start()

        for metro_idx, metro in enumerate(metros):
            city = metro["search_term"]
            metro_name = metro["name"]

            logger.info(f"\n{'='*60}")
            logger.info(f"Metro [{metro_idx+1}/{len(metros)}]: {metro_name}")
            logger.info(f"{'='*60}")

            for cat_idx, category in enumerate(categories):
                # Skip completed pairs
                if progress.is_completed(city, category):
                    logger.info(f"  Skipping (already done): {category} in {city}")
                    continue

                progress.mark_in_progress(city, category)
                query = f"{category} in {city}"
                pair_label = f"[{metro_idx+1}/{len(metros)}][{cat_idx+1}/{len(categories)}]"

                logger.info(f"  {pair_label} Searching: {query}")

                try:
                    # Check for blocks before searching
                    if await is_blocked(page):
                        logger.warning("Blocked! Pausing and refreshing context...")
                        await random_delay(
                            settings.CAPTCHA_PAUSE_SECONDS,
                            settings.CAPTCHA_PAUSE_SECONDS + 60,
                        )
                        page = await browser.new_context()

                    # Execute the search and scrape
                    businesses = await search_and_scrape(page, query, metro_name)
                    detail_visits += len(businesses)

                    # Checkpoint
                    if businesses:
                        save_checkpoint(city, category, businesses)

                    # Deduplicate
                    unique = dedup.deduplicate(businesses)

                    # Export raw
                    export_raw(unique)

                    # Qualify and export leads
                    leads = filter_qualified(unique)
                    if leads:
                        export_qualified(leads)
                        total_leads += len(leads)

                    progress.mark_completed(city, category)
                    clear_checkpoint(city, category)

                    logger.info(
                        f"  {pair_label} Done: {len(businesses)} found, "
                        f"{len(unique)} unique, {len(leads)} qualified leads"
                    )

                    # Refresh browser context periodically
                    if detail_visits >= settings.CONTEXT_REFRESH_EVERY:
                        logger.info("Refreshing browser context...")
                        page = await browser.new_context()
                        detail_visits = 0

                    # Delay between searches
                    await search_delay()

                except Exception as e:
                    logger.error(f"  {pair_label} FAILED: {e}")
                    progress.mark_failed(city, category)
                    # Try to recover
                    try:
                        page = await browser.new_context()
                        detail_visits = 0
                    except Exception:
                        pass
                    continue

            # Longer break between cities
            if metro_idx < len(metros) - 1:
                logger.info(f"City break before next metro...")
                await random_delay(settings.CITY_BREAK_MIN, settings.CITY_BREAK_MAX)

    finally:
        # Always save state on exit
        dedup.save()
        progress.save()
        await browser.close()

        # Final summary
        stats = progress.stats
        raw_count = get_csv_row_count(settings.LEADS_RAW_CSV)
        qual_count = get_csv_row_count(settings.LEADS_QUALIFIED_CSV)

        logger.info(f"\n{'='*60}")
        logger.info("SCRAPER COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Searches completed: {stats['completed']}")
        logger.info(f"Searches failed:    {stats['failed']}")
        logger.info(f"Total businesses:   {raw_count}")
        logger.info(f"Qualified leads:    {qual_count}")
        logger.info(f"Dedup pool size:    {dedup.total_seen}")
        logger.info(f"Output: {settings.LEADS_QUALIFIED_CSV}")
        logger.info(f"{'='*60}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
