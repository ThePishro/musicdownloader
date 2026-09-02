from downloader import MusicDownloader
from playlist_exporter import SpotifyPlaylistExporter
from spotify_scraper import SpotifyScraper


def search_and_download_flow():
    scraper = SpotifyScraper()
    downloader = MusicDownloader(
        output_dir="downloads", max_workers=3, max_retries=3
    )
    queue = []

    print("\n--- Track Search & Queue (Spotify Metadata) ---")
    print(
        "Type a song/artist name to search. Type 'done' when you are ready to"
        " download."
    )

    while True:
        query = input(
            "\nEnter music/artist name (or 'done' to start download): "
        ).strip()

        if not query:
            continue

        if query.lower() == "done":
            if not queue:
                print("⚠️ No tracks added to queue.")
                confirm = input("Exit to main menu? (y/n): ").strip().lower()
                if confirm == "y":
                    break
                continue
            else:
                print(
                    f"\n🚀 Starting download for {len(queue)} queued track(s)...")
                for track in queue:
                    try:
                        downloader._download_worker_with_retry(
                            track, delay=0.2)
                        print(
                            f"✔ Downloaded: {track['artist']} - {track['title']}")
                    except Exception as e:
                        print(
                            f"✘ Failed: {track['artist']} - {track['title']} | Error: {e}")
                break

        results = scraper.search_tracks(query, max_results=10)

        if not results:
            print("❌ No results found. Try another search query.")
            continue

        print(f"\nResults for '{query}':")
        print("-" * 65)
        for res in results:
            print(
                f"{res['index']:2d}) {res['title'][:35]:<35} [{res['duration']}] -"
                f" {res['artist']}"
            )
        print("-" * 65)

        while True:
            choice = (
                input(
                    "\nSelect number to queue (1-10), 's' to search another song, or"
                    " 'done' to download: "
                )
                .strip()
                .lower()
            )

            if choice == "done":
                if queue:
                    print(
                        f"\n🚀 Starting download for {len(queue)} queued track(s)...")
                    for track in queue:
                        try:
                            downloader._download_worker_with_retry(
                                track, delay=0.2)
                            print(
                                f"✔ Downloaded: {track['artist']} - {track['title']}")
                        except Exception as e:
                            print(
                                f"✘ Failed: {track['artist']} - {track['title']} | Error: {e}"
                            )
                return

            if choice == "s":
                break

            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(results):
                    selected_track = results[idx - 1]
                    queue.append(selected_track)
                    print(
                        f"✅ Added to queue: {selected_track['artist']} -"
                        f" {selected_track['title']} ({len(queue)} track(s) queued)"
                    )
                    break
                else:
                    print(f"❌ Invalid choice. Enter 1-{len(results)}.")
            else:
                print("❌ Invalid input.")


def download_from_url_flow():
    """Download directly from a pasted Spotify track or playlist URL.

    Unlike search_and_download_flow (which only ever searches by text),
    this parses the URL via SpotifyScraper.parse_url — get_track_metadata
    for a single track (with album backfilled through Pathfinder search)
    or get_playlist_tracks for a playlist — then downloads everything
    through MusicDownloader.process_url with the usual progress bar,
    concurrency, and retry logic.
    """
    spotify_url = input(
        "\nEnter a Spotify track or playlist URL: "
    ).strip()

    if not spotify_url:
        print("❌ URL cannot be empty.")
        return

    downloader = MusicDownloader(
        output_dir="downloads", max_workers=3, max_retries=3
    )

    try:
        downloader.process_url(spotify_url)
    except ValueError as e:
        # Raised by SpotifyScraper.extract_id for anything that isn't a
        # recognizable /track/ or /playlist/ URL.
        print(f"❌ {e}")
    except Exception as e:
        print(f"❌ Unexpected error while processing URL: {e}")


def export_playlist_flow():
    """Export a playlist to exported_playlists/<Playlist Name>/, producing
    both playlist.json (full metadata, for a future re-download flow) and
    playlist.txt (Artist - Song lines).
    """
    playlist_url = input("Enter Spotify playlist URL: ").strip()

    if not playlist_url:
        print("❌ URL cannot be empty.")
        return

    exporter = SpotifyPlaylistExporter()
    exporter.export_playlist(playlist_url=playlist_url)
