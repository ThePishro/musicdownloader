import os
import time
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth


class SpotifyPlaylistExporter:
    def __init__(self):
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                scope="playlist-read-private playlist-read-collaborative",
                cache_path=".spotify_cache"
            )
        )

    def export_playlist(
        self,
        playlist_url: str,
        output_path: str,
        limit: int = 100,
        sleep_time: float = 0.2
    ):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        offset = 0
        total_tracks: Optional[int] = None
        exported = 0

        with open(output_path, "w", encoding="utf-8") as file:
            while True:
                results = self.sp.playlist_items(
                    playlist_url,
                    limit=limit,
                    offset=offset
                )

                if total_tracks is None:
                    total_tracks = results["total"]
                    print(f"\nTotal tracks: {total_tracks}")

                items = results["items"]
                if not items:
                    break

                for item in items:
                    track = item.get("track")
                    if not track:
                        continue

                    artists = ", ".join(
                        artist["name"] for artist in track["artists"]
                    )
                    title = track["name"]

                    file.write(f"{artists} - {title}\n")
                    exported += 1

                offset += limit
                print(f"Exported {exported}/{total_tracks}", end="\r")
                time.sleep(sleep_time)

        print("\nPlaylist exported successfully.")
