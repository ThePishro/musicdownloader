import os
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
    playlist_url = input("\nEnter Spotify playlist URL: ").strip()
    file_name = input("Enter output file name (without .txt): ").strip()

    if not file_name:
        print("Invalid file name.")
        return

    output_path = os.path.join("output", f"{file_name}.txt")

    exporter = SpotifyPlaylistExporter()
    exporter.export_playlist(
        playlist_url=playlist_url,
        output_path=output_path
    )

    print("\nExport completed successfully.")
    print(f"File saved at: {os.path.abspath(output_path)}")


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
