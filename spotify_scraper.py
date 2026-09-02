import json
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
import requests

from spotify_pathfinder import SpotifyPathfinder


class SpotifyScraper:
    """Extract Spotify metadata and perform login-free Web Player searches.

    Everything here is anonymous / no-credentials-required by design:
    - Track & playlist metadata comes from the public embed pages.
    - Search comes from the internal Web Player Pathfinder API.

    Deliberately does NOT use the authenticated Spotify Web API
    (spotipy / Client Credentials): that path fails on Spotify-owned
    editorial playlists (e.g. "Today's Top Hits") and isn't needed anyway,
    since Pathfinder already returns everything we need anonymously.
    """

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

    def _backfill_album_via_pathfinder(
        self, track_id: str, artist: str, title: str
    ) -> Optional[str]:
        """Recover album name for a track using the anonymous Pathfinder
        search API, since the embed page never exposes album data
        (confirmed absent on multiple real album tracks).

        Matches on exact spotify_id first; falls back to the top search
        result if no exact ID match is found (title/artist can differ
        slightly in formatting between the two endpoints).
        """
        try:
            results = self._pathfinder.search(f"{artist} - {title}", limit=5)
        except Exception:
            return None

        if not results:
            return None

        for result in results:
            if result.get("spotify_id") == track_id:
                return result.get("album")

        # No exact ID match — best-effort fallback to the top hit.
        return results[0].get("album")

    def get_track_metadata(self, track_id: str) -> Dict:
        """Extract metadata for a single track from the embed page, with
        album name backfilled via an anonymous Pathfinder search since the
        embed endpoint doesn't expose it.
        """
        data = self._get_embed_json("track", track_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]

        title = entity.get("title") or entity.get("name", "Unknown Title")

        artists_data = entity.get("artists", [])
        artist = (
            ", ".join(a["name"] for a in artists_data if "name" in a)
            if artists_data else "Unknown Artist"
        )

        year = None
        release_date = entity.get("releaseDate")
        if isinstance(release_date, dict) and release_date.get("isoString"):
            year = release_date["isoString"][:4]

        # Confirmed field path: entity.visualIdentity.image (list of
        # {url, maxHeight, maxWidth}) — NOT album.images or
        # visuals.avatarImage, which don't exist on current embed responses.
        cover_url = ""
        images = entity.get("visualIdentity", {}).get("image", [])
        if images:
            largest = max(images, key=lambda img: img.get("maxWidth", 0))
            cover_url = largest.get("url", "")

        album = self._backfill_album_via_pathfinder(track_id, artist, title)
        if not album:
            album = "Unknown Album"

        return {
            "id": track_id,
            "type": "track",
            "title": title,
            "artist": artist,
            "album": album,
            "year": year,
            "cover_url": cover_url,
            "search_query": f"{artist} - {title} Audio",
        }

    def get_playlist_data(self, playlist_id: str) -> tuple[str, List[Dict]]:
        """Fetch the playlist's own name (from the embed page — confirmed
        correct there) together with its FULL track list, fetched via the
        paginated Pathfinder fetchPlaylistContents API.

        The embed page's own trackList caps out at 100 tracks with no
        pagination support at all (confirmed on a real 5000+ track
        playlist), so it's only used for the playlist name/metadata here —
        Pathfinder is the actual track source, and also gives us album,
        album artist, track/disc number, and year for every track, which
        the embed page doesn't expose even for its first 100.
        """
        data = self._get_embed_json("playlist", playlist_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]

        playlist_name = (
            entity.get("name")
            or entity.get("title")
            or "Unknown Playlist"
        )

        tracks, total_count = self._pathfinder.get_playlist_tracks(playlist_id)

        if total_count and len(tracks) != total_count:
            print(
                f"⚠️ Expected {total_count} tracks but got {len(tracks)} —"
                " some items may have been skipped (unavailable/local files)."
            )

        return playlist_name, tracks

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """Extract metadata for all tracks inside a public playlist.

        Kept for backward compatibility (used by parse_url / process_url,
        which only need the track list). Use get_playlist_data directly
        when you also need the playlist's name.
        """
        _, tracks = self.get_playlist_data(playlist_id)
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
