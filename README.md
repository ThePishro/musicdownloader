# 🎵 MusicDownloader

A Python CLI for downloading music using **Spotify metadata** and **YouTube audio**, with support for individual tracks, playlists, metadata tagging, album artwork, and offline playlist exports.

> Search Spotify. Pick your tracks. Download them with their Spotify metadata.

---

## ✨ Features

### 🔎 Spotify-powered search

Search for tracks directly from the terminal using Spotify's Web Player data.

Search results include:

* Track title
* Artist
* Album
* Duration
* Album artwork
* Spotify track ID

No Spotify account or API credentials are required for the search flow.

### 🎧 Search & Download

Search for a song or artist, select the track you want, add it to a download queue, and download everything when you're ready.

```text
=== MusicDownloader ===
1) Search & Download Tracks (From Youtube With Spotify Metadata)
2) Download from Spotify URL (Track or Playlist)
3) Export Spotify Playlist
0) Exit
```

The downloader uses the Spotify metadata to find the corresponding YouTube video and download the audio.

### 🔗 Spotify URL support

You can also paste a Spotify URL directly.

Supported:

* Spotify track URLs
* Spotify playlist URLs

For playlists, MusicDownloader retrieves the complete available track list rather than relying on Spotify's limited embed-page track list.

### 📚 Large playlist support

Playlists are retrieved through Spotify's internal Pathfinder playlist-content endpoint with pagination.

This allows the application to process playlists containing hundreds or thousands of tracks.

Unavailable or malformed playlist items are skipped instead of stopping the entire operation.

### 🏷️ Automatic ID3 tagging

Downloaded MP3 files are automatically tagged using the metadata obtained from Spotify.

Supported metadata includes:

* Title
* Artist
* Album
* Album artist
* Track number
* Disc number
* Release year
* Genre
* Album artwork

Files are saved using:

```text
Artist - Song Title.mp3
```

Existing files are not overwritten; duplicate filenames receive an incrementing suffix.

### 🖼️ Album artwork

When available, the album cover is downloaded and embedded directly into the MP3's ID3 tags.

### ⚡ Concurrent downloads

Playlist downloads use multiple workers to download tracks concurrently while staggering requests to avoid unnecessary traffic bursts.

Downloads also include retry handling with exponential backoff for transient failures.

### 🍪 YouTube browser cookies

YouTube downloads can use cookies from a local browser session.

By default, MusicDownloader attempts to detect the system's default browser automatically.

This can help when YouTube requires an authenticated browser session or presents bot/verification checks.

### 📦 Playlist export

Spotify playlists can be exported without downloading the music.

Each exported playlist contains:

```text
exported_playlists/
└── Playlist Name/
    ├── playlist.json
    └── playlist.txt
```

`playlist.json` contains the complete metadata collected for the playlist and can be used as a foundation for future re-download functionality.

`playlist.txt` contains a simple list:

```text
Artist - Song
Artist - Another Song
Artist - Another Track
```

---

## 🚀 Getting Started

### Requirements

* Python 3
* FFmpeg
* aria2c
* A supported web browser for optional YouTube cookie extraction

### Installation

Clone the repository:

```bash
git clone https://github.com/ThePishro/musicdownloader.git
cd musicdownloader
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Then start MusicDownloader:

```bash
python main.py
```

---

## 🧭 Usage

After launching the application, you'll see three main options.

### 1. Search & Download Tracks

Search by song or artist:

```text
Enter music/artist name: Amir Tataloo Behesht
```

Choose a result:

```text
 1) Behesht                           [4:12] - Amir Tataloo
 2) ...
```

Add tracks to the queue and enter `done` when you're ready to download.

### 2. Download from Spotify URL

Paste a Spotify track or playlist URL:

```text
Enter a Spotify track or playlist URL:
https://open.spotify.com/track/...
```

The application retrieves the Spotify metadata and handles the YouTube download automatically.

For playlists, tracks are processed concurrently with progress reporting.

### 3. Export Spotify Playlist

Paste a Spotify playlist URL:

```text
Enter Spotify playlist URL:
https://open.spotify.com/playlist/...
```

The playlist is exported to:

```text
exported_playlists/<Playlist Name>/
```

with both a full JSON representation and a human-readable text file.

---

## 🏗️ Architecture

MusicDownloader is split into several responsibilities.

```text
musicdownloader/
│
├── main.py
│
├── src/
│   └── cli_flows.py
│
├── spotify_scraper.py
├── spotify_pathfinder.py
├── playlist_exporter.py
├── downloader.py
├── browser_detect.py
├── utils.py
│
├── core/
│   ├── models/
│   │   └── track.py
│   │
│   └── search/
│       ├── base.py
│       └── youtube_music.py
│
└── requirements.txt
```

### SpotifyPathfinder

Handles anonymous communication with Spotify's Web Player Pathfinder service.

It provides:

* Anonymous authentication
* Track search
* Playlist contents
* Spotify metadata
* Album information
* Artwork information

### SpotifyScraper

Handles Spotify URLs and embed-page metadata.

It connects Spotify URLs to the application's common track metadata format.

### MusicDownloader

Responsible for:

* YouTube search
* Audio downloading
* Format fallbacks
* Browser cookies
* Concurrent downloads
* Retry handling
* MP3 conversion
* ID3 tagging
* Album artwork

### SpotifyPlaylistExporter

Creates reusable playlist exports containing the playlist metadata and complete track information.

---

## 🧰 Tech Stack

* **Python**
* **yt-dlp** — YouTube media extraction/downloading
* **Mutagen** — MP3/ID3 metadata
* **Spotify Web Player / Pathfinder** — anonymous Spotify metadata/search
* **BeautifulSoup** — Spotify embed parsing
* **curl_cffi** — HTTP requests and browser impersonation
* **Rich** — download progress UI
* **aria2c** — HTTP download acceleration
* **Halo / tqdm** — CLI progress feedback

---

## ⚠️ Important Notes

MusicDownloader relies on parts of Spotify's Web Player and internal Pathfinder API that are not official public APIs.

Spotify can change these endpoints, persisted query hashes, authentication flows, or response structures at any time. If that happens, Spotify-related functionality may stop working until the implementation is updated.

YouTube extraction is handled through `yt-dlp` and may also be affected by changes on YouTube's side.

---

## ⚖️ Disclaimer

This project is intended for educational and personal use.

You are responsible for ensuring that anything you download is lawful in your jurisdiction and that you have the necessary rights or permissions to download and store the content.

The project is not affiliated with Spotify, YouTube, or any of their subsidiaries.

---

## 🤝 Contributing

Contributions, bug reports, and improvements are welcome.

If you find a Spotify Pathfinder change, YouTube extraction issue, metadata problem, or anything else that breaks the downloader, feel free to open an issue or submit a pull request.

---

## 📄 License

See the repository for licensing information.
