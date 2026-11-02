"""
Camelot Wheel logic for harmonic mixing.
Converts musical key + mode into Camelot notation, and finds compatible keys.
"""

# Spotify-style pitch class (0-11) + mode (0 = minor, 1 = major) -> Camelot
# This map also works if you feed it standard key names via KEY_NAME_TO_CAMELOT below.
PITCH_MODE_TO_CAMELOT = {
    (0, 1): "8B",   (0, 0): "5A",    # C major / C minor
    (1, 1): "3B",   (1, 0): "12A",   # C#/Db
    (2, 1): "10B",  (2, 0): "7A",    # D
    (3, 1): "5B",   (3, 0): "2A",    # D#/Eb
    (4, 1): "12B",  (4, 0): "9A",    # E
    (5, 1): "7B",   (5, 0): "4A",    # F
    (6, 1): "2B",   (6, 0): "11A",   # F#/Gb
    (7, 1): "9B",   (7, 0): "6A",    # G
    (8, 1): "4B",   (8, 0): "1A",    # G#/Ab
    (9, 1): "11B",  (9, 0): "8A",    # A
    (10, 1): "6B",  (10, 0): "3A",   # A#/Bb
    (11, 1): "1B",  (11, 0): "10A",  # B
}

# For sources (like GetSongBPM) that give you a key string like "A minor" or "F# major"
KEY_NAME_TO_PITCH = {
    "c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4,
    "f": 5, "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9,
    "a#": 10, "bb": 10, "b": 11,
}


def key_name_to_camelot(key_str):
    """
    Convert a human key string like 'A minor', 'F# major', 'Bb min' into Camelot.
    Returns e.g. '8A' or None if it can't parse.
    """
    if not key_str:
        return None
    s = key_str.strip().lower()
    mode = 1  # default major
    if "min" in s or s.endswith("m"):
        mode = 0
    # strip mode words
    for token in ["major", "minor", "maj", "min"]:
        s = s.replace(token, "")
    s = s.strip().rstrip("m").strip()
    pitch = KEY_NAME_TO_PITCH.get(s)
    if pitch is None:
        return None
    return PITCH_MODE_TO_CAMELOT.get((pitch, mode))


def compatible_camelot(camelot):
    """
    Given a Camelot code like '8A', return the harmonically compatible codes.
    Rules: same key, +1, -1 (around the 12-hour wheel), and same number opposite letter.
    """
    if not camelot or len(camelot) < 2:
        return []
    number = int(camelot[:-1])
    letter = camelot[-1].upper()

    def wrap(n):
        # wheel is 1-12
        return ((n - 1) % 12) + 1

    same = f"{number}{letter}"
    up = f"{wrap(number + 1)}{letter}"
    down = f"{wrap(number - 1)}{letter}"
    flip = f"{number}{'B' if letter == 'A' else 'A'}"
    return [same, up, down, flip]


def bpm_compatible(bpm_a, bpm_b, tolerance=0.06):
    """
    True if two BPMs are within tolerance (default 6%).
    Also treats half/double time as compatible (e.g. 70 and 140).
    """
    if not bpm_a or not bpm_b:
        return False
    for factor in (1.0, 0.5, 2.0):
        target = bpm_b * factor
        if abs(bpm_a - target) <= bpm_a * tolerance:
            return True
    return False


if __name__ == "__main__":
    # quick self-test
    print("A minor ->", key_name_to_camelot("A minor"))      # 8A
    print("compatible with 8A ->", compatible_camelot("8A"))  # 8A, 9A, 7A, 8B
    print("128 vs 130 ->", bpm_compatible(128, 130))          # True
    print("128 vs 145 ->", bpm_compatible(128, 145))          # False
