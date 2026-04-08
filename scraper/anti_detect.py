"""Anti-detection utilities: random delays, mouse simulation, block detection."""

import random
import asyncio
import logging
from playwright.async_api import Page

from config.settings import (
    SCROLL_DELAY_MIN,
    SCROLL_DELAY_MAX,
    DETAIL_DELAY_MIN,
    DETAIL_DELAY_MAX,
    SEARCH_DELAY_MIN,
    SEARCH_DELAY_MAX,
    IDLE_PAUSE_MIN,
    IDLE_PAUSE_MAX,
    IDLE_PAUSE_EVERY,
)
from scraper.selectors import SELECTORS

logger = logging.getLogger(__name__)

# Action counter for idle pause scheduling
_action_count = 0
_next_idle_at = random.randint(*IDLE_PAUSE_EVERY)


async def random_delay(min_s: float, max_s: float):
    """Sleep for a random duration between min_s and max_s seconds."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def scroll_delay():
    await random_delay(SCROLL_DELAY_MIN, SCROLL_DELAY_MAX)


async def detail_delay():
    await random_delay(DETAIL_DELAY_MIN, DETAIL_DELAY_MAX)


async def search_delay():
    await random_delay(SEARCH_DELAY_MIN, SEARCH_DELAY_MAX)


async def maybe_idle_pause():
    """Occasionally pause longer to simulate human reading behavior."""
    global _action_count, _next_idle_at
    _action_count += 1
    if _action_count >= _next_idle_at:
        pause = random.uniform(IDLE_PAUSE_MIN, IDLE_PAUSE_MAX)
        logger.debug(f"Idle pause: {pause:.1f}s (after {_action_count} actions)")
        await asyncio.sleep(pause)
        _action_count = 0
        _next_idle_at = random.randint(*IDLE_PAUSE_EVERY)


async def human_click(page: Page, locator):
    """Move mouse near the element then click, simulating human behavior."""
    try:
        box = await locator.bounding_box()
        if box:
            # Move to a random point near the target first
            offset_x = random.randint(-5, 5)
            offset_y = random.randint(-5, 5)
            target_x = box["x"] + box["width"] / 2 + offset_x
            target_y = box["y"] + box["height"] / 2 + offset_y
            await page.mouse.move(target_x, target_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        await locator.click()
    except Exception:
        # Fallback: direct click
        await locator.click()


async def is_blocked(page: Page) -> bool:
    """Check if Google has shown a CAPTCHA or block page."""
    # Check for CAPTCHA iframe
    for sel in SELECTORS["captcha_indicator"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1000):
                logger.warning("CAPTCHA detected!")
                return True
        except Exception:
            pass

    # Check page text for block indicators
    try:
        body_text = await page.inner_text("body", timeout=2000)
        body_lower = body_text.lower()
        for indicator in SELECTORS["block_indicator_text"]:
            if indicator in body_lower:
                logger.warning(f"Block indicator found: '{indicator}'")
                return True
    except Exception:
        pass

    return False
