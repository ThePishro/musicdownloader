"""Anonymous Spotify Web Player Pathfinder client.

Uses the current no-login Web Player token + client-token flow and the
internal Pathfinder search query instead of /v1/search, which rate-limits
anonymous Web Player tokens.
"""

import base64
import hashlib
import hmac
import json
import re
import struct
import time
from typing import Dict, List

import requests

TOTP_SECRET = "GM3TMMJTGYZTQNZVGM4DINJZHA4TGOBYGMZTCMRTGEYDSMJRHE4TEOBUG4YTCMRUGQ4DQOJUGQYTAMRRGA2TCMJSHE3TCMBY"
TOTP_VERSION = 61
# Current persisted searchDesktop query. Keep a fallback so a stale hash can
# be replaced without changing the rest of the client.
SEARCH_HASH = "d9f785900f0710b31c07818d617f4f7600c1e21217e80f5b043d1e78d74e6026"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"


def _totp(ts=None):
    ts = int(time.time() if ts is None else ts)
    secret = base64.b32decode(TOTP_SECRET + "=" * ((8 - len(TOTP_SECRET) % 8) % 8))
    digest = hmac.new(secret, struct.pack(">Q", ts // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


class SpotifyPathfinder:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        self.access_token = ""
        self.client_token = ""
        self.client_id = ""
        self.device_id = ""
        self.client_version = ""

    def initialize(self):
        page = self.session.get("https://open.spotify.com", timeout=15)
        page.raise_for_status()

        match = re.search(r'<script id="appServerConfig" type="text/plain">([^<]+)</script>', page.text)
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
                r = self.session.get("https://open.spotify.com/api/token", params=params, timeout=15)
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
            raise last_error or RuntimeError("Could not obtain anonymous Spotify token")

        if not self.client_version:
            raise RuntimeError("Spotify Web Player client version was not found")
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
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        self.client_token = data.get("granted_token", {}).get("token", "")
        if not self.client_token:
            raise RuntimeError("Spotify did not grant a client token")

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        if not self.access_token or not self.client_token:
            self.initialize()

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
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Token": self.client_token,
            "Spotify-App-Version": self.client_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "App-Platform": "WebPlayer",
        }

        r = self.session.post(
            "https://api-partner.spotify.com/pathfinder/v2/query",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if r.status_code in (401, 403):
            self.access_token = self.client_token = ""
            self.initialize()
            headers["Authorization"] = f"Bearer {self.access_token}"
            headers["Client-Token"] = self.client_token
            r = self.session.post(
                "https://api-partner.spotify.com/pathfinder/v2/query",
                json=payload,
                headers=headers,
                timeout=15,
            )
        r.raise_for_status()
        data = r.json().get("data", {}).get("searchV2", {})
        items = data.get("tracksV2", {}).get("items", [])

        results = []
        for idx, entry in enumerate(items[:limit], 1):
            item = entry.get("item", {}).get("data", {})
            if not item:
                continue
            artists = item.get("artists", {}).get("items", [])
            artist_names = [a.get("profile", {}).get("name", "") for a in artists]
            cover_sources = item.get("albumOfTrack", {}).get("coverArt", {}).get("sources", [])
            cover_url = cover_sources[-1].get("url", "") if cover_sources else ""
            duration_ms = item.get("duration", {}).get("totalMilliseconds", 0) or 0
            total_seconds = int(duration_ms / 1000)
            duration = f"{total_seconds // 60}:{total_seconds % 60:02d}"
            track_id = item.get("id", "") or item.get("uri", "").split(":")[-1]
            artist = ", ".join(x for x in artist_names if x) or "Unknown Artist"
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
