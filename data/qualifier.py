"""Lead qualification filters."""

import logging
from data.models import Business
from config.settings import MIN_RATING, MIN_REVIEWS

logger = logging.getLogger(__name__)


def is_qualified_lead(business: Business) -> bool:
    """
    Check if a business qualifies as a good lead.

    Criteria:
    - Does NOT have a website
    - Has a phone number
    - Rating >= MIN_RATING (default 3.0)
    - Review count >= MIN_REVIEWS (default 5)

    NOTE: Business Email is intentionally NOT required. A lead qualifies
    with or without a scraped email address.
    """
    if business.has_website:
        return False

    if not business.phone:
        return False

    if business.rating is not None and business.rating < MIN_RATING:
        return False

    if business.review_count is not None and business.review_count < MIN_REVIEWS:
        return False

    # If rating or review_count is None, we can't confirm quality
    # but we still include them (they have a phone and no website)
    return True


def filter_qualified(businesses: list[Business]) -> list[Business]:
    """Filter a list of businesses to only qualified leads."""
    qualified = [b for b in businesses if is_qualified_lead(b)]
    logger.info(
        f"Qualified {len(qualified)}/{len(businesses)} businesses as leads"
    )
    return qualified
