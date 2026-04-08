"""Global settings and tunables for the scraper."""

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
PROGRESS_FILE = OUTPUT_DIR / "progress.json"
SEEN_KEYS_FILE = OUTPUT_DIR / "seen_keys.json"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
LOG_FILE = OUTPUT_DIR / "scraper.log"
LEADS_RAW_CSV = OUTPUT_DIR / "leads_raw.csv"
LEADS_QUALIFIED_CSV = OUTPUT_DIR / "leads_qualified.csv"

# --- Browser ---
HEADLESS = False  # Headful mode is less detected
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

# --- Anti-Detection Delays (seconds) ---
SCROLL_DELAY_MIN = 1.5
SCROLL_DELAY_MAX = 3.5
DETAIL_DELAY_MIN = 2.0
DETAIL_DELAY_MAX = 4.0
SEARCH_DELAY_MIN = 5.0
SEARCH_DELAY_MAX = 10.0
CITY_BREAK_MIN = 30.0
CITY_BREAK_MAX = 60.0
IDLE_PAUSE_MIN = 10.0
IDLE_PAUSE_MAX = 30.0
IDLE_PAUSE_EVERY = (8, 15)  # random range: take idle pause every N actions

# --- Viewport Randomization ---
VIEWPORT_WIDTH_RANGE = (1200, 1920)
VIEWPORT_HEIGHT_RANGE = (800, 1080)

# --- Session Management ---
CONTEXT_REFRESH_EVERY = 50  # New browser context every N detail visits
CAPTCHA_PAUSE_SECONDS = 300  # 5 minute pause on CAPTCHA detection

# --- Scraping Limits ---
MAX_SCROLLS_PER_SEARCH = 25
SCROLL_NO_NEW_RESULTS_LIMIT = 3  # Stop after N consecutive scrolls with no new results
DETAIL_LOAD_TIMEOUT_MS = 10000
RESULTS_FEED_TIMEOUT_MS = 15000
ELEMENT_CHECK_TIMEOUT_MS = 2000
WEBSITE_TIMEOUT_MS = 8000  # Timeout for loading business websites to extract email

# --- Lead Qualification ---
MIN_RATING = 3.0
MIN_REVIEWS = 5

# --- Checkpoint ---
CHECKPOINT_EVERY = 20  # Save partial results every N businesses

# --- User Agents ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
