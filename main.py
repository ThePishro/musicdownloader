import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.cli_flows import export_playlist_flow, search_and_download_flow


def main():
    while True:
        print("\n=== MusicDownloader ===")
        print("1) Search & Download Tracks (Spotify Metadata)")
        print("2) Option 2 (placeholder)")
        print("3) Export Spotify Playlist")
        print("0) Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            search_and_download_flow()
        elif choice == "2":
            print("\nOption 2 is not implemented yet.")
        elif choice == "3":
            export_playlist_flow()
        elif choice == "0":
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid option. Please try again.")


if __name__ == "__main__":
    main()