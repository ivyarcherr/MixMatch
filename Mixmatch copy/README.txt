DJ AGENT (LOCAL EDITION) - SETUP GUIDE
======================================

What it does:
  - Scans a folder of your music files (mp3, wav, flac, m4a, aiff)
  - Reads song title + artist from each file's tags
  - Analyzes the actual audio to compute BPM + key (no Spotify, no external API)
  - Converts key to Camelot notation
  - Writes everything to a Notion database
  - Recommends harmonically compatible mixes from your library


WHERE TO PUT THE CODE
---------------------
Put all three files in ONE folder on your computer, for example a folder
called "dj_agent" on your Desktop:

    dj_agent/
      dj_agent.py      <- the main script you run
      analyze.py       <- audio analysis (BPM + key)
      camelot.py       <- Camelot wheel + mixing logic

dj_agent.py imports the other two, so they must sit next to each other.
You don't edit analyze.py or camelot.py. You only run dj_agent.py.


STEP 1 - Install Python packages
--------------------------------
Open Terminal and paste:

    pip install librosa mutagen notion-client numpy soundfile

(If you get an "externally managed environment" error, add --break-system-packages
to the end of that command.)


STEP 2 - Set up Notion
----------------------
  - Go to https://www.notion.so/my-integrations
  - "New integration", name it "DJ Agent", copy the token (starts with "secret_" or "ntn_")
  - Create a database with these EXACT property names:
        Song      -> Title
        Artist    -> Text
        BPM       -> Number
        Key       -> Text
        Camelot   -> Text
  - Open the database, click "..." -> Connections -> add your DJ Agent integration
  - Grab the database ID from the URL:
        notion.so/workspace/DATABASE_ID?v=...
    The DATABASE_ID is the 32-character string before the "?"


STEP 3 - Fill in the config
---------------------------
Open dj_agent.py in any text editor. At the top, paste your two values:

    NOTION_TOKEN = "your token here"
    NOTION_DATABASE_ID = "your database id here"


STEP 4 - Run it
---------------
Open Terminal, cd into the folder, then:

Analyze your whole music library and write it to Notion:

    cd ~/Desktop/dj_agent
    python dj_agent.py analyze "/path/to/your/music/folder"

(Drag the music folder onto the Terminal window to paste its path automatically.)

Get mix recommendations for any track already analyzed:

    python dj_agent.py mix "Levels"


HOW IT WORKS
------------
- BPM comes from librosa beat tracking.
- Key comes from chroma analysis matched against Krumhansl-Schmuckler key
  profiles (the standard academic method for key detection).
- It analyzes ~90 seconds from the MIDDLE of each track (the main section is
  more representative than the intro).
- Re-running "analyze" skips songs already in Notion, so it won't duplicate.
- Recommender uses Camelot rules: same key, +1, -1, and same-number opposite
  letter, filtered to within 6% BPM (half/double time counts).


ACCURACY NOTE
-------------
Audio key detection is good but not perfect, roughly 70-85% on real tracks
depending on genre. BPM is usually very accurate for electronic/dance music
with a steady beat. For tracks where the detected key looks off, you can edit
the Key + Camelot fields directly in Notion. Cross-checking against what your
ears tell you on the Pioneer is always the final word.
