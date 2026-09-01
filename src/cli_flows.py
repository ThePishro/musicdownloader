import os
from downloader import MusicDownloader
from src.spotify.playlist_exporter import SpotifyPlaylistExporter
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
        print(f"\n🚀 Starting download for {len(queue)} queued track(s)...")
        for track in queue:
          try:
            downloader._download_worker_with_retry(track, delay=0.2)
            print(f"✔ Downloaded: {track['artist']} - {track['title']}")
          except Exception as e:
            print(f"✘ Failed: {track['artist']} - {track['title']} | Error: {e}")
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
          print(f"\n🚀 Starting download for {len(queue)} queued track(s)...")
          for track in queue:
            try:
              downloader._download_worker_with_retry(track, delay=0.2)
              print(f"✔ Downloaded: {track['artist']} - {track['title']}")
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


def export_playlist_flow():
  playlist_url = input("Enter Spotify playlist URL: ").strip()
  file_name = input("Enter output file name: ").strip()

  if not file_name:
    print("❌ File name cannot be empty.")
    return

  output_dir = "playlists"
  os.makedirs(output_dir, exist_ok=True)
  output_file_path = os.path.join(output_dir, f"{file_name}.txt")

  exporter = SpotifyPlaylistExporter()
  exporter.export_playlist(
      playlist_url=playlist_url, output_file_path=output_file_path
  )