"""Checkpoint system for saving partial results within a single search."""

import json
import logging
from pathlib import Path
from data.models import Business
from config.settings import CHECKPOINT_DIR

logger = logging.getLogger(__name__)


def _checkpoint_path(city: str, category: str) -> Path:
    """Get the checkpoint file path for a city+category pair."""
    safe_name = f"{city}_{category}".replace(" ", "_").replace("/", "_")
    return CHECKPOINT_DIR / f"{safe_name}.json"


def save_checkpoint(city: str, category: str, businesses: list[Business]):
    """Save partial results to a checkpoint file."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(city, category)
    data = [b.model_dump(mode="json") for b in businesses]
    path.write_text(json.dumps(data), encoding="utf-8")
    logger.debug(f"Checkpoint saved: {len(businesses)} businesses -> {path.name}")


def load_checkpoint(city: str, category: str) -> list[Business]:
    """Load partial results from a checkpoint file."""
    path = _checkpoint_path(city, category)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        businesses = [Business.model_validate(d) for d in data]
        logger.info(f"Loaded checkpoint: {len(businesses)} businesses from {path.name}")
        return businesses
    except Exception as e:
        logger.warning(f"Failed to load checkpoint {path.name}: {e}")
        return []


def clear_checkpoint(city: str, category: str):
    """Remove a checkpoint file after successful completion."""
    path = _checkpoint_path(city, category)
    if path.exists():
        path.unlink()
