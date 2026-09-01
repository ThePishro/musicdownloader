from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackResult:
    platform: str
    title: str
    artist: str
    album: Optional[str]
    duration_sec: Optional[int]
    year: Optional[int]
    url: str
    source_id: str
