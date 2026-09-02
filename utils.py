import re


def sanitize_filename(name: str) -> str:
    """Strip characters invalid in filenames/folder names across
    Windows/macOS/Linux, and collapse whitespace. Falls back to
    'Unknown' if the result would be empty.
    """
    name = re.sub(r'[\\/*?:"<>|]', "", name or "")
    return re.sub(r"\s+", " ", name).strip() or "Unknown"
