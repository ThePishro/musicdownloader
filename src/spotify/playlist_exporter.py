import os
import time
from pathlib import Path
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
from halo import Halo
from tqdm import tqdm
from colorama import Fore, Style, init

init(autoreset=True)
COLOR_SUCCESS = Fore.GREEN
COLOR_ERROR   = Fore.RED
COLOR_WARN    = Fore.YELLOW
COLOR_INFO    = Fore.CYAN
COLOR_DIM     = Style.DIM
COLOR_RESET   = Style.RESET_ALL


class SpotifyPlaylistExporter:
    # Spotify editorial playlists (restricted)
    SPOTIFY_OWNED_PREFIXES = ("37i9dQZF",)

    def __init__(self):
        env_path = Path(__file__).parent.parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)

        client_id = os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise RuntimeError(f"{COLOR_ERROR}❌ Spotify credentials not found in .env{COLOR_RESET}")

        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )

        self.spotify = spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=20,
            retries=3,
        )

    def extract_playlist_id(self, playlist_url_or_id: str) -> str:
        s = playlist_url_or_id.strip()
        if "playlist/" in s:
            return s.split("playlist/")[-1].split("?")[0]
        return s

    def is_probably_spotify_owned(self, playlist_id: str) -> bool:
        return playlist_id.startswith(self.SPOTIFY_OWNED_PREFIXES)

    def format_time(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def export_playlist(self, playlist_url: str, output_file_path: str):
        spinner = Halo(text=f"{COLOR_INFO}Fetching playlist information...{COLOR_RESET}", spinner="dots")
        spinner.start()

        playlist_id = self.extract_playlist_id(playlist_url)

        # ✅ Detect Spotify-owned playlists BEFORE API call
        if self.is_probably_spotify_owned(playlist_id):
            spinner.fail(
                f"{COLOR_ERROR}❌ This playlist is owned by Spotify.\n"
                f"Since Nov 27, 2024, Spotify has restricted API access to editorial playlists.{COLOR_RESET}"
            )
            return False

        # ✅ Fetch playlist metadata
        try:
            playlist = self.spotify.playlist(playlist_id)
        except SpotifyException as e:
            if getattr(e, "http_status", None) == 404:
                spinner.fail(
                    f"{COLOR_ERROR}❌ Cannot access this playlist.\n"
                    f"It may be private or you may not have permission.{COLOR_RESET}"
                )
                return False
            spinner.fail(f"{COLOR_ERROR}❌ Spotify error: {e}{COLOR_RESET}")
            return False

        total_tracks = int(playlist["tracks"]["total"])
        spinner.succeed(f"Found {total_tracks} tracks")

        limit = 100
        offset = 0
        lines = []

        start_time = time.time()

        # ✅ FINAL tqdm format (no double comma, clean UX)
        pbar = tqdm(
            total=total_tracks,
            desc="Exporting playlist",
            unit="Track",
            ncols=120,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} Tracks{postfix}",
            leave=True,
        )

        # initial postfix
        pbar.set_postfix_str("Remaining ~--:--", refresh=True)

        while offset < total_tracks:
            try:
                response = self.spotify.playlist_items(
                    playlist_id,
                    limit=limit,
                    offset=offset,
                    additional_types="track",
                )
            except SpotifyException as e:
                pbar.close()
                if getattr(e, "http_status", None) == 404:
                    print("\n❌ Tracks not accessible (playlist may be private).")
                    return False
                print(f"\n❌ Spotify error while fetching tracks: {e}")
                return False

            items = response.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track")

                if not track:
                    pbar.update(1)
                    continue

                title = (track.get("name") or "").strip()
                artists = ", ".join(
                    (a.get("name") or "").strip()
                    for a in (track.get("artists") or [])
                    if (a.get("name") or "").strip()
                )

                if title and artists:
                    line = f"{artists} - {title}"
                    lines.append(line)
                    tqdm.write(line)

                processed = pbar.n + 1
                elapsed = time.time() - start_time

                if processed > 5 and elapsed > 0:
                    avg_time = elapsed / processed
                    remaining_sec = avg_time * (total_tracks - processed)
                    pbar.set_postfix_str(
                        f"Remaining ~{self.format_time(remaining_sec)}",
                        refresh=False,
                    )
                else:
                    pbar.set_postfix_str("Remaining ~--:--", refresh=False)

                pbar.update(1)

            offset += len(items)

        pbar.close()

        # ✅ Write output file
        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")

        print(f"{COLOR_SUCCESS}\n✅ Playlist exported successfully to: {output_file_path}{COLOR_RESET}")
        return True
