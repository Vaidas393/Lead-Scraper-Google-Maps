"""CSV and Excel export for leads."""

import csv
import logging
from pathlib import Path
from data.models import Business
from config.settings import LEADS_RAW_CSV, LEADS_QUALIFIED_CSV

logger = logging.getLogger(__name__)

CSV_HEADERS = [
    "Name", "Category", "Address", "Phone", "Business Email", "Rating", "Reviews",
    "Has Website", "Website URL", "Google Maps URL", "Metro Area", "State",
    "Search Query", "Scraped At",
]


def _ensure_csv(filepath: Path):
    """Create the CSV file with headers if it doesn't exist."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    if not filepath.exists():
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()


def append_to_csv(businesses: list[Business], filepath: Path):
    """Append businesses to a CSV file."""
    if not businesses:
        return

    _ensure_csv(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        for b in businesses:
            writer.writerow(b.to_csv_dict())

    logger.info(f"Appended {len(businesses)} records to {filepath.name}")


def export_raw(businesses: list[Business]):
    """Export all scraped businesses to the raw CSV."""
    append_to_csv(businesses, LEADS_RAW_CSV)


def export_qualified(businesses: list[Business]):
    """Export qualified leads to the qualified CSV."""
    append_to_csv(businesses, LEADS_QUALIFIED_CSV)


def get_csv_row_count(filepath: Path) -> int:
    """Count existing rows in a CSV (excluding header)."""
    if not filepath.exists():
        return 0
    with open(filepath, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # Subtract header
