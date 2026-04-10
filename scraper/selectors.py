"""
Centralized Google Maps selectors.

ALL CSS selectors, aria-label patterns, and XPath queries live here.
When Google changes its DOM, update THIS file only.

Strategy: prefer aria-label and role attributes (more stable than CSS classes).
Each key maps to a list of selectors tried in order (fallback chain).
"""

SELECTORS = {
    # --- Results List ---
    "results_feed": [
        'div[role="feed"]',
        "div.m6QErb.DxyBCb.kA9KIf.dS8AEf",
    ],
    "result_link": [
        "a.hfpxzc",
        'a[href*="/maps/place/"]',
    ],

    # --- Card-Level Quick Data ---
    "card_name": [
        "a.hfpxzc",  # aria-label on this element contains the business name
    ],
    "card_rating": [
        'span[aria-label*="stars"]',
        'span[role="img"][aria-label*="star"]',
    ],
    "card_reviews_count": [
        "span.UY7F9",
        'span[aria-label*="reviews"]',
    ],

    # --- Detail Panel ---
    "detail_name": [
        "h1.DUwDvf",
        "h1.fontHeadlineLarge",
        "h1",
    ],
    "detail_address": [
        'button[data-item-id="address"]',
        '*[aria-label*="Address"]',
        'button[data-tooltip="Copy address"]',
    ],
    "detail_phone": [
        'button[data-item-id*="phone"]',
        '*[aria-label*="Phone"]',
        'button[data-tooltip="Copy phone number"]',
    ],
    "detail_email": [
        'button[data-item-id*="email"]',
        '*[aria-label*="Email"]',
        'a[href^="mailto:"]',
    ],
    "detail_website": [
        'a[data-item-id="authority"]',
        '*[aria-label*="Website"]',
        '*[data-tooltip="Open website"]',
    ],
    "detail_rating": [
        "div.F7nice span[aria-hidden]",
        'span[aria-label*="stars"]',
    ],
    "detail_reviews_count": [
        'span[aria-label*="reviews"]',
    ],
    "detail_category": [
        'button[jsaction*="category"]',
        "span.DkEaL",
    ],

    # --- Scroll End Detection ---
    "end_of_list": [
        "span.HlvSq",
        'p.fontBodyMedium:has-text("end of the list")',
    ],

    # --- Detail Panel Load Signal ---
    "detail_loaded": [
        "h1.DUwDvf",
        'button[jsaction*="reviewlegaldisclosure"]',
        "h1",
    ],

    # --- CAPTCHA / Block Detection ---
    "captcha_indicator": [
        'iframe[src*="recaptcha"]',
        '#recaptcha',
    ],
    "block_indicator_text": [
        "unusual traffic",
        "automated queries",
        "not a robot",
    ],
}
