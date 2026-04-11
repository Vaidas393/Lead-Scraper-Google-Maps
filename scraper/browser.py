"""Playwright browser lifecycle with stealth configuration."""

import random
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import Stealth

from config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser and context with anti-detection."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def start(self) -> Page:
        """Launch browser and return a stealth page."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.HEADLESS,
            args=settings.BROWSER_ARGS,
        )
        return await self.new_context()

    async def new_context(self) -> Page:
        """Create a fresh browser context with randomized fingerprint."""
        if self._context:
            await self._context.close()

        viewport = {
            "width": random.randint(*settings.VIEWPORT_WIDTH_RANGE),
            "height": random.randint(*settings.VIEWPORT_HEIGHT_RANGE),
        }
        user_agent = random.choice(settings.USER_AGENTS)

        self._context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            geolocation=None,
            permissions=[],
        )

        # playwright-stealth 2.x: Stealth().apply_stealth_async (replaces removed stealth_async)
        await Stealth().apply_stealth_async(self._context)
        self._page = await self._context.new_page()

        logger.info(
            f"New context: viewport={viewport['width']}x{viewport['height']}, "
            f"UA={user_agent[:50]}..."
        )
        return self._page

    @property
    def page(self) -> Page | None:
        return self._page

    async def close(self):
        """Clean shutdown."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed.")
