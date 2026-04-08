"""Deduplication of scraped businesses."""

import json
import logging
from pathlib import Path
from data.models import Business
from config.settings import SEEN_KEYS_FILE

logger = logging.getLogger(__name__)


class Deduplicator:
    """Tracks seen businesses to prevent duplicates across searches."""

    def __init__(self):
        self._seen: set[str] = set()
        self._load()

    def _load(self):
        """Load previously seen keys from disk."""
        if SEEN_KEYS_FILE.exists():
            try:
                data = json.loads(SEEN_KEYS_FILE.read_text(encoding="utf-8"))
                self._seen = set(data)
                logger.info(f"Loaded {len(self._seen)} previously seen businesses.")
            except Exception as e:
                logger.warning(f"Failed to load seen keys: {e}")

    def save(self):
        """Persist seen keys to disk."""
        SEEN_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SEEN_KEYS_FILE.write_text(
            json.dumps(list(self._seen)), encoding="utf-8"
        )

    def is_duplicate(self, business: Business) -> bool:
        """Check if this business has been seen before."""
        return business.dedup_key in self._seen

    def mark_seen(self, business: Business):
        """Record this business as seen."""
        self._seen.add(business.dedup_key)

    def deduplicate(self, businesses: list[Business]) -> list[Business]:
        """Filter out duplicates and mark new ones as seen."""
        unique = []
        dupes = 0
        for b in businesses:
            if self.is_duplicate(b):
                dupes += 1
            else:
                self.mark_seen(b)
                unique.append(b)

        if dupes > 0:
            logger.info(f"Removed {dupes} duplicates. Kept {len(unique)} unique businesses.")
        return unique

    @property
    def total_seen(self) -> int:
        return len(self._seen)
