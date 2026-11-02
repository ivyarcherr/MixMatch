"""
DJ Agent (local edition)
------------------------
Analyzes the MP3s in your library to extract BPM + key, converts to Camelot,
writes everything to a Notion database, and recommends harmonic mixes.

No Spotify, no external BPM API. Everything is computed from your own files.

Run modes:
    python dj_agent.py analyze "/path/to/your/music/folder"   -> analyze + write to Notion
    python dj_agent.py mix "Song Name"                        -> recommend mixes from your Notion library
"""

import os
import sys
import glob

from mutagen import File as MutagenFile
from notion_client import Client

from camelot import key_name_to_camelot, compatible_camelot, bpm_compatible
from analyze import analyze_file

# ----------------------------------------------------------------------
# CONFIG - fill these in
# ----------------------------------------------------------------------
NOTION_TOKEN = PASTE_KEY_HERE
NOTION_DATABASE_ID = PASTE_KEY_HERE
# ----------------------------------------------------------------------

AUDIO_EXTS = ("*.mp3", "*.wav", "*.flac", "*.m4a", "*.aiff", "*.aif")


# ---------- Read tags ----------
def read_tags(path):
    """Pull song title + artist from the file's metadata. Falls back to filename."""
    title, artist = None, None
    try:
        audio = MutagenFile(path, easy=True)
        if audio:
            title = (audio.get("title") or [None])[0]
            artist = (audio.get("artist") or [None])[0]
    except Exception:
        pass
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    if not artist:
        artist = ""
    return title, artist


def find_audio_files(folder):
    files = []
    for ext in AUDIO_EXTS:
        files.extend(glob.glob(os.path.join(folder, "**", ext), recursive=True))
    return sorted(files)


# ---------- Notion ----------
def get_data_source_id(notion):
    """
    The current Notion API puts a 'data source' inside each database.
    Queries and new pages go through the data source, not the database directly.
    This looks up the data source ID from your database ID once.
    """
    db = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    sources = db.get("data_sources", [])
    if not sources:
        raise RuntimeError(
            "No data source found on this database. Make sure the database ID "
            "is correct and the DJ Agent integration is connected to it."
        )
    return sources[0]["id"]


def write_track_to_notion(notion, data_source_id, track):
    camelot = key_name_to_camelot(track.get("key_str")) or ""
    notion.pages.create(
        parent={"type": "data_source_id", "data_source_id": data_source_id},
        properties={
            "Song": {"title": [{"text": {"content": track["name"]}}]},
            "Artist": {"rich_text": [{"text": {"content": track["artist"]}}]},
            "BPM": {"number": track["bpm"]},
            "Key": {"rich_text": [{"text": {"content": track.get("key_str") or ""}}]},
            "Camelot": {"rich_text": [{"text": {"content": camelot}}]},
        },
    )


def existing_song_names(notion, data_source_id):
    """Return a set of song names already in Notion, to skip re-analyzing."""
    names = set()
    cursor = None
    while True:
        kwargs = {"data_source_id": data_source_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        for row in resp["results"]:
            names.add(_text(row["properties"].get("Song")))
        if resp.get("has_more"):
            cursor = resp["next_cursor"]
        else:
            break
    return names


def read_library_from_notion(notion, data_source_id):
    library = []
    cursor = None
    while True:
        kwargs = {"data_source_id": data_source_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.data_sources.query(**kwargs)
        for row in resp["results"]:
            props = row["properties"]
            library.append({
                "name": _text(props.get("Song")),
                "artist": _text(props.get("Artist")),
                "bpm": props.get("BPM", {}).get("number"),
                "camelot": _text(props.get("Camelot")),
            })
        if resp.get("has_more"):
            cursor = resp["next_cursor"]
        else:
            break
    return library


def _text(prop):
    if not prop:
        return ""
    for kind in ("title", "rich_text"):
        if kind in prop and prop[kind]:
            return prop[kind][0]["plain_text"]
    return ""


# ---------- Recommender ----------
def recommend_mixes(library, seed_name):
    seed = next((t for t in library if seed_name.lower() in t["name"].lower()), None)
    if not seed:
        print(f"Couldn't find '{seed_name}' in your library.")
        return
    if not seed["camelot"] or not seed["bpm"]:
        print(f"'{seed['name']}' is missing BPM or Camelot data.")
        return

    compatible_keys = compatible_camelot(seed["camelot"])
    print(f"\nMixing from: {seed['name']} - {seed['artist']} "
          f"({seed['bpm']} BPM, {seed['camelot']})")
    print(f"Compatible keys: {', '.join(compatible_keys)}\n")

    matches = [
        t for t in library
        if t["name"] != seed["name"]
        and t["camelot"] in compatible_keys
        and bpm_compatible(seed["bpm"], t["bpm"])
    ]
    if not matches:
        print("No harmonic matches found yet. Analyze more tracks.")
        return

    matches.sort(key=lambda t: abs((t["bpm"] or 0) - seed["bpm"]))
    print("Recommended next tracks:")
    for t in matches:
        print(f"  - {t['name']} - {t['artist']} ({t['bpm']} BPM, {t['camelot']})")


# ---------- Main ----------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    mode = sys.argv[1]
    notion = Client(auth=NOTION_TOKEN)
    data_source_id = get_data_source_id(notion)

    if mode == "analyze":
        folder = sys.argv[2]
        files = find_audio_files(folder)
        print(f"Found {len(files)} audio files.")
        seen = existing_song_names(notion, data_source_id)

        for path in files:
            title, artist = read_tags(path)
            if title in seen:
                print(f"  = skip (already in Notion): {title}")
                continue
            try:
                feats = analyze_file(path)
            except Exception as e:
                print(f"  ! failed to analyze {title}: {e}")
                continue
            track = {"name": title, "artist": artist, **feats}
            write_track_to_notion(notion, data_source_id, track)
            cam = key_name_to_camelot(feats.get("key_str")) or "?"
            print(f"  + {title} - {artist} ({feats['bpm']} BPM, {cam})")

        print("Done. Library updated in Notion.")

    elif mode == "mix":
        seed_name = sys.argv[2]
        library = read_library_from_notion(notion, data_source_id)
        recommend_mixes(library, seed_name)

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
