"""
watch.py
--------
Watches your DJ music folder. When you add a new track, it analyzes it
(BPM + key via your existing analyze.py), converts to Camelot, and writes
it into the same Notion database your DJ Agent already populated.

It reuses dj_agent.py for everything (token, data source, analysis, the
Notion write), so the new rows match your existing schema exactly.

On startup it also reconciles: it scans the folder once and adds any tracks
that aren't in Notion yet, so anything added while the watcher was off gets
picked up the next time it runs.

Run it:
    cd ~/Desktop/Mr.DJ
    python3 watch.py

Stop it with Control + C.
"""

import os
import time
import queue
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import dj_agent as agent
from analyze import analyze_file
from camelot import key_name_to_camelot
from notion_client import Client

# ----------------------------------------------------------------------
# EDIT THIS to your real DJ music folder
# ----------------------------------------------------------------------
WATCH_FOLDER = "/Users/ivyarcher/Desktop/DJ Music"
# ----------------------------------------------------------------------

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aiff", ".aif"}


def is_audio(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def wait_until_stable(path, needed=2, interval=2.0, timeout=180):
    """
    Block until the file size stops changing, so we never analyze a track
    that's still being downloaded/copied. Returns True once stable, False
    if it never settles (or vanishes) within `timeout` seconds.
    """
    last_size = -1
    stable_count = 0
    start = time.time()
    while time.time() - start < timeout:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size > 0 and size == last_size:
            stable_count += 1
            if stable_count >= needed:
                return True
        else:
            stable_count = 0
            last_size = size
        time.sleep(interval)
    return False


def process_file(path, notion, data_source_id, seen):
    """Analyze one file and write it to Notion if it's new. Updates `seen`."""
    if not is_audio(path) or not os.path.exists(path):
        return
    if not wait_until_stable(path):
        print(f"  ! skip (file never finished writing): {os.path.basename(path)}")
        return

    title, artist = agent.read_tags(path)
    if title in seen:
        print(f"  = already in Notion: {title}")
        return

    try:
        feats = analyze_file(path)
    except Exception as e:
        print(f"  ! failed to analyze {title}: {e}")
        return

    track = {"name": title, "artist": artist, **feats}
    try:
        agent.write_track_to_notion(notion, data_source_id, track)
    except Exception as e:
        print(f"  ! failed to write {title} to Notion: {e}")
        return

    seen.add(title)
    cam = key_name_to_camelot(feats.get("key_str")) or "?"
    print(f"  + added: {title} - {artist} ({feats['bpm']} BPM, {cam})")


class NewTrackHandler(FileSystemEventHandler):
    """Pushes new/renamed audio file paths onto a queue for the worker."""

    def __init__(self, work_queue):
        self.q = work_queue

    def on_created(self, event):
        if not event.is_directory and is_audio(event.src_path):
            self.q.put(event.src_path)

    def on_moved(self, event):
        # downloaders often write a temp file then rename it to the final name
        if not event.is_directory and is_audio(event.dest_path):
            self.q.put(event.dest_path)


def worker(work_queue, notion, data_source_id, seen):
    while True:
        path = work_queue.get()
        if path is None:
            break
        try:
            process_file(path, notion, data_source_id, seen)
        finally:
            work_queue.task_done()


def reconcile(folder, notion, data_source_id, seen):
    """One-time scan at startup to catch files added while the watcher was off."""
    files = agent.find_audio_files(folder)
    new = 0
    for path in files:
        title, _ = agent.read_tags(path)
        if title not in seen:
            process_file(path, notion, data_source_id, seen)
            new += 1
    print(f"Startup reconcile: checked {len(files)} files, added {new} new.\n")


def main():
    if not os.path.isdir(WATCH_FOLDER):
        print(f"Folder not found: {WATCH_FOLDER}\nEdit WATCH_FOLDER at the top of watch.py.")
        return

    notion = Client(auth=agent.NOTION_TOKEN)
    data_source_id = agent.get_data_source_id(notion)
    seen = agent.existing_song_names(notion, data_source_id)
    print(f"Connected to Notion. {len(seen)} tracks already in the database.")
    print(f"Watching: {WATCH_FOLDER}\n")

    # catch up on anything added while we were off
    reconcile(WATCH_FOLDER, notion, data_source_id, seen)

    work_queue = queue.Queue()
    threading.Thread(
        target=worker,
        args=(work_queue, notion, data_source_id, seen),
        daemon=True,
    ).start()

    observer = Observer()
    observer.schedule(NewTrackHandler(work_queue), WATCH_FOLDER, recursive=True)
    observer.start()
    print("Watching for new tracks. Drop a file in the folder to test. Control + C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
