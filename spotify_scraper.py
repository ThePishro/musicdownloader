import json
import re
from typing import Dict, List
from bs4 import BeautifulSoup
import requests


class SpotifyScraper:
    """A standalone scraper to extract Spotify track, playlist, and search metadata without API keys or credentials."""

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _get_embed_json(self, entity_type: str, entity_id: str) -> dict:
        """Fetches the Spotify embed HTML and parses the __NEXT_DATA__ JSON script tag."""
        url = f"https://open.spotify.com/embed/{entity_type}/{entity_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if not script_tag:
            raise ValueError(
                f"Could not parse embed metadata for {entity_type}/{entity_id}."
            )

        return json.loads(script_tag.string)

    def extract_id(self, url: str) -> tuple[str, str]:
        """Helper method to extract the entity type ('track' or 'playlist') and the 22-character ID from a URL."""
        match = re.search(r"(track|playlist)[/:]([a-zA-Z0-9]{22})", url)
        if not match:
            raise ValueError("Invalid Spotify track or playlist URL.")
        return match.group(1), match.group(2)

    def get_track_metadata(self, track_id: str) -> Dict:
        """Extracts metadata for a single track."""
        data = self._get_embed_json("track", track_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]

        title = entity.get("name", "Unknown Title")

        artists_data = entity.get("artists", [])
        artists = (
            ", ".join([a["name"] for a in artists_data if "name" in a])
            if artists_data
            else "Unknown Artist"
        )

        album = "Unknown Album"
        if "album" in entity and isinstance(entity["album"], dict):
            album = entity["album"].get("name", "Unknown Album")
        elif "albumOfTrack" in entity and isinstance(entity["albumOfTrack"], dict):
            album = entity["albumOfTrack"].get("name", "Unknown Album")

        cover_url = ""
        images = []
        if "album" in entity and "images" in entity["album"]:
            images = entity["album"]["images"]
        elif "visuals" in entity and "avatarImage" in entity["visuals"]:
            cover_url = entity["visuals"]["avatarImage"].get("sources", [{}])[0].get(
                "url", ""
            )

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
        """Extracts metadata for all tracks inside a public playlist."""
        data = self._get_embed_json("playlist", playlist_id)
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
        track_list = entity.get("trackList", [])

        tracks = []
        for item in track_list:
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
        """Universal method: takes any Spotify URL and returns a list of track metadata dicts."""
        entity_type, entity_id = self.extract_id(spotify_url)
        if entity_type == "track":
            return [self.get_track_metadata(entity_id)]
        elif entity_type == "playlist":
            return self.get_playlist_tracks(entity_id)
        return []

    def search_tracks(self, query: str, max_results: int = 10) -> List[Dict]:
        """Searches Spotify using their public web player guest token mechanism."""
        try:
            # Step 1: Get a temporary guest access token from Spotify's web player endpoint
            token_res = requests.get(
                "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
                headers=self.headers,
                timeout=10,
            )
            token_res.raise_for_status()
            access_token = token_res.json().get("accessToken")

            if not access_token:
                print("⚠️ Could not acquire Spotify guest access token.")
                return []

            # Step 2: Query Spotify's official Web API search endpoint using the guest token
            search_url = "https://api.spotify.com/v1/search"
            params = {"q": query, "type": "track", "limit": max_results}
            api_headers = {
                **self.headers,
                "Authorization": f"Bearer {access_token}",
            }

            response = requests.get(
                search_url, headers=api_headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            tracks = data.get("tracks", {}).get("items", [])
            results = []

            for idx, item in enumerate(tracks, start=1):
                title = item.get("name", "Unknown Title")
                artists = ", ".join([a["name"] for a in item.get("artists", [])])
                album = item.get("album", {}).get("name", "Unknown Album")

                duration_ms = item.get("duration_ms", 0)
                mins, secs = divmod(int(duration_ms / 1000), 60)
                duration_str = f"{mins}:{secs:02d}"

                images = item.get("album", {}).get("images", [])
                cover_url = images[0].get("url", "") if images else ""

                results.append({
                    "index": idx,
                    "title": title,
                    "artist": artists,
                    "album": album,
                    "duration": duration_str,
                    "cover_url": cover_url,
                    "search_query": f"{artists} - {title} Audio",
                })

            return results

        except Exception as e:
            print(f"⚠️ Spotify search failed: {e}")
            return []