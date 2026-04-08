"""Data models for scraped business leads."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Business(BaseModel):
    """A business scraped from Google Maps."""

    name: str
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    email: Optional[str] = None
    has_website: bool = False
    website_url: Optional[str] = None
    google_maps_url: Optional[str] = None
    metro_area: str = ""
    search_query: str = ""
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def dedup_key(self) -> str:
        """Composite key for deduplication: normalized name + phone or address."""
        normalized_name = self.name.lower().strip()
        phone_digits = "".join(filter(str.isdigit, self.phone or ""))
        secondary = phone_digits if phone_digits else (self.address or "").lower().strip()
        return f"{normalized_name}::{secondary}"

    def to_csv_dict(self) -> dict:
        """Convert to a flat dict suitable for CSV export."""
        return {
            "Name": self.name,
            "Category": self.category or "",
            "Address": self.address or "",
            "Phone": self.phone or "",
            "Email": self.email or "",
            "Rating": self.rating if self.rating is not None else "",
            "Reviews": self.review_count if self.review_count is not None else "",
            "Has Website": "Yes" if self.has_website else "No",
            "Website URL": self.website_url or "",
            "Google Maps URL": self.google_maps_url or "",
            "Metro Area": self.metro_area,
            "Search Query": self.search_query,
            "Scraped At": self.scraped_at.isoformat(),
        }
