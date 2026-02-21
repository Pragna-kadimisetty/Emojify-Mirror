"""
╔══════════════════════════════════════════════════════════════╗
║              THE EMOJIFY MIRROR 🪞                          ║
║    Real-time Face Emotion Detection + Emoji Overlay         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python emojify_mirror.py

Controls:
    Q       → Quit
    S       → Save a screenshot
    +/-     → Increase/Decrease emoji opacity
    SPACE   → Toggle emoji overlay on/off
"""

import cv2
import numpy as np
import time
import os
import urllib.request
import urllib.error
from collections import deque

# Suppress TensorFlow noise in the terminal
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from fer import FER


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION  ← tweak these values to tune the app
# ─────────────────────────────────────────────────────────────────────────────
CAMERA_INDEX   = 0       # 0 = built-in webcam; try 1/2 if nothing shows
FRAME_WIDTH    = 1280
FRAME_HEIGHT   = 720
EMOJI_DIR      = "emojis"
DETECTION_SKIP = 3       # run FER every N frames  (higher → faster FPS)
SMOOTH_WINDOW  = 8       # frames to average emotion scores over
PADDING_FACTOR = 0.25    # emoji padding relative to face size
MIN_CONFIDENCE = 0.25    # ignore emotions scored below this

# OpenMoji CDN — free open-source RGBA PNGs (618×618 px, transparent bg)
_BASE = "https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/color/618x618"
EMOJI_URLS = {
    "happy":    f"{_BASE}/1F604.png",   # 😄
    "sad":      f"{_BASE}/1F622.png",   # 😢
    "angry":    f"{_BASE}/1F620.png",   # 😠
    "surprise": f"{_BASE}/1F632.png",   # 😲
    "neutral":  f"{_BASE}/1F610.png",   # 😐
    "fear":     f"{_BASE}/1F628.png",   # 😨
    "disgust":  f"{_BASE}/1F922.png",   # 🤢
}

# UI colours (BGR for OpenCV)
COLOR_TEXT   = (255, 255, 255)
COLOR_SHADOW = (0,   0,   0  )
COLOR_BAR_BG = (50,  50,  50 )
COLOR_BAR_FG = {
    "happy":    (0,   215, 255),
    "sad":      (220, 80,  80 ),
    "angry":    (30,  30,  220),
    "surprise": (0,   165, 255),
    "neutral":  (180, 180, 180),
    "fear":     (200, 0,   200),
    "disgust":  (50,  180, 50 ),
}
FONT      = cv2.FONT_HERSHEY_DUPLEX
FONT_BOLD = cv2.FONT_HERSHEY_TRIPLEX


# ─────────────────────────────────────────────────────────────────────────────
#  AUTO-DOWNLOAD EMOJIS
# ─────────────────────────────────────────────────────────────────────────────
def ensure_emojis_downloaded(emoji_dir: str) -> None:
    """
    Automatically downloads any missing emoji PNGs from OpenMoji on GitHub.
    Safe to call every run — skips files that already exist on disk.
    """
    os.makedirs(emoji_dir, exist_ok=True)

    missing = [
        name for name in EMOJI_URLS
        if not os.path.exists(os.path.join(emoji_dir, f"{name}.png"))
        or os.path.getsize(os.path.join(emoji_dir, f"{name}.png")) < 1000
    ]

    if not missing:
        print("  [OK] All emoji PNGs present.")
        return

    print(f"  Downloading {len(missing)} missing emoji(s) from OpenMoji CDN…\n")

    for emotion in missing:
        dest = os.path.join(emoji_dir, f"{emotion}.png")
        url  = EMOJI_URLS[emotion]
        try:
            print(f"    ⬇  {emotion}.png", end="", flush=True)
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (EmojifyMirror/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"  OK  ({len(data)//1024} KB)")
        except Exception as exc:
            print(f"  FAILED — {exc}")
            print(f"    → Manually save any RGBA PNG as: {dest}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
#  EMOJI LOADER
# ─────────────────────────────────────────────────────────────────────────────
def load_emojis(emoji_dir: str) -> dict:
    """Load RGBA emoji PNGs from disk into memory as NumPy arrays."""
    result = {}
    for emotion in EMOJI_URLS:
        path = os.path.join(emoji_dir, f"{emotion}.png")
        if not os.path.exists(path):
            continue
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        if img.ndim == 2:                         # grayscale → BGRA
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:                   # RGB → BGRA (add full alpha)
            alpha = np.full(img.shape[:2], 255, dtype=img.dtype)
            img   = cv2.merge([img, alpha])
        result[emotion] = img
        print(f"  [OK] {emotion}.png  ({img.shape[1]}×{img.shape[0]})")
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  ALPHA BLENDING  ← the critical compositing function
# ─────────────────────────────────────────────────────────────────────────────
def alpha_blend(frame: np.ndarray, overlay: np.ndarray,
                x: int, y: int, opacity: float = 1.0) -> np.ndarray:
    """
    Blend a 4-channel BGRA emoji over a 3-channel BGR frame.

    Per-pixel formula:
        output = α * emoji_color + (1 − α) * frame_color
    where α = (emoji_alpha / 255) × global_opacity

    Fully vectorised with NumPy — no Python pixel loops.
    """
    out    = frame.copy()
    oh, ow = overlay.shape[:2]
    fh, fw = frame.shape[:2]

    # Clamp to frame bounds
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + ow, fw), min(y + oh, fh)
    if x1 >= x2 or y1 >= y2:
        return out

    crop      = overlay[y1 - y : y1 - y + (y2 - y1),
                        x1 - x : x1 - x + (x2 - x1)]
    emoji_bgr = crop[..., :3].astype(np.float32)
    alpha     = crop[...,  3].astype(np.float32) / 255.0 * opacity
    alpha_3ch = alpha[:, :, np.newaxis]

    bg      = out[y1:y2, x1:x2].astype(np.float32)
    blended = alpha_3ch * emoji_bgr + (1.0 - alpha_3ch) * bg

    out[y1:y2, x1:x2] = blended.astype(np.uint8)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def draw_text_shadow(frame, text, pos, font=FONT, scale=0.8,
                     thickness=2, color=COLOR_TEXT):
    x, y = pos
    cv2.putText(frame, text, (x+2, y+2), font, scale,
                COLOR_SHADOW, thickness+1, cv2.LINE_AA)
    cv2.putText(frame, text, (x,   y  ), font, scale,
                color,       thickness,   cv2.LINE_AA)


def draw_conf_bar(frame, emotion, conf, x, y, w=160, h=12):
    cv2.rectangle(frame, (x, y), (x+w, y+h), COLOR_BAR_BG, -1)
    cv2.rectangle(frame, (x, y), (x+int(w*min(conf,1)), y+h),
                  COLOR_BAR_FG.get(emotion, (200,200,200)), -1)
    cv2.rectangle(frame, (x, y), (x+w, y+h), (100,100,100), 1)


def draw_hud(frame, fps, emoji_on, opacity):
    fh, _ = frame.shape[:2]
    for i, line in enumerate(reversed([
        f"FPS: {fps:5.1f}",
        f"Emoji: {'ON' if emoji_on else 'OFF'}",
        f"Opacity: {int(opacity*100)}%",
        "[Q] Quit  [S] Save  [Space] Toggle",
        "[+]/[-] Opacity",
    ])):
        draw_text_shadow(frame, line, (10, fh - 10 - i*22), scale=0.5, thickness=1)


# ─────────────────────────────────────────────────────────────────────────────
#  EMOTION SMOOTHER  — removes flickering via temporal averaging
# ─────────────────────────────────────────────────────────────────────────────
class EmotionSmoother:
    def __init__(self, window=SMOOTH_WINDOW):
        self.history = deque(maxlen=window)

    def update(self, scores: dict) -> tuple:
        self.history.append(scores)
        totals = {}
        for s in self.history:
            for e, v in s.items():
                totals[e] = totals.get(e, 0.0) + v
        n = len(self.history)
        avg  = {e: v/n for e, v in totals.items()}
        best = max(avg, key=avg.get)
        return best, avg[best]


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n🪞  Emojify Mirror — Starting up…\n")

    # 1. Auto-download missing emoji PNGs
    print("Checking emoji assets:")
    ensure_emojis_downloaded(EMOJI_DIR)

    # 2. Load PNGs into memory
    print("Loading emojis:")
    emojis = load_emojis(EMOJI_DIR)
    if not emojis:
        print("\n[ERROR] No emoji assets found. Check internet / ./emojis/ folder.\n")
        return

    # 3. Init FER
    print("\nLoading FER model…")
    detector = FER(mtcnn=False)
    print("  [OK] FER ready.\n")

    # 4. Open webcam
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {CAMERA_INDEX}.")
        return

    smoother       = EmotionSmoother()
    emoji_on       = True
    opacity        = 0.85
    frame_count    = 0
    last_results   = None
    fps_times      = deque(maxlen=30)
    screenshot_idx = 0

    print("▶  Running! Press Q to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        frame_count += 1

        # Detect every N frames for speed
        if frame_count % DETECTION_SKIP == 0:
            last_results = detector.detect_emotions(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )

        for face in (last_results or []):
            fx, fy, fw, fh = face["box"]
            dominant, conf  = smoother.update(face["emotions"])

            if conf < MIN_CONFIDENCE:
                continue

            # Emoji overlay
            if emoji_on and dominant in emojis:
                pad  = int(max(fw, fh) * PADDING_FACTOR)
                sz   = max(fw, fh) + pad * 2
                rsz  = cv2.resize(emojis[dominant], (sz, sz),
                                  interpolation=cv2.INTER_LANCZOS4)
                frame = alpha_blend(frame, rsz,
                                    fx + fw//2 - sz//2,
                                    fy + fh//2 - sz//2, opacity)

            # Bar + label
            bar_color = COLOR_BAR_FG.get(dominant, COLOR_TEXT)
            if fy - 30 > 10:
                draw_conf_bar(frame, dominant, conf, fx, fy-30, w=fw)
            draw_text_shadow(frame, f"{dominant.upper()}  {conf*100:.0f}%",
                             (fx, fy-36), font=FONT_BOLD,
                             scale=0.65, thickness=2, color=bar_color)
            cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), bar_color, 2)

        # FPS
        fps_times.append(time.time())
        fps = ((len(fps_times)-1)/(fps_times[-1]-fps_times[0])
               if len(fps_times) >= 2 else 0.0)

        draw_hud(frame, fps, emoji_on, opacity)
        cv2.imshow("Emojify Mirror", frame)

        key = cv2.waitKey(1) & 0xFF
        if   key == ord("q"):               
            break
        elif key == ord(" "):    
            emoji_on = not emoji_on
        elif key == ord("s"):
            fn = f"screenshot_{screenshot_idx:04d}.png"
            cv2.imwrite(fn, frame)
            print(f"[INFO] Saved {fn}")
            screenshot_idx += 1
        elif key in (ord("+"), ord("=")):  
            opacity = min(1.0, opacity+0.05)
        elif key == ord("-"):      
            opacity = max(0.1, opacity-0.05)

    cap.release()
    cv2.destroyAllWindows()
    print("Goodbye! 👋")


if __name__ == "__main__":
    main()