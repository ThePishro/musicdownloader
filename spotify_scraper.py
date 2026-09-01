import json
import re
from typing import Dict, List

from bs4 import BeautifulSoup
import requests

from spotify_pathfinder import SpotifyPathfinder


class SpotifyScraper:
    """Extract Spotify metadata and perform login-free Web Player searches."""

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._pathfinder = SpotifyPathfinder()

    def _get_embed_json(self, entity_type: str, entity_id: str) -> dict:
        """Fetch Spotify embed HTML and parse its __NEXT_DATA__ metadata."""
        url = f"https://open.spotify.com/embed/{entity_type}/{entity_id}"
        response = requests.get(url, headers=self.headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script_tag:
            raise ValueError(
                f"Could not parse embed metadata for {entity_type}/{entity_id}."
            )
        return json.loads(script_tag.string)

    def extract_id(self, url: str) -> tuple[str, str]:
        """Extract a Spotify track or playlist ID from a URL."""
        match = re.search(r"(track|playlist)[/:]([a-zA-Z0-9]{22})", url)
        if not match:
            raise ValueError("Invalid Spotify track or playlist URL.")
        return match.group(1), match.group(2)

    def get_track_metadata(self, track_id: str) -> Dict:
        """Extract metadata for a single track."""
        data = self._get_embed_json("track", track_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]

        title = entity.get("name", "Unknown Title")
        artists_data = entity.get("artists", [])
        artists = (
            ", ".join(a["name"] for a in artists_data if "name" in a)
            if artists_data else "Unknown Artist"
        )

        album = "Unknown Album"
        if isinstance(entity.get("album"), dict):
            album = entity["album"].get("name", "Unknown Album")
        elif isinstance(entity.get("albumOfTrack"), dict):
            album = entity["albumOfTrack"].get("name", "Unknown Album")

        cover_url = ""
        images = []
        if isinstance(entity.get("album"), dict):
            images = entity["album"].get("images", [])
        elif isinstance(entity.get("visuals"), dict):
            avatar = entity["visuals"].get("avatarImage", {})
            sources = avatar.get("sources", [])
            if sources:
                cover_url = sources[0].get("url", "")
        if not cover_url and images:
            cover_url = images[0].get("url", "")

        return {
            "id": track_id,
            "type": "track",
            "title": title,
            "artist": artists,
            "album": album,
            "cover_url": cover_url,
            "search_query": f"{artists} - {title} Audio",
        }

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Extract metadata for all tracks inside a public playlist."""
        data = self._get_embed_json("playlist", playlist_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
        tracks = []
        for item in entity.get("trackList", []):
            title = item.get("title", "Unknown Title")
            artist = item.get("subtitle", "Unknown Artist")
            tracks.append({
                "type": "track",
                "title": title,
                "artist": artist,
                "album": "Spotify Playlist",
                "cover_url": item.get("displayImage", ""),
                "search_query": f"{artist} - {title} Audio",
            })
        return tracks

    def parse_url(self, spotify_url: str) -> List[Dict]:
        """Parse a Spotify track or playlist URL into track metadata."""
        entity_type, entity_id = self.extract_id(spotify_url)
        if entity_type == "track":
            return [self.get_track_metadata(entity_id)]
        if entity_type == "playlist":
            return self.get_playlist_tracks(entity_id)
        return []

    def search_tracks(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search Spotify anonymously through the Web Player Pathfinder API."""
        try:
            return self._pathfinder.search(query, max_results)
        except Exception as e:
            print(f"⚠️ Spotify search failed: {e}")
            return []
