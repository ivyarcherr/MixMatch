"""
Local audio analysis: extract BPM and musical key from an audio file.

BPM  -> librosa beat tracking
Key  -> chroma features matched against Krumhansl-Schmuckler key profiles
"""

import warnings
import numpy as np
import librosa

warnings.filterwarnings("ignore")  # librosa is chatty about deprecations

# Krumhansl-Schmuckler key profiles (correlation templates for major/minor)
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def detect_bpm(y, sr):
    """Estimate tempo in BPM."""
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo = np.atleast_1d(tempo)[0]  # newer librosa returns an array
    return int(round(float(tempo)))


def detect_key(y, sr):
    """
    Estimate musical key. Returns a string like 'A minor' or 'F# major'.
    Works by averaging chroma energy across the track and correlating
    against rotated major/minor profiles.
    """
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    best_corr = -np.inf
    best_key = None
    for i in range(12):
        major_rot = np.roll(MAJOR_PROFILE, i)
        minor_rot = np.roll(MINOR_PROFILE, i)
        corr_major = np.corrcoef(chroma_mean, major_rot)[0, 1]
        corr_minor = np.corrcoef(chroma_mean, minor_rot)[0, 1]
        if corr_major > best_corr:
            best_corr = corr_major
            best_key = f"{PITCH_NAMES[i]} major"
        if corr_minor > best_corr:
            best_corr = corr_minor
            best_key = f"{PITCH_NAMES[i]} minor"
    return best_key


def analyze_file(path, duration=90):
    """
    Analyze an audio file. Loads up to `duration` seconds from the middle
    of the track (the drop / main section is more representative than the intro).
    Returns {bpm, key_str}.
    """
    # peek at total length so we can sample the middle
    total = librosa.get_duration(path=path)
    offset = max(0, (total - duration) / 2)
    y, sr = librosa.load(path, sr=22050, mono=True, offset=offset, duration=duration)
    return {
        "bpm": detect_bpm(y, sr),
        "key_str": detect_key(y, sr),
    }


if __name__ == "__main__":
    # self-test: generate a 120 BPM click in A minor and check detection is sane
    sr = 22050
    dur = 10
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    # A minor triad: A(440), C(523.25), E(659.25)
    tone = (np.sin(2 * np.pi * 440 * t)
            + np.sin(2 * np.pi * 523.25 * t)
            + np.sin(2 * np.pi * 659.25 * t))
    # add a click every 0.5s (= 120 BPM)
    click = np.zeros_like(t)
    for beat in np.arange(0, dur, 0.5):
        idx = int(beat * sr)
        click[idx:idx + 200] += 1.0
    y = (0.5 * tone + click).astype(np.float32)
    print("Detected BPM:", detect_bpm(y, sr), "(expected ~120)")
    print("Detected key:", detect_key(y, sr), "(expected A minor / C major family)")
