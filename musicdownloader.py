import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    
from src.spotify.playlist_exporter import SpotifyPlaylistExporter


def show_menu():
    print("\n=== MusicDownloader ===")
    print("1) Option 1 (placeholder)")
    print("2) Option 2 (placeholder)")
    print("3) Export Spotify Playlist")
    print("0) Exit")


def placeholder(option_number: int):
    print(f"\nOption {option_number} is not implemented yet.")


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
        playlist_url=playlist_url,
        output_file_path=output_file_path
    )

def main():
    while True:
        show_menu()
        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            placeholder(1)

        elif choice == "2":
            placeholder(2)

        elif choice == "3":
            export_playlist_flow()

        elif choice == "0":
            print("\nGoodbye!")
            break

        else:
            print("\nInvalid option. Please try again.")


if __name__ == "__main__":
    main()