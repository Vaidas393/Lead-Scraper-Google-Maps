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

# Mapping of full US state names -> 2-letter abbreviation (case-insensitive lookup)
US_STATE_MAP: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


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


def _resolve_states(raw_states: list[str]) -> set[str]:
    """
    Convert a list of state inputs (abbreviations OR full names) to uppercase abbreviations.
    e.g. ["Texas", "FL", "new york"] -> {"TX", "FL", "NY"}
    """
    resolved = set()
    for s in raw_states:
        upper = s.upper()
        lower = s.lower()
        if upper in {v for v in US_STATE_MAP.values()}:
            resolved.add(upper)
        elif lower in US_STATE_MAP:
            resolved.add(US_STATE_MAP[lower])
        else:
            logger.warning(f"Unknown state '{s}' — skipping. Use abbreviation (TX) or full name (Texas).")
    return resolved


def parse_args():
    parser = argparse.ArgumentParser(
        description="Google Maps Lead Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Interactive mode (recommended)
  python main.py --state Texas Florida    # Scrape specific states by full name
  python main.py --state TX FL            # Same using abbreviations
  python main.py --metros 3 --categories 2  # Quick test run
  python main.py --headless               # Run without browser window
"""
    )
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
        help="Run browser in headless mode (no visible window)"
    )
    parser.add_argument(
        "--state", type=str, nargs="+", metavar="STATE",
        help="Filter by state(s) — accepts full name or abbreviation, e.g. --state Texas Florida"
    )
    parser.add_argument(
        "--yes", "-y", action="store_true",
        help="Skip interactive prompts and run with defaults"
    )
    return parser.parse_args()


def _interactive_prompt() -> dict:
    """
    Guide the user through configuration interactively.
    Returns a dict with keys: state_filter, category_limit, metro_limit, headless.
    """
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║      Google Maps Lead Scraper — Setup Wizard     ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    # --- State filter ---
    available_abbrs = sorted({m["state"] for m in METROS})
    print(f"Available states: {', '.join(available_abbrs)}")
    print("Enter state name(s) or abbreviation(s) to filter (comma-separated),")
    state_input = input("or press ENTER to scrape ALL states: ").strip()
    raw_states = [s.strip() for s in state_input.split(",") if s.strip()] if state_input else []

    # --- Category limit ---
    print(f"\nThere are {len(CATEGORIES)} business categories configured.")
    cat_input = input("How many categories to scrape? (ENTER = all): ").strip()
    category_limit = int(cat_input) if cat_input.isdigit() else None

    # --- Headless ---
    headless_input = input("\nRun in headless mode? (browser hidden) [y/N]: ").strip().lower()
    headless = headless_input in ("y", "yes")

    print()
    return {"raw_states": raw_states, "category_limit": category_limit, "metro_limit": None, "headless": headless}


async def run():
    args = parse_args()
    setup_logging()

    # ── Interactive mode: triggered when no filtering args are provided ──
    no_args_given = not args.state and not args.metros and not args.categories and not args.headless and not args.yes
    if no_args_given:
        cfg = _interactive_prompt()
        raw_states = cfg["raw_states"]
        category_limit = cfg["category_limit"]
        metro_limit = cfg["metro_limit"]
        if cfg["headless"]:
            settings.HEADLESS = True
    else:
        raw_states = args.state or []
        category_limit = args.categories
        metro_limit = args.metros
        if args.headless:
            settings.HEADLESS = True

    metros = METROS[:metro_limit] if metro_limit else METROS
    categories = CATEGORIES[:category_limit] if category_limit else CATEGORIES

    # ── Filter metros by state ──
    if raw_states:
        state_filter = _resolve_states(raw_states)
        if not state_filter:
            logger.error("No valid states found after resolving input. Exiting.")
            return
        metros = [m for m in metros if m.get("state", "").upper() in state_filter]
        if not metros:
            logger.error(f"No metros found for state(s): {', '.join(state_filter)}")
            return
        logger.info(f"Filtered to {len(metros)} metro(s) in state(s): {', '.join(state_filter)}")

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

                    # Incremental dedup + export: called immediately after each business
                    unique_in_search: list = []

                    def on_business(b):
                        unique = dedup.deduplicate([b])
                        if unique:
                            export_raw(unique)
                            unique_in_search.append(unique[0])

                    # Execute the search and scrape (writes to CSV per-business)
                    businesses = await search_and_scrape(
                        page, query, metro_name,
                        state=metro.get("state", ""),
                        on_business=on_business,
                    )
                    detail_visits += len(businesses)

                    if not businesses:
                        logger.warning(
                            f"  {pair_label} Search returned 0 businesses — "
                            "possible block or no results. Will retry next run."
                        )
                        progress.mark_failed(city, category)
                        continue

                    # Checkpoint raw list for recovery
                    save_checkpoint(city, category, businesses)

                    # Qualify and export leads from the unique set
                    leads = filter_qualified(unique_in_search)
                    if leads:
                        export_qualified(leads)
                        total_leads += len(leads)

                    progress.mark_completed(city, category)
                    clear_checkpoint(city, category)

                    logger.info(
                        f"  {pair_label} Done: {len(businesses)} found, "
                        f"{len(unique_in_search)} unique, {len(leads)} qualified leads"
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
