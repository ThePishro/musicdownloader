import json
from pathlib import Path
from typing import Dict, List, Tuple

from halo import Halo
from tqdm import tqdm
from colorama import Fore, Style, init

from spotify_scraper import SpotifyScraper
from utils import sanitize_filename

init(autoreset=True)
COLOR_SUCCESS = Fore.GREEN
COLOR_ERROR = Fore.RED
COLOR_WARN = Fore.YELLOW
COLOR_INFO = Fore.CYAN
COLOR_RESET = Style.RESET_ALL


class SpotifyPlaylistExporter:
    """Exports a Spotify playlist into exported_playlists/<Playlist Name>/,
    containing:

      - playlist.json  Full track metadata (id, title, artist, album,
                        cover_url, search_query, ...) for every track.
                        Meant to be reusable later by a "download whole
                        playlist from this JSON" flow without re-scraping
                        Spotify.
      - playlist.txt    Plain "Artist - Song" lines, one per track, for
                        personal reference/other tools.

    Uses SpotifyScraper's anonymous embed-page scraping — no API
    credentials required, and (unlike the Spotify Web API) not restricted
    on Spotify-owned editorial playlists like "Today's Top Hits".
    """

    def __init__(self):
        self.scraper = SpotifyScraper()

    def _fetch_playlist(self, playlist_url: str) -> Tuple[str, str, List[Dict]]:
        """Validate the URL and fetch (playlist_id, playlist_name, tracks)."""
        entity_type, playlist_id = self.scraper.extract_id(playlist_url)
        if entity_type != "playlist":
            raise ValueError(
                "This URL is a track link, not a playlist link. Use the"
                " 'Download from Spotify URL' option for single tracks."
            )

        playlist_name, tracks = self.scraper.get_playlist_data(playlist_id)
        return playlist_id, playlist_name, tracks

    def export_playlist(
        self, playlist_url: str, base_output_dir: str = "exported_playlists"
    ) -> bool:
        spinner = Halo(
            text=f"{COLOR_INFO}Fetching playlist information...{COLOR_RESET}",
            spinner="dots",
        )
        spinner.start()

        try:
            playlist_id, playlist_name, tracks = self._fetch_playlist(
                playlist_url)
        except ValueError as e:
            spinner.fail(f"{COLOR_ERROR}❌ {e}{COLOR_RESET}")
            return False
        except Exception as e:
            spinner.fail(
                f"{COLOR_ERROR}❌ Could not fetch playlist: {e}{COLOR_RESET}")
            return False

        total_tracks = len(tracks)
        if total_tracks == 0:
            spinner.fail(
                f"{COLOR_ERROR}❌ No tracks found. The playlist may be private,"
                f" empty, or region-restricted.{COLOR_RESET}"
            )
            return False

        spinner.succeed(f"Found {total_tracks} track(s) in '{playlist_name}'")

        folder_name = sanitize_filename(playlist_name)
        playlist_dir = Path(base_output_dir) / folder_name
        playlist_dir.mkdir(parents=True, exist_ok=True)

        json_path = playlist_dir / "playlist.json"
        txt_path = playlist_dir / "playlist.txt"

        lines = []
        for track in tqdm(
            tracks, desc="Processing tracks", unit="track", ncols=100
        ):
            artist = track.get("artist", "Unknown Artist")
            title = track.get("title", "Unknown Title")
            lines.append(f"{artist} - {title}")

        export_payload = {
            "playlist_name": playlist_name,
            "playlist_url": playlist_url,
            "playlist_id": playlist_id,
            "total_tracks": total_tracks,
            "tracks": tracks,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2, ensure_ascii=False)

        with open(txt_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        print(f"{COLOR_SUCCESS}\n✅ Playlist exported successfully:{COLOR_RESET}")
        print(f"   📁 {playlist_dir}")
        print(f"   📄 {json_path.name}  (full metadata, for future re-download)")
        print(f"   📄 {txt_path.name}  (Artist - Song, plain text)")
        return True
