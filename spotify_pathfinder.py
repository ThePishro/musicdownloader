"""Anonymous Spotify Web Player Pathfinder client.

Uses the current no-login Web Player token + client-token flow and the
internal Pathfinder search / playlist-contents queries instead of the
official Web API, which either rate-limits anonymous tokens (search) or
outright refuses Spotify-owned editorial playlists (playlist endpoints).
"""

import base64
import hashlib
import hmac
import json
import re
import struct
import time
from typing import Dict, List, Tuple

import requests

TOTP_SECRET = "GM3TMMJTGYZTQNZVGM4DINJZHA4TGOBYGMZTCMRTGEYDSMJRHE4TEOBUG4YTCMRUGQ4DQOJUGQYTAMRRGA2TCMJSHE3TCMBY"
TOTP_VERSION = 61
# Current persisted searchDesktop query. Keep a fallback so a stale hash can
# be replaced without changing the rest of the client.
SEARCH_HASH = "d9f785900f0710b31c07818d617f4f7600c1e21217e80f5b043d1e78d74e6026"
# Persisted fetchPlaylistContents query — captured from a live browser
# session (Network tab), since it's not documented anywhere. If Spotify
# rotates this hash, requests will start failing with a "PersistedQueryNotFound"
# style GraphQL error and it'll need to be re-captured the same way.
PLAYLIST_CONTENTS_HASH = "86dde7b9d9356e2369414647cf6950cfed96e778e129cfdfc99aea6c1613b3b0"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"


def _totp(ts=None):
    ts = int(time.time() if ts is None else ts)
    secret = base64.b32decode(
        TOTP_SECRET + "=" * ((8 - len(TOTP_SECRET) % 8) % 8))
    digest = hmac.new(secret, struct.pack(
        ">Q", ts // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


class SpotifyPathfinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        self.access_token = ""
        self.client_token = ""
        self.client_id = ""
        self.device_id = ""
        self.client_version = ""

    def initialize(self):
        page = self.session.get("https://open.spotify.com", timeout=15)
        page.raise_for_status()

        match = re.search(
            r'<script id="appServerConfig" type="text/plain">([^<]+)</script>', page.text)
        if match:
            try:
                cfg = json.loads(base64.b64decode(match.group(1)))
                self.client_version = cfg.get("clientVersion", "")
            except Exception:
                pass

        for cookie in self.session.cookies:
            if cookie.name == "sp_t":
                self.device_id = cookie.value

        last_error = None
        for offset in (0, -30, 30):
            try:
                code = _totp(time.time() + offset)
                params = {
                    "reason": "init",
                    "productType": "web-player",
                    "totp": code,
                    "totpVer": str(TOTP_VERSION),
                    "totpServer": code,
                }
                r = self.session.get(
                    "https://open.spotify.com/api/token", params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                self.access_token = data["accessToken"]
                self.client_id = data["clientId"]
                for cookie in r.cookies:
                    if cookie.name == "sp_t":
                        self.device_id = cookie.value
                break
            except Exception as exc:
                last_error = exc
        else:
            raise last_error or RuntimeError(
                "Could not obtain anonymous Spotify token")

        if not self.client_version:
            raise RuntimeError(
                "Spotify Web Player client version was not found")
        if not self.device_id:
            raise RuntimeError("Spotify Web Player device ID was not found")

        payload = {
            "client_data": {
                "client_version": self.client_version,
                "client_id": self.client_id,
                "js_sdk_data": {
                    "device_brand": "unknown",
                    "device_model": "unknown",
                    "os": "windows",
                    "os_version": "NT 10.0",
                    "device_id": self.device_id,
                    "device_type": "computer",
                },
            }
        }
        r = self.session.post(
            "https://clienttoken.spotify.com/v1/clienttoken",
            json=payload,
            headers={"Content-Type": "application/json",
                     "Accept": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self.client_token = data.get("granted_token", {}).get("token", "")
        if not self.client_token:
            raise RuntimeError("Spotify did not grant a client token")

    def _graphql_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Token": self.client_token,
            "Spotify-App-Version": self.client_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "App-Platform": "WebPlayer",
        }

    def _graphql_post(self, payload: dict) -> dict:
        """POST a Pathfinder GraphQL query, refreshing auth once on 401/403."""
        if not self.access_token or not self.client_token:
            self.initialize()

        headers = self._graphql_headers()
        r = self.session.post(
            "https://api-partner.spotify.com/pathfinder/v2/query",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if r.status_code in (401, 403):
            self.access_token = self.client_token = ""
            self.initialize()
            r = self.session.post(
                "https://api-partner.spotify.com/pathfinder/v2/query",
                json=payload,
                headers=self._graphql_headers(),
                timeout=15,
            )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"):
            raise RuntimeError(f"Pathfinder GraphQL error: {data['errors']}")
        return data

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        variables = {
            "searchTerm": query,
            "offset": 0,
            "limit": limit,
            "numberOfTopResults": min(5, limit),
            "includeAudiobooks": False,
        }
        payload = {
            "operationName": "searchDesktop",
            "variables": variables,
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": SEARCH_HASH}},
        }

        data = self._graphql_post(payload)
        result = data.get("data", {}).get("searchV2", {})
        items = result.get("tracksV2", {}).get("items", [])

        results = []
        for idx, entry in enumerate(items[:limit], 1):
            item = entry.get("item", {}).get("data", {})
            if not item:
                continue
            artists = item.get("artists", {}).get("items", [])
            artist_names = [a.get("profile", {}).get("name", "")
                            for a in artists]
            cover_sources = item.get("albumOfTrack", {}).get(
                "coverArt", {}).get("sources", [])
            cover_url = cover_sources[-1].get("url",
                                              "") if cover_sources else ""
            duration_ms = item.get("duration", {}).get(
                "totalMilliseconds", 0) or 0
            total_seconds = int(duration_ms / 1000)
            duration = f"{total_seconds // 60}:{total_seconds % 60:02d}"
            track_id = item.get("id", "") or item.get("uri", "").split(":")[-1]
            artist = ", ".join(
                x for x in artist_names if x) or "Unknown Artist"
            title = item.get("name", "Unknown Title")
            album = item.get("albumOfTrack", {}).get("name", "Unknown Album")
            results.append({
                "index": idx,
                "title": title,
                "artist": artist,
                "album": album,
                "duration": duration,
                "cover_url": cover_url,
                "search_query": f"{artist} - {title} Audio",
                "spotify_id": track_id,
            })
        return results

    def _parse_playlist_item(self, item: dict) -> Dict:
        """Map one fetchPlaylistContents item into our standard track dict.

        Confirmed field paths (from a real captured response):
          itemV2.data.{name, uri, discNumber, trackNumber,
                       trackDuration.totalMilliseconds,
                       artists.items[].profile.name,
                       albumOfTrack.{name, date.isoString, coverArt.sources[],
                                     artists.items[].profile.name}}
        """
        data = item.get("itemV2", {}).get("data", {})

        title = data.get("name", "Unknown Title")

        artists = data.get("artists", {}).get("items", [])
        artist = (
            ", ".join(a["profile"]["name"]
                      for a in artists if a.get("profile", {}).get("name"))
            or "Unknown Artist"
        )

        album_data = data.get("albumOfTrack", {}) or {}
        album = album_data.get("name", "Unknown Album")

        album_artists = album_data.get("artists", {}).get("items", [])
        album_artist = (
            ", ".join(a["profile"]["name"]
                      for a in album_artists if a.get("profile", {}).get("name"))
            or None
        )

        year = None
        release_date = album_data.get("date", {})
        if release_date.get("isoString"):
            year = release_date["isoString"][:4]

        cover_sources = album_data.get("coverArt", {}).get("sources", [])
        cover_url = ""
        if cover_sources:
            largest = max(cover_sources, key=lambda img: img.get("width") or 0)
            cover_url = largest.get("url", "")

        uri = data.get("uri", "")
        track_id = uri.split(":")[-1] if uri else ""

        return {
            "id": track_id,
            "type": "track",
            "title": title,
            "artist": artist,
            "album": album,
            "album_artist": album_artist,
            "track_number": data.get("trackNumber"),
            "disc_number": data.get("discNumber"),
            "year": year,
            "cover_url": cover_url,
            "search_query": f"{artist} - {title} Audio",
        }

    def get_playlist_tracks(
        self, playlist_id: str, batch_size: int = 100, request_delay: float = 0.25
    ) -> Tuple[List[Dict], int]:
        """Fetch every track in a playlist via fetchPlaylistContents,
        paginating with offset/limit until totalCount is reached.

        Returns (tracks, total_count). total_count comes straight from the
        API's own reported totalCount for the playlist, useful for a
        progress bar or sanity-checking the final list length.
        """
        playlist_uri = f"spotify:playlist:{playlist_id}"
        all_tracks: List[Dict] = []
        offset = 0
        total_count = None

        while True:
            variables = {
                "uri": playlist_uri,
                "offset": offset,
                "limit": batch_size,
                "includeEpisodeContentRatingsV2": True,
            }
            payload = {
                "operationName": "fetchPlaylistContents",
                "variables": variables,
                "extensions": {
                    "persistedQuery": {"version": 1, "sha256Hash": PLAYLIST_CONTENTS_HASH}
                },
            }

            data = self._graphql_post(payload)
            content = data.get("data", {}).get(
                "playlistV2", {}).get("content", {})
            items = content.get("items", [])

            if total_count is None:
                total_count = content.get("totalCount", 0)

            if not items:
                break

            for item in items:
                try:
                    all_tracks.append(self._parse_playlist_item(item))
                except Exception:
                    # Skip malformed/unavailable items (e.g. local files,
                    # removed tracks) rather than aborting the whole export.
                    continue

            offset += len(items)

            if total_count and offset >= total_count:
                break
            if len(items) < batch_size:
                # Fewer items than requested came back — treat as end of list
                # even if totalCount disagrees, to avoid looping forever.
                break

            if request_delay > 0:
                time.sleep(request_delay)

        return all_tracks, (total_count or len(all_tracks))
