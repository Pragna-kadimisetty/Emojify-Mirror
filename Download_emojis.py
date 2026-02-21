"""
╔══════════════════════════════════════════════════════════════╗
║            EMOJI AUTO-DOWNLOADER                            ║
║  Downloads real RGBA emoji PNGs from OpenMoji (free CDN)   ║
╚══════════════════════════════════════════════════════════════╝

Run this ONCE before starting emojify_mirror.py:
    python download_emojis.py
"""

import os
import urllib.request
import urllib.error

# ─────────────────────────────────────────────────────────────────────────────
#  OpenMoji CDN URLs — these are free, open-source emoji PNGs (RGBA ✅)
#  Each URL points to a 618×618 px PNG with full transparency support.
#  Unicode code points used:
#    happy    → 😄 U+1F604   Grinning Face With Smiling Eyes
#    sad      → 😢 U+1F622   Crying Face
#    angry    → 😠 U+1F620   Angry Face
#    surprise → 😲 U+1F632   Astonished Face
#    neutral  → 😐 U+1F610   Neutral Face
#    fear     → 😨 U+1F628   Fearful Face
#    disgust  → 🤢 U+1F922   Nauseated Face
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618"

EMOJI_URLS = {
    "happy":    f"{BASE_URL}/1F604.png",
    "sad":      f"{BASE_URL}/1F622.png",
    "angry":    f"{BASE_URL}/1F620.png",
    "surprise": f"{BASE_URL}/1F632.png",
    "neutral":  f"{BASE_URL}/1F610.png",
    "fear":     f"{BASE_URL}/1F628.png",
    "disgust":  f"{BASE_URL}/1F922.png",
}

OUTPUT_DIR = "emojis"


def download_emojis():
    """Download all emoji PNGs into the /emojis folder."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n📥  Downloading {len(EMOJI_URLS)} emoji PNGs from OpenMoji...\n")

    success = 0
    failed  = []

    for emotion, url in EMOJI_URLS.items():
        dest = os.path.join(OUTPUT_DIR, f"{emotion}.png")

        # Skip if already downloaded
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  ✅  {emotion}.png  (already exists, skipping)")
            success += 1
            continue

        try:
            print(f"  ⬇️   Downloading {emotion}.png ...", end="", flush=True)

            # Add a browser-like User-Agent header so GitHub raw doesn't block us
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (EmojifyMirror/1.0)"
            })
            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read()

            with open(dest, "wb") as f:
                f.write(data)

            size_kb = len(data) / 1024
            print(f"  done!  ({size_kb:.1f} KB)")
            success += 1

        except urllib.error.URLError as e:
            print(f"  FAILED ❌  ({e.reason})")
            failed.append(emotion)

        except Exception as e:
            print(f"  FAILED ❌  ({e})")
            failed.append(emotion)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"  ✅  Downloaded: {success}/{len(EMOJI_URLS)}")

    if failed:
        print(f"  ❌  Failed:     {', '.join(failed)}")
        print("\n  If downloads failed, check your internet connection,")
        print("  or manually download PNGs from:")
        print("  https://openmoji.org/library/  (search each emotion name)")
        print("  Save them as:  emojis/happy.png, emojis/sad.png ... etc.\n")
    else:
        print("\n  🎉  All emojis ready!  Now run:  python emojify_mirror.py\n")


if __name__ == "__main__":
    download_emojis()