import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyPlaylistExporter:
    def __init__(self):
        """
        Initialize Spotify client using credentials from .env file
        """

        # Load environment variables from .env
        load_dotenv()

        client_id = os.getenv("SPOTIPY_CLIENT_ID")
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")

        if not client_id or not client_secret:
            raise RuntimeError(
                "Spotify credentials not found. "
                "Please set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in .env file."
            )

        self.spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
        )

    def export_playlist(self, playlist_url: str, output_file_path: str):
        """
        Export all tracks from a Spotify playlist into a text file.
        Format: Artist - Track Title
        """

        limit = 100
        offset = 0

        with open(output_file_path, "w", encoding="utf-8") as file:
            while True:
                response = self.spotify.playlist_items(
                    playlist_url,
                    limit=limit,
                    offset=offset
                )

                items = response.get("items", [])
                if not items:
                    break

                for item in items:
                    track = item.get("track")
                    if not track:
                        continue

                    artists = ", ".join(
                        artist["name"] for artist in track.get("artists", [])
                    )
                    track_name = track.get("name")

                    file.write(f"{artists} - {track_name}\n")

                offset += limit
