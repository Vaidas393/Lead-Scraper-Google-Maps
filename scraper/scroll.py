"""Infinite scroll handler for Google Maps results feed."""

import logging
from playwright.async_api import Page

from config.settings import MAX_SCROLLS_PER_SEARCH, SCROLL_NO_NEW_RESULTS_LIMIT
from scraper.selectors import SELECTORS
from scraper.anti_detect import scroll_delay, maybe_idle_pause

logger = logging.getLogger(__name__)


async def _find_feed(page: Page):
    """Locate the scrollable results feed element."""
    for sel in SELECTORS["results_feed"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=3000):
                return el
        except Exception:
            continue
    return None


async def _is_end_of_list(page: Page) -> bool:
    """Check if we've reached the end of the results list."""
    for sel in SELECTORS["end_of_list"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                return True
        except Exception:
            continue
    return False


async def _count_result_cards(page: Page) -> int:
    """Count the number of result link elements currently loaded."""
    for sel in SELECTORS["result_link"]:
        try:
            count = await page.locator(sel).count()
            if count > 0:
                return count
        except Exception:
            continue
    return 0


async def scroll_results(page: Page) -> int:
    """
    Scroll through the Google Maps results feed to load all results.

    Returns the total number of result cards loaded.
    """
    feed = await _find_feed(page)
    if not feed:
        logger.warning("Could not find results feed element.")
        return 0

    prev_count = await _count_result_cards(page)
    no_new_count = 0

    for scroll_num in range(1, MAX_SCROLLS_PER_SEARCH + 1):
        # Scroll the feed to bottom
        await feed.evaluate("el => el.scrollTop = el.scrollHeight")
        await scroll_delay()

        # Check end of list
        if await _is_end_of_list(page):
            logger.info(f"Reached end of list after {scroll_num} scrolls.")
            break

        # Count new results
        current_count = await _count_result_cards(page)
        if current_count <= prev_count:
            no_new_count += 1
            if no_new_count >= SCROLL_NO_NEW_RESULTS_LIMIT:
                logger.info(
                    f"No new results after {SCROLL_NO_NEW_RESULTS_LIMIT} scrolls. "
                    f"Stopping at {current_count} results."
                )
                break
        else:
            no_new_count = 0
            logger.debug(
                f"Scroll {scroll_num}: {prev_count} -> {current_count} results"
            )

        prev_count = current_count
        await maybe_idle_pause()

    total = await _count_result_cards(page)
    logger.info(f"Scroll complete. Total results loaded: {total}")
    return total
