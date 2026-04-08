"""Progress tracking for resumable scraping."""

import json
import logging
from pathlib import Path
from config.settings import PROGRESS_FILE

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks which (city, category) pairs have been completed."""

    def __init__(self):
        self._progress: dict[str, str] = {}  # key -> "completed" | "in_progress" | "failed"
        self._load()

    @staticmethod
    def _make_key(city: str, category: str) -> str:
        return f"{city}::{category}"

    def _load(self):
        """Load progress from disk."""
        if PROGRESS_FILE.exists():
            try:
                self._progress = json.loads(
                    PROGRESS_FILE.read_text(encoding="utf-8")
                )
                completed = sum(1 for v in self._progress.values() if v == "completed")
                logger.info(
                    f"Loaded progress: {completed} completed, "
                    f"{len(self._progress) - completed} remaining."
                )
            except Exception as e:
                logger.warning(f"Failed to load progress: {e}")

    def save(self):
        """Persist progress to disk."""
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS_FILE.write_text(
            json.dumps(self._progress, indent=2), encoding="utf-8"
        )

    def is_completed(self, city: str, category: str) -> bool:
        key = self._make_key(city, category)
        return self._progress.get(key) == "completed"

    def mark_in_progress(self, city: str, category: str):
        key = self._make_key(city, category)
        self._progress[key] = "in_progress"
        self.save()

    def mark_completed(self, city: str, category: str):
        key = self._make_key(city, category)
        self._progress[key] = "completed"
        self.save()

    def mark_failed(self, city: str, category: str):
        key = self._make_key(city, category)
        self._progress[key] = "failed"
        self.save()

    @property
    def stats(self) -> dict:
        completed = sum(1 for v in self._progress.values() if v == "completed")
        failed = sum(1 for v in self._progress.values() if v == "failed")
        in_progress = sum(1 for v in self._progress.values() if v == "in_progress")
        return {
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "total_tracked": len(self._progress),
        }
