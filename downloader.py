from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from typing import Dict, List
from mutagen.id3 import ID3, APIC, TALB, TPE1, TIT2
from mutagen.mp3 import MP3
from curl_cffi import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from spotify_scraper import SpotifyScraper
import yt_dlp

console = Console()


class MusicDownloader:

  def __init__(
      self,
      output_dir: str = "downloads",
      max_workers: int = 3,
      max_retries: int = 3,
  ):
    self.output_dir = output_dir
    self.max_workers = max_workers
    self.max_retries = max_retries
    os.makedirs(self.output_dir, exist_ok=True)
    self.scraper = SpotifyScraper()

  def download_audio_from_youtube(self, metadata: Dict) -> str:
    """Searches YouTube/YouTube Music using client emulation to bypass rate limits."""
    out_tmpl = os.path.join(self.output_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        'format': 'ba/ba*',  # Grab best audio directly without fetching redundant stream formats
        'default_search': 'ytsearch1',
        'outtmpl': out_tmpl,
        # Speed Optimization 1: Use 8 concurrent threads for audio fragments
        'concurrent_fragment_downloads': 8,
        # Speed Optimization 2: Use aria2c for raw HTTP downloading if installed
        'external_downloader': 'aria2c',
        'external_downloader_args': ['-j', '8', '-x', '8', '-s', '8', '-k', '1M'],
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']}
        },
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(metadata["search_query"], download=True)
      if "entries" in info:
        info = info["entries"][0]
      filename = ydl.prepare_filename(info)
      return os.path.splitext(filename)[0] + ".mp3"

  def embed_id3_tags(self, file_path: str, metadata: Dict):
    audio = MP3(file_path, ID3=ID3)
    try:
        audio.add_tags()
    except Exception:
        pass

    audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
    audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
    audio.tags.add(TALB(encoding=3, text=metadata["album"]))

    if metadata.get("cover_url"):
        try:
            # Fast async/cffi fetch for album art
            img_data = requests.get(metadata["cover_url"], impersonate="chrome120", timeout=5).content
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=img_data
            ))
        except Exception:
            pass

    audio.save()

  def _download_worker_with_retry(
      self, track_meta: Dict, delay: float = 0.5
  ) -> str:
    """Worker task executing download and tagging with retry logic and backoff."""
    # Stagger thread start to avoid sudden network traffic bursts
    if delay > 0:
      time.sleep(delay)

    last_exception = None
    for attempt in range(1, self.max_retries + 1):
      try:
        filepath = self.download_audio_from_youtube(track_meta)
        self.embed_id3_tags(filepath, track_meta)
        return filepath
      except Exception as e:
        last_exception = e
        if attempt < self.max_retries:
          # Exponential backoff pause: 2s, 4s, 8s...
          sleep_time = 2**attempt
          time.sleep(sleep_time)

    raise last_exception

  def process_url(self, spotify_url: str):
    """Parses Spotify URL and downloads tracks concurrently with progress and retries."""
    tracks = self.scraper.parse_url(spotify_url)
    total_tracks = len(tracks)

    if total_tracks == 0:
      console.print("[red]✘ No tracks found for this URL.[/red]")
      return

    console.print(
        f"[bold green]✓ Found {total_tracks} track(s).[/bold green] Starting"
        f" download using {self.max_workers} workers...\n"
    )

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    )

    with progress:
      main_task = progress.add_task(
          "[cyan]Downloading tracks...", total=total_tracks
      )

      with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        # Submit workers with staggered initial delays (0.0s, 0.5s, 1.0s...)
        future_to_track = {
            executor.submit(
                self._download_worker_with_retry, track, idx * 0.5
            ): track
            for idx, track in enumerate(tracks)
        }

        for future in as_completed(future_to_track):
          track_info = future_to_track[future]
          try:
            future.result()
            progress.console.print(
                f"[green]✔[/green] Finished: [bold]{track_info['artist']}[/bold]"
                f" - {track_info['title']}"
            )
          except Exception as e:
            progress.console.print(
                f"[red]✘[/red] Failed after {self.max_retries} attempts:"
                f" {track_info['artist']} - {track_info['title']} | Error: {e}"
            )

          progress.advance(main_task)


if __name__ == "__main__":
  downloader = MusicDownloader(
      output_dir="downloads", max_workers=6, max_retries=4
  )
  downloader.process_url(
      "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
  )