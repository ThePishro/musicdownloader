from typing import List
from ytmusicapi import YTMusic

from core.search.base import BaseSearchProvider
from core.models.track import TrackResult


class YouTubeMusicSearch(BaseSearchProvider):

    def __init__(self):
        self.ytmusic = YTMusic()

    def search(self, query: str, limit: int = 10) -> List[TrackResult]:
        results = self.ytmusic.search(
            query=query,
            filter="songs",
            limit=limit
        )

        tracks: List[TrackResult] = []

        for item in results:
            tracks.append(
                TrackResult(
                    platform="youtube_music",
                    title=item.get("title"),
                    artist=item["artists"][0]["name"] if item.get("artists") else "Unknown",
                    album=item["album"]["name"] if item.get("album") else None,
                    duration_sec=item.get("duration_seconds"),
                    year=item.get("year"),
                    url=f"https://music.youtube.com/watch?v={item['videoId']}",
                    source_id=item["videoId"],
                )
            )

        return tracks
