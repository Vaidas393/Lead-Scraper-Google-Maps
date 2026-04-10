"""Core Google Maps scraping engine."""

import re
import logging
from urllib.parse import quote_plus, unquote
from playwright.async_api import Page

from config.settings import (
    RESULTS_FEED_TIMEOUT_MS,
    DETAIL_LOAD_TIMEOUT_MS,
    ELEMENT_CHECK_TIMEOUT_MS,
    WEBSITE_TIMEOUT_MS,
)
from data.models import Business
from scraper.selectors import SELECTORS
from scraper.scroll import scroll_results
from scraper.anti_detect import detail_delay, human_click, maybe_idle_pause

logger = logging.getLogger(__name__)


async def _try_selectors(page_or_locator, selector_list: list, timeout: int = None) -> str | None:
    """Try each selector in order. Return first match's text content."""
    timeout = timeout or ELEMENT_CHECK_TIMEOUT_MS
    for sel in selector_list:
        try:
            el = page_or_locator.locator(sel).first
            if await el.is_visible(timeout=timeout):
                return (await el.inner_text()).strip()
        except Exception:
            continue
    return None


async def _try_selectors_attr(page_or_locator, selector_list: list, attr: str, timeout: int = None) -> str | None:
    """Try each selector in order. Return first match's attribute value."""
    timeout = timeout or ELEMENT_CHECK_TIMEOUT_MS
    for sel in selector_list:
        try:
            el = page_or_locator.locator(sel).first
            if await el.is_visible(timeout=timeout):
                val = await el.get_attribute(attr)
                return val.strip() if val else None
        except Exception:
            continue
    return None


def _parse_review_count(text: str | None) -> int | None:
    """Extract numeric review count from text like '(1,234)' or '1234 reviews'."""
    if not text:
        return None
    numbers = re.findall(r"[\d,]+", text)
    if numbers:
        return int(numbers[0].replace(",", ""))
    return None


def _parse_rating(text: str | None) -> float | None:
    """Extract rating from text like '4.5' or '4.5 stars'."""
    if not text:
        return None
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        return float(match.group(1))
    return None


def _parse_aria_label_field(aria_value: str | None, prefix: str) -> str | None:
    """Extract value from aria-label like 'Address: 123 Main St'."""
    if aria_value and prefix in aria_value:
        return aria_value.split(prefix, 1)[1].strip()
    return aria_value


async def _has_website(page: Page) -> tuple[bool, str | None]:
    """Check if the detail panel shows a website link. Returns (has_website, url)."""
    for sel in SELECTORS["detail_website"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=ELEMENT_CHECK_TIMEOUT_MS):
                url = await el.get_attribute("href")
                return True, url
        except Exception:
            continue
    return False, None


async def _extract_detail_phone(page: Page) -> str | None:
    """Extract phone number from the detail panel."""
    for sel in SELECTORS["detail_phone"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=ELEMENT_CHECK_TIMEOUT_MS):
                # Try aria-label first (e.g., "Phone: (555) 123-4567")
                aria = await el.get_attribute("aria-label")
                if aria and "Phone" in aria:
                    return _parse_aria_label_field(aria, "Phone:") or _parse_aria_label_field(aria, "Phone ")
                # Fall back to text content
                text = await el.inner_text()
                if text and re.search(r"\d", text):
                    return text.strip()
        except Exception:
            continue
    return None


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EMAIL_FALSE_POSITIVES = {"@example.com", "@sentry.io", "@gmail.com"}
EMAIL_FALSE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js"}


def _is_valid_email(email: str) -> bool:
    """Filter out common false-positive emails."""
    lower = email.lower()
    if any(lower.endswith(ext) for ext in EMAIL_FALSE_EXTENSIONS):
        return False
    if any(fp in lower for fp in EMAIL_FALSE_POSITIVES):
        return False
    return True


async def _extract_detail_email(page: Page) -> str | None:
    """Extract email from the Google Maps detail panel."""
    for sel in SELECTORS["detail_email"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=ELEMENT_CHECK_TIMEOUT_MS):
                # Check for mailto href
                href = await el.get_attribute("href")
                if href and href.startswith("mailto:"):
                    email = unquote(href.replace("mailto:", "").split("?")[0].strip())
                    if _is_valid_email(email):
                        return email
                # Check aria-label
                aria = await el.get_attribute("aria-label")
                if aria:
                    match = EMAIL_RE.search(aria)
                    if match and _is_valid_email(unquote(match.group())):
                        return unquote(match.group())
                # Check text content
                text = await el.inner_text()
                if text:
                    match = EMAIL_RE.search(text)
                    if match and _is_valid_email(unquote(match.group())):
                        return unquote(match.group())
        except Exception:
            continue
    return None


async def _extract_email_from_website(page: Page, website_url: str) -> str | None:
    """Visit the business website and try to extract an email address."""
    new_page = None
    try:
        context = page.context
        new_page = await context.new_page()
        await new_page.goto(website_url, wait_until="domcontentloaded", timeout=WEBSITE_TIMEOUT_MS)

        # Try mailto links first
        mailto_links = new_page.locator('a[href^="mailto:"]')
        count = await mailto_links.count()
        for i in range(min(count, 5)):
            href = await mailto_links.nth(i).get_attribute("href")
            if href:
                email = unquote(href.replace("mailto:", "").split("?")[0].strip())
                if _is_valid_email(email):
                    return email

        # Fall back to regex on page text
        body_text = await new_page.inner_text("body")
        matches = EMAIL_RE.findall(body_text)
        for email in matches:
            email = unquote(email)
            if _is_valid_email(email):
                return email

    except Exception as e:
        logger.debug(f"Failed to extract email from website {website_url}: {e}")
    finally:
        if new_page:
            await new_page.close()
    return None


async def _extract_detail_address(page: Page) -> str | None:
    """Extract address from the detail panel."""
    for sel in SELECTORS["detail_address"]:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=ELEMENT_CHECK_TIMEOUT_MS):
                aria = await el.get_attribute("aria-label")
                if aria and "Address" in aria:
                    return _parse_aria_label_field(aria, "Address:") or _parse_aria_label_field(aria, "Address ")
                text = await el.inner_text()
                if text:
                    return text.strip()
        except Exception:
            continue
    return None


async def _wait_for_detail_panel(page: Page) -> bool:
    """Wait for the business detail panel to load."""
    for sel in SELECTORS["detail_loaded"]:
        try:
            el = page.locator(sel).first
            await el.wait_for(state="visible", timeout=DETAIL_LOAD_TIMEOUT_MS)
            return True
        except Exception:
            continue
    return False


async def search_and_scrape(
    page: Page,
    query: str,
    metro_area: str,
    state: str = "",
    on_business=None,
) -> list[Business]:
    """
    Execute a single search on Google Maps and extract all business details.

    Args:
        page: Playwright page with stealth applied.
        query: Search query like "plumbers in Houston TX".
        metro_area: Metro area name for tagging results.
        on_business: Optional callback called immediately after each business
                     is extracted. Signature: on_business(business: Business).
                     Use this for incremental CSV writes.

    Returns:
        List of Business objects extracted from this search.
    """
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    logger.info(f"Searching: {query} -> {url}")

    await page.goto(url, wait_until="domcontentloaded")

    # Wait for results feed
    feed_found = False
    for sel in SELECTORS["results_feed"]:
        try:
            await page.locator(sel).first.wait_for(
                state="visible", timeout=RESULTS_FEED_TIMEOUT_MS
            )
            feed_found = True
            break
        except Exception:
            continue

    if not feed_found:
        logger.warning(f"No results feed found for query: {query}")
        return []

    # Scroll to load all results
    total_results = await scroll_results(page)
    if total_results == 0:
        logger.warning(f"No results loaded for query: {query}")
        return []

    # Collect all result links
    results: list[Business] = []
    link_selector = SELECTORS["result_link"][0]
    links_count = await page.locator(link_selector).count()

    logger.info(f"Found {links_count} result cards. Extracting details...")

    for i in range(links_count):
        try:
            business = await _extract_single_result(page, link_selector, i, query, metro_area, state)
            if business:
                results.append(business)
                logger.debug(f"  [{i+1}/{links_count}] {business.name} | website={business.has_website} | email={business.email}")
                if on_business:
                    on_business(business)
        except Exception as e:
            logger.error(f"  [{i+1}/{links_count}] Failed to extract: {e}")
            continue

        await maybe_idle_pause()

    logger.info(f"Extracted {len(results)} businesses from '{query}'")
    return results


async def _extract_single_result(
    page: Page,
    link_selector: str,
    index: int,
    query: str,
    metro_area: str,
    state: str = "",
) -> Business | None:
    """Click into a single result and extract its business details."""
    # Re-locate the link (DOM may have shifted)
    link = page.locator(link_selector).nth(index)

    # Get the business name from aria-label before clicking.
    # Google's aria-label format: "Business Name · 4.5 stars · 23 reviews"
    # The separator can be " · " (U+00B7), " ‧ " (U+2027), or " • " (U+2022).
    raw_aria = await link.get_attribute("aria-label") or ""
    # Split on any middle-dot/bullet variant surrounded by optional spaces
    card_name = re.split(r"\s[·‧•]\s", raw_aria)[0].strip() if raw_aria else ""

    # Get the maps URL
    maps_url = await link.get_attribute("href") or ""

    # Click into the detail panel
    await human_click(page, link)
    await detail_delay()

    if not await _wait_for_detail_panel(page):
        logger.debug(f"Detail panel did not load for: {card_name}")
        # Try to go back to results
        await page.keyboard.press("Escape")
        await detail_delay()
        return None

    # Extract all fields from detail panel
    name = await _try_selectors(page, SELECTORS["detail_name"]) or card_name
    category = await _try_selectors(page, SELECTORS["detail_category"])
    address = await _extract_detail_address(page)
    phone = await _extract_detail_phone(page)
    has_website, website_url = await _has_website(page)

    # Email — try Maps detail panel first, then the business website
    email = await _extract_detail_email(page)
    if not email and has_website and website_url:
        email = await _extract_email_from_website(page, website_url)

    # Rating
    rating_text = await _try_selectors(page, SELECTORS["detail_rating"])
    if not rating_text:
        rating_text = await _try_selectors_attr(page, SELECTORS["card_rating"], "aria-label")
    rating = _parse_rating(rating_text)

    # Review count
    reviews_text = await _try_selectors(page, SELECTORS["detail_reviews_count"])
    if not reviews_text:
        reviews_text = await _try_selectors_attr(page, SELECTORS["detail_reviews_count"], "aria-label")
    review_count = _parse_review_count(reviews_text)

    # Navigate back to results list
    await page.keyboard.press("Escape")
    await detail_delay()

    # Wait for results feed to reappear
    for sel in SELECTORS["results_feed"]:
        try:
            await page.locator(sel).first.wait_for(state="visible", timeout=5000)
            break
        except Exception:
            continue

    return Business(
        name=name,
        category=category,
        address=address,
        phone=phone,
        email=email,
        rating=rating,
        review_count=review_count,
        has_website=has_website,
        website_url=website_url,
        google_maps_url=maps_url,
        metro_area=metro_area,
        state=state or None,
        search_query=query,
    )
