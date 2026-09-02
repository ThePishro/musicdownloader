from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from typing import Dict, List
from mutagen.id3 import ID3, APIC, TALB, TPE1, TPE2, TIT2, TRCK, TPOS, TDRC, TCON
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
from browser_detect import detect_default_browser, FALLBACK_BROWSER_PRIORITY
from utils import sanitize_filename
import yt_dlp

console = Console()


class NoSearchResultsError(Exception):
    """Raised when no candidate search query finds any YouTube results at
    all. Distinct from DownloadFailureError so the retry loop can skip
    wasting backoff time on something retrying can't fix.
    """
    pass


class DownloadFailureError(Exception):
    """Raised when a YouTube match WAS found, but every attempt to
    actually download it failed (e.g. "Requested format is not
    available", extractor errors, etc). Distinct from
    NoSearchResultsError — the search succeeded, the download didn't —
    so the error message doesn't lie about what actually happened.
    """
    pass


class MusicDownloader:

    def __init__(
        self,
        output_dir: str = "downloads",
        max_workers: int = 3,
        max_retries: int = 3,
        cookies_from_browser: str = "auto",
    ):
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.max_retries = max_retries

        # "auto" (default) detects the OS-level default browser and pulls its
        # real YouTube session cookies, so different users on different
        # machines/browsers each get a sensible default without hardcoding one
        # person's browser. Pass an explicit name ("chrome", "firefox", "edge",
        # "brave", "opera", "vivaldi", "safari") to override, or None/"" to
        # disable cookies entirely.
        if cookies_from_browser == "auto":
            detected = detect_default_browser()
            if detected:
                print(
                    f"🍪 Using cookies from detected default browser: {detected}")
                self.cookies_from_browser = detected
            else:
                # Detection failed (unsupported OS, tool missing, unrecognized
                # browser, etc) — fall back to the most commonly installed option
                # rather than silently disabling cookies and re-hitting the bot
                # check. Still just a best guess; explicit override always wins.
                fallback = FALLBACK_BROWSER_PRIORITY[0]
                print(
                    "🍪 Could not auto-detect your default browser — falling back"
                    f" to '{fallback}'. If downloads still fail with a"
                    " sign-in/bot-check error, pass cookies_from_browser="
                    "\"firefox\" (or whichever browser you actually use and are"
                    " signed into YouTube on) when creating MusicDownloader."
                )
                self.cookies_from_browser = fallback
        else:
            self.cookies_from_browser = cookies_from_browser or None

        os.makedirs(self.output_dir, exist_ok=True)
        self.scraper = SpotifyScraper()

    def _build_final_path(self, metadata: Dict) -> str:
        """Build the final 'Artist - Title.mp3' path, avoiding collisions."""
        artist = sanitize_filename(metadata.get("artist", "Unknown Artist"))
        title = sanitize_filename(metadata.get("title", "Unknown Title"))
        base_name = f"{artist} - {title}"
        candidate = os.path.join(self.output_dir, f"{base_name}.mp3")
        counter = 2
        while os.path.exists(candidate):
            candidate = os.path.join(
                self.output_dir, f"{base_name} ({counter}).mp3")
            counter += 1
        return candidate

    def _candidate_search_queries(self, metadata: Dict) -> List[str]:
        """Build an ordered list of queries to try on YouTube. The primary
        search_query (usually "Artist - Title Audio") is tried first; if that
        finds nothing, a plainer "Artist - Title" (no suffix) is tried as a
        fallback, since the "Audio" suffix can over-narrow results for less
        common tracks.
        """
        queries = []
        primary = metadata.get("search_query")
        if primary:
            queries.append(primary)

        artist = (metadata.get("artist") or "").strip()
        title = (metadata.get("title") or "").strip()
        if artist and title:
            simple = f"{artist} - {title}"
            if simple not in queries:
                queries.append(simple)

        return queries

    # Tried in order against a resolved video before giving up on it.
    # 'ba/ba*' alone was failing with "Requested format is not available"
    # on some videos — broader fallbacks (combined video+audio, then
    # anything at all) cover cases where audio-only streams aren't offered
    # for a given client/video combination.
    FORMAT_FALLBACKS = ['ba/ba*', 'bestaudio/best', 'best']

    def _build_search_opts(self) -> dict:
        """Search-only config — deliberately has NO 'format' key. Using
        extract_flat means yt-dlp returns lightweight search-result metadata
        (id/title/url) without resolving any formats at all, so a video with
        no matching format for our download-time selector still counts as
        "found" here — format resolution only happens in phase 2, against a
        single already-identified video, where a real failure means something.
        """
        opts = {
            'default_search': 'ytsearch1',
            'extract_flat': 'in_playlist',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {'youtube': {'player_client': ['web', 'android']}},
        }
        if self.cookies_from_browser:
            opts['cookiesfrombrowser'] = (
                self.cookies_from_browser, None, None, None)
        return opts

    def _build_ydl_opts(self, format_selector: str) -> dict:
        out_tmpl = os.path.join(self.output_dir, "%(id)s.%(ext)s")
        opts = {
            'format': format_selector,
            'outtmpl': out_tmpl,
            'concurrent_fragment_downloads': 8,
            # DASH/HLS fragments must stay on yt-dlp's native downloader —
            # handing them to aria2c was dropping/corrupting the initial
            # segment (missing first few seconds of audio). aria2c only
            # handles plain HTTP downloads.
            'external_downloader': {'dash': 'native', 'm3u8': 'native', 'http': 'aria2c'},
            'external_downloader_args': {'aria2c': ['-j', '8', '-x', '8', '-s', '8', '-k', '1M']},
            # 'web' first: YouTube's SABR rollout has been breaking adaptive
            # (audio-only) formats specifically on the 'android' client for
            # many videos — 'web' is currently the more reliable source of
            # usable formats, with 'android' kept as a secondary attempt.
            'extractor_args': {'youtube': {'player_client': ['web', 'android']}},
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        if self.cookies_from_browser:
            opts['cookiesfrombrowser'] = (
                self.cookies_from_browser, None, None, None)
        return opts

    def download_audio_from_youtube(self, metadata: Dict) -> str:
        """Searches YouTube/YouTube Music using client emulation to bypass rate limits."""
        candidates = self._candidate_search_queries(metadata)
        last_error = None
        found_any_match = False

        for query in candidates:
            # Phase 1: search only, no download yet — lets us tell "this query
            # found nothing" apart from "found something, download failed".
            search_opts = self._build_ydl_opts(self.FORMAT_FALLBACKS[0])
            search_opts['default_search'] = 'ytsearch1'

            try:
                with yt_dlp.YoutubeDL(search_opts) as ydl:
                    search_info = ydl.extract_info(query, download=False)
            except Exception as e:
                last_error = e
                continue

            if search_info and "entries" in search_info:
                entries = search_info.get("entries") or []
            elif search_info:
                entries = [search_info]
            else:
                entries = []

            if not entries:
                # Genuinely no results for this query — try the next candidate.
                continue

            found_any_match = True
            video_info = entries[0]
            video_url = video_info.get("webpage_url") or video_info.get("id")

            # Phase 2: we have a real video — try downloading it with each
            # format fallback before giving up on this particular video.
            for format_selector in self.FORMAT_FALLBACKS:
                try:
                    dl_opts = self._build_ydl_opts(format_selector)
                    with yt_dlp.YoutubeDL(dl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=True)
                    filename = ydl.prepare_filename(info)
                    temp_mp3_path = os.path.splitext(filename)[0] + ".mp3"
                    final_path = self._build_final_path(metadata)
                    os.replace(temp_mp3_path, final_path)
                    return final_path
                except Exception as e:
                    last_error = e
                    continue
            # Every format fallback failed for this video — move on to the
            # next candidate query, which may resolve to a different video.

        if found_any_match:
            raise DownloadFailureError(
                f"Found a YouTube match for"
                f" '{metadata.get('artist', '?')} - {metadata.get('title', '?')}'"
                f" but every download attempt failed. Last error: {last_error}"
            ) from last_error

        raise NoSearchResultsError(
            f"No YouTube results found for"
            f" '{metadata.get('artist', '?')} - {metadata.get('title', '?')}'"
            f" (tried: {candidates})"
        ) from last_error

    def embed_id3_tags(self, file_path: str, metadata: Dict):
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass

        audio.tags.add(TIT2(encoding=3, text=metadata["title"]))
        audio.tags.add(TPE1(encoding=3, text=metadata["artist"]))
        audio.tags.add(
            TALB(encoding=3, text=metadata.get("album", "Unknown Album")))

        if metadata.get("album_artist"):
            audio.tags.add(TPE2(encoding=3, text=metadata["album_artist"]))
        if metadata.get("track_number"):
            track_tag = str(metadata["track_number"])
            if metadata.get("total_tracks"):
                track_tag += f"/{metadata['total_tracks']}"
            audio.tags.add(TRCK(encoding=3, text=track_tag))
        if metadata.get("disc_number"):
            audio.tags.add(TPOS(encoding=3, text=str(metadata["disc_number"])))
        if metadata.get("year"):
            audio.tags.add(TDRC(encoding=3, text=str(metadata["year"])))
        if metadata.get("genre"):
            audio.tags.add(TCON(encoding=3, text=metadata["genre"]))

        if metadata.get("cover_url"):
            try:
                # Fast async/cffi fetch for album art
                img_resp = requests.get(
                    metadata["cover_url"], impersonate="chrome120", timeout=5
                )
                mime = img_resp.headers.get(
                    "content-type", "image/jpeg").split(";")[0].strip()
                audio.tags.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc='Cover',
                    data=img_resp.content
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
            except NoSearchResultsError:
                # No YouTube match exists for any candidate query — retrying the
                # exact same search won't produce a different result, so fail
                # immediately instead of wasting exponential backoff time.
                raise
            except DownloadFailureError as e:
                # A match WAS found but the download itself failed — this can be
                # transient (CDN hiccup, temporary format issue), so let it go
                # through the normal retry/backoff path below.
                last_exception = e
                if attempt < self.max_retries:
                    sleep_time = 2**attempt
                    time.sleep(sleep_time)
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
