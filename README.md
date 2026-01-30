# 🎵 Music-Downloader

Music Downloader is a Python-based project designed to help users manage their music offline.
The project starts by exporting Spotify playlist tracks into a clean and readable text format
and will gradually evolve into a more complete offline music management tool.

This repository is developed step-by-step and is beginner-friendly for contributors.

---

## 🚀 Current Features

- Export Spotify playlist tracks
- Output format:
  
  Artist - Song Name
  
- Save playlist data into a `.txt` file

---

## 🧠 Motivation

This project was born out of a real personal need.

Losing access to the internet made it clear how important it is to have music available locally.
Since most of my music is stored on Spotify, this tool aims to bridge the gap between
online playlists and offline access.

---

## 🛠 Tech Stack

- **Language:** Python
- **API:** Spotify Web API
- **Authentication:** OAuth 2.0
- **Type:** CLI-based application (initial phase)

---

## 📦 Project Structure (Initial)
```text
musicdownloader/
│
├── src/
│   ├── spotify/
│   │   └── playlist_exporter.py
│   └── main.py
│
├── output/
│   └── playlists.txt
│
├── requirements.txt
└── README.md

🧩 Roadmap

[x] Export playlist track names
[ ] Support multiple playlists
[ ] Add CLI arguments
[ ] Track metadata (album, duration, release year)
[ ] Music downloading (future phase)
[ ] Cross-platform support
```
🤝 Contributing
Contributions are welcome!

If you have ideas, suggestions, or improvements, feel free to open an issue

or submit a pull request.

---

⚠️ Disclaimer
This project is intended for educational and personal use only.

Downloading copyrighted content may violate Spotify’s terms of service.
