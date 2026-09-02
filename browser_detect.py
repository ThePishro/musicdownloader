"""Best-effort detection of the user's OS-level default browser, mapped to
the browser name yt-dlp's --cookies-from-browser / cookiesfrombrowser
option expects (chrome, firefox, edge, brave, opera, vivaldi, chromium,
safari).

Detection failing is expected and handled gracefully everywhere this is
used — it just means "fall back to no cookies, or let the user specify
one explicitly," not a hard error.
"""

import platform
import subprocess
from typing import Optional

# Fragments matched against the Linux .desktop id / Windows ProgId,
# lowercased. Order doesn't matter — first substring match wins.
_LINUX_DESKTOP_ID_MAP = {
    "firefox": "firefox",
    "google-chrome": "chrome",
    "chromium": "chromium",
    "brave": "brave",
    "microsoft-edge": "edge",
    "opera": "opera",
    "vivaldi": "vivaldi",
}

_WINDOWS_PROGID_MAP = {
    "firefoxurl": "firefox",
    "chromehtml": "chrome",
    "msedgehtm": "edge",
    "bravehtml": "brave",
    "operastable": "opera",
    "vivaldihtm": "vivaldi",
}

# Reasonable fallback order when auto-detection fails entirely — most
# commonly installed / most likely to actually have YouTube cookies.
FALLBACK_BROWSER_PRIORITY = ["chrome", "firefox", "edge", "brave"]


def detect_default_browser() -> Optional[str]:
    """Returns a yt-dlp-compatible browser name, or None if detection
    fails (unsupported OS, tool not available, unrecognized browser, etc).
    """
    system = platform.system()

    try:
        if system == "Linux":
            return _detect_linux_default_browser()
        if system == "Windows":
            return _detect_windows_default_browser()
        if system == "Darwin":
            return _detect_macos_default_browser()
    except Exception:
        pass

    return None


def _detect_linux_default_browser() -> Optional[str]:
    # xdg-settings is part of xdg-utils, present on virtually every
    # desktop Linux distro (GNOME, KDE, XFCE, etc all ship it).
    result = subprocess.run(
        ["xdg-settings", "get", "default-web-browser"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    desktop_id = result.stdout.strip().lower()  # e.g. "firefox.desktop"
    for fragment, name in _LINUX_DESKTOP_ID_MAP.items():
        if fragment in desktop_id:
            return name
    return None


def _detect_windows_default_browser() -> Optional[str]:
    import winreg  # only importable on Windows

    key_path = (
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations"
        r"\http\UserChoice"
    )
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        prog_id, _ = winreg.QueryValueEx(key, "ProgId")

    prog_id_lower = prog_id.lower()
    for fragment, name in _WINDOWS_PROGID_MAP.items():
        if fragment in prog_id_lower:
            return name
    return None


def _detect_macos_default_browser() -> Optional[str]:
    # macOS default-app detection reliably needs LaunchServices' binary
    # plist parsed properly (e.g. via `plutil` to convert to JSON first) —
    # not attempting a fragile text-scrape here. Falls through to the
    # caller's fallback list on macOS for now.
    return None
