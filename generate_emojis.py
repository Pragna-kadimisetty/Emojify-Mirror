"""
generate_emojis.py
──────────────────
Generates placeholder RGBA emoji PNGs for all 7 emotions.
Run this if the /emojis folder is missing or you want to regenerate them.

Usage:
    python generate_emojis.py

For best results, replace the generated PNGs with real emoji images from:
    https://openmoji.org  (free, open-source, RGBA ✅)
"""

import os
from PIL import Image, ImageDraw

OUTPUT_DIR = "emojis"
SIZE       = 256   # pixel size — larger = higher quality when resized

EMOTIONS = {
    "happy":    (255, 200,  30),   # golden yellow
    "sad":      ( 80, 120, 220),   # blue
    "angry":    (210,  40,  40),   # red
    "surprise": (255, 150,  30),   # orange
    "neutral":  (160, 160, 160),   # grey
    "fear":     (160,  60, 200),   # purple
    "disgust":  ( 60, 160,  60),   # green
}


def draw_face(emotion: str, color: tuple, size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r, g, b = color
    dark = (max(0, r-60), max(0, g-60), max(0, b-60), 255)
    s    = size

    # Face circle
    draw.ellipse([6, 6, s-6, s-6], fill=(r, g, b, 255), outline=dark, width=4)

    eye_y  = s // 3
    es     = s // 11   # eye radius
    mouth_y = int(s * 0.62)

    def eyes(fill=dark, radius=es):
        draw.ellipse([s//4-radius, eye_y-radius, s//4+radius, eye_y+radius], fill=fill)
        draw.ellipse([3*s//4-radius, eye_y-radius, 3*s//4+radius, eye_y+radius], fill=fill)

    if emotion == "happy":
        eyes()
        draw.arc([s//4, mouth_y-s//10, 3*s//4, mouth_y+s//10], 0, 180, fill=dark, width=5)

    elif emotion == "sad":
        eyes()
        draw.arc([s//4, mouth_y, 3*s//4, mouth_y+s//8], 180, 360, fill=dark, width=5)
        # tears
        for tx in [s//4, 3*s//4]:
            draw.ellipse([tx-4, eye_y+es, tx+4, eye_y+es+20], fill=(100, 150, 255, 210))

    elif emotion == "angry":
        eyes()
        # angry brows
        draw.line([s//5, eye_y-es-6, s//3+2, eye_y-2], fill=dark, width=5)
        draw.line([4*s//5, eye_y-es-6, 2*s//3-2, eye_y-2], fill=dark, width=5)
        draw.arc([s//4, mouth_y, 3*s//4, mouth_y+s//8], 180, 360, fill=dark, width=5)

    elif emotion == "surprise":
        eyes(radius=int(es*1.6))
        # O-shaped mouth
        draw.ellipse([s//3, mouth_y-s//14, 2*s//3, mouth_y+s//9], fill=dark)

    elif emotion == "neutral":
        eyes()
        draw.line([s//4, mouth_y, 3*s//4, mouth_y], fill=dark, width=5)

    elif emotion == "fear":
        eyes(radius=int(es*1.5))
        # wavy mouth
        draw.arc([s//3, mouth_y-s//14, 2*s//3, mouth_y+s//9], 180, 360, fill=dark, width=4)
        # sweat drop
        draw.ellipse([3*s//4+4, eye_y, 3*s//4+14, eye_y+20], fill=(120, 180, 255, 220))

    elif emotion == "disgust":
        eyes()
        draw.line([s//5, eye_y-es-4, s//3, eye_y], fill=dark, width=4)
        draw.line([4*s//5, eye_y-es-4, 2*s//3, eye_y], fill=dark, width=4)
        draw.arc([s//4, mouth_y, 3*s//4, mouth_y+s//8], 180, 360, fill=dark, width=5)

    return img


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for emotion, color in EMOTIONS.items():
        img  = draw_face(emotion, color, SIZE)
        path = os.path.join(OUTPUT_DIR, f"{emotion}.png")
        img.save(path)
        print(f"  ✅  {path}")
    print(f"\nAll {len(EMOTIONS)} emojis saved to ./{OUTPUT_DIR}/")
    print("Tip: replace these with real PNGs from https://openmoji.org for best quality.")


if __name__ == "__main__":
    main()