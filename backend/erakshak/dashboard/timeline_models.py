"""Timeline event data models for E-RAKSHAK."""

from dataclasses import dataclass, asdict
from typing import Optional, Any


@dataclass
class TimelineEvent:
    id: str
    case_id: str
    exhibit_id: str
    timestamp: str
    timestamp_sort: int
    bucket_15m: str
    bucket_1h: str
    source_app: str
    source_type: str
    category: str
    event_type: str
    direction: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    actor: Optional[str] = None
    sender: Optional[str] = None
    receiver: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    location_accuracy: Optional[float] = None
    media_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    file_path: Optional[str] = None
    deleted_status: Optional[str] = None
    recovered_status: Optional[str] = None
    confidence: str = "high"
    source_file: Optional[str] = None
    source_hash: Optional[str] = None
    parser: Optional[str] = None
    raw_ref: Optional[str] = None
    raw_json: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the dataclass instance to a dict."""
        return asdict(self)
