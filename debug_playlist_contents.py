"""
Debug helper: call the anonymous Pathfinder GraphQL API with the
fetchPlaylistContents operation (captured from a real browser session) and
dump the raw response, so we can find the correct field paths for track
data before wiring pagination into spotify_pathfinder.py for real.

Usage:
    python debug_playlist_contents.py <spotify_playlist_url_or_id> [offset] [limit]

Example:
    python debug_playlist_contents.py 3Kv9kljcArAqh9L2pPrQtb 0 50
"""

import json
import re
import sys

from spotify_pathfinder import SpotifyPathfinder

PLAYLIST_CONTENTS_HASH = "86dde7b9d9356e2369414647cf6950cfed96e778e129cfdfc99aea6c1613b3b0"


def extract_playlist_id(url_or_id: str) -> str:
    match = re.search(r"playlist[/:]([a-zA-Z0-9]{22})", url_or_id)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9]{22}", url_or_id.strip()):
        return url_or_id.strip()
    raise ValueError(f"Could not extract a playlist ID from: {url_or_id}")


def summarize(obj, label, depth=0, max_depth=4):
    indent = "  " * depth
    if depth > max_depth:
        print(f"{indent}{label}: ... (max depth reached)")
        return
    if isinstance(obj, dict):
        print(f"{indent}{label}: dict (keys: {list(obj.keys())})")
        for k, v in obj.items():
            summarize(v, k, depth + 1, max_depth)
    elif isinstance(obj, list):
        print(f"{indent}{label}: list (len={len(obj)})")
        if obj:
            summarize(obj[0], f"{label}[0]", depth + 1, max_depth)
    else:
        preview = obj if not isinstance(obj, str) or len(obj) < 60 else obj[:60] + "..."
        print(f"{indent}{label} = {preview!r}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_playlist_contents.py <playlist_url_or_id> [offset] [limit]")
        sys.exit(1)

    playlist_id = extract_playlist_id(sys.argv[1])
    offset = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    pf = SpotifyPathfinder()
    pf.initialize()

    variables = {
        "uri": f"spotify:playlist:{playlist_id}",
        "offset": offset,
        "limit": limit,
        "includeEpisodeContentRatingsV2": True,
    }
    payload = {
        "operationName": "fetchPlaylistContents",
        "variables": variables,
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": PLAYLIST_CONTENTS_HASH}},
    }
    headers = {
        "Authorization": f"Bearer {pf.access_token}",
        "Client-Token": pf.client_token,
        "Spotify-App-Version": pf.client_version,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "App-Platform": "WebPlayer",
    }

    print(f"Requesting offset={offset} limit={limit} for playlist {playlist_id}...")
    r = pf.session.post(
        "https://api-partner.spotify.com/pathfinder/v2/query",
        json=payload,
        headers=headers,
        timeout=15,
    )
    print(f"HTTP status: {r.status_code}")
    r.raise_for_status()
    data = r.json()

    out_path = "playlist_contents_debug.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Full response written to: {out_path}")

    if "errors" in data:
        print("\n⚠️ GraphQL errors in response:")
        print(json.dumps(data["errors"], indent=2))

    print("\n--- Response structure summary ---")
    summarize(data, "root")

    print(
        "\nDone. Share playlist_contents_debug.json (or the summary above) "
        "so we can find the exact path to the track items and their fields "
        "(title, artists, album, duration, etc.) before wiring this into "
        "spotify_pathfinder.py for real."
    )


if __name__ == "__main__":
    main()
