from core.search.youtube_music import YouTubeMusicSearch


def main():
    searcher = YouTubeMusicSearch()
    results = searcher.search("Daft Punk One More Time", limit=5)

    print("\nResults:\n" + "-" * 40)
    for i, track in enumerate(results, start=1):
        print(f"{i}. {track.title} - {track.artist}")
        print(f"   Album: {track.album}")
        print(f"   Duration: {track.duration_sec}s")
        print(f"   URL: {track.url}")
        print()

if __name__ == "__main__":
    main()