from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import Dict, List
import urllib.parse
from mutagen.id3 import ID3, APIC, TALB, TPE1, TIT2
from mutagen.mp3 import MP3
from curl_cffi import requests
import yt_dlp


class YouTubeMusicSearcher:

  def __init__(self, output_dir: str = "downloads", max_workers: int = 4):
    self.output_dir = output_dir
    self.max_workers = max_workers
    os.makedirs(self.output_dir, exist_ok=True)

  def search_youtube_music(
      self, query: str, max_results: int = 10
  ) -> List[Dict]:
    """Searches Spotify's web frontend (via curl_cffi) to fetch track metadata without API keys."""
    print(f"\n🔎 Searching Spotify for: '{query}'...")
    results = []

    try:
      # Search Spotify's internal web API endpoint
      encoded_query = urllib.parse.quote(query)
      url = f"https://api.spotify.com/v1/search?q={encoded_query}&type=track&limit={max_results}"

      # Perform request using browser impersonation
      response = requests.get(
          f"https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
          impersonate="chrome120",
          timeout=10,
      )

      token_data = response.json()
      access_token = token_data.get("accessToken")

      if not access_token:
        print("⚠️ Could not fetch public guest token from Spotify.")
        return []

      headers = {"Authorization": f"Bearer {access_token}"}
      search_res = requests.get(
          url, headers=headers, impersonate="chrome120", timeout=10
      )
      data = search_res.json()

      tracks = data.get("tracks", {}).get("items", [])

      for idx, item in enumerate(tracks, start=1):
        title = item.get("name", "Unknown Title")
        artists = ", ".join([a["name"] for a in item.get("artists", [])])
        album = item.get("album", {}).get("name", "")
        duration_ms = item.get("duration_ms", 0)

        mins, secs = divmod(int(duration_ms / 1000), 60)
        duration_str = f"{mins}:{secs:02d}"

        # Grab cover art thumbnail
        images = item.get("album", {}).get("images", [])
        cover_url = images[0]["url"] if images else None

        results.append({
            "index": idx,
            "title": title,
            "artist": artists,
            "album": album,
            "duration": duration_str,
            "cover_url": cover_url,
            # Search query string formatted for MusicDownloader / yt-dlp
            "search_query": f"{artists} - {title}",
        })

    except Exception as e:
      print(f"⚠️ Spotify search failed: {e}")
      return []

    return results

  search_youtube = search_youtube_music