#!/usr/bin/env python3
"""
Prepare lily_v001 dataset for LoRA training on FLUX.1 Dev.

What this script does:
1. Writes individual captions (.txt) for each of the 36 images
2. Converts JPG → PNG and resizes (longest side = 1024)
3. Creates dataset.toml for musubi-tuner
4. Validates the dataset

Usage (on Mac, before uploading to pod):
    python scripts/prepare_lily_v001.py

Output: ~/Desktop/lily_v001_training/ (ready to upload via runpodctl)
"""

import os
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────

SOURCE_DIR = Path.home() / "Desktop" / "lily_dataset"
OUTPUT_DIR = Path.home() / "Desktop" / "lily_v001_training"
IMG_DIR = OUTPUT_DIR / "img"
MAX_RESOLUTION = 1024
TRIGGER = "lily"

# ── Captions ────────────────────────────────────────────────────────────────
# Rules: trigger word first, describe ONLY clothing/pose/scene/lighting/action.
# Do NOT describe face or hair features — let LoRA learn from pixels.

CAPTIONS = {
    "lily_1": f"{TRIGGER}, a young woman wearing a grey university crewneck sweatshirt, sitting at a wooden table in a cafe, holding a coffee cup, window light from the left, smiling at camera",
    "lily_2": f"{TRIGGER}, a young woman, bare shoulders, extreme close-up headshot, facing camera directly, neutral expression, white background, flat even lighting",
    "lily_3": f"{TRIGGER}, a young woman, close-up headshot, slight smile, bare shoulders, white background, soft natural lighting",
    "lily_4": f"{TRIGGER}, a young woman wearing a grey crewneck t-shirt, laughing with a big open smile, head and shoulders portrait, white background, even studio lighting",
    "lily_5": f"{TRIGGER}, a young woman, close-up three-quarter view portrait, bare shoulders, neutral expression, white background, soft natural lighting",
    "lily_6": f"{TRIGGER}, a young woman wearing a grey crewneck t-shirt, head and shoulders portrait, neutral expression, looking directly at camera, grey background, soft studio lighting",
    "lily_7": f"{TRIGGER}, a young woman, extreme close-up three-quarter view, bare shoulders, subtle smile, white background, soft natural lighting",
    "lily_8": f"{TRIGGER}, a young woman, close-up headshot, facing camera directly, neutral expression, bare shoulders, white background, flat even lighting",
    "lily_9": f"{TRIGGER}, a young woman, close-up headshot, eyes looking down with a soft amused expression, bare shoulders, white background, natural lighting",
    "lily_10": f"{TRIGGER}, a young woman, close-up three-quarter view, looking to the side, bare shoulders, contemplative expression, white background, natural lighting",
    "lily_11": f"{TRIGGER}, a young woman wearing a grey crewneck t-shirt, head and shoulders portrait, wide natural smile, white background, bright even lighting",
    "lily_12": f"{TRIGGER}, a young woman wearing a light grey hoodie, sitting on a couch reading a book, looking down at the pages, bookshelf in background, warm indoor lighting",
    "lily_13": f"{TRIGGER}, a young woman wearing an olive green field jacket over a brown t-shirt and jeans, walking on a city sidewalk, carrying a brown leather bag, golden hour sunlight, pedestrians in background",
    "lily_14": f"{TRIGGER}, a young woman wearing a light blue floral sundress, sitting on a wooden park bench, dappled sunlight through trees, green foliage in background, slight smile",
    "lily_15": f"{TRIGGER}, a young woman wearing a denim jacket over a white t-shirt and jeans, sitting against a red brick wall, soft overcast lighting, slight smile",
    "lily_16": f"{TRIGGER}, a young woman wearing round tortoiseshell glasses and a beige knit cardigan, sitting at a desk working on a laptop, desk lamp and notebook nearby, warm interior evening lighting, bookshelf in background",
    "lily_17": f"{TRIGGER}, a young woman wearing a white linen tank top, standing in a greenhouse surrounded by tropical plants and flowers, natural sunlight filtering through glass roof, looking to the side",
    "lily_18": f"{TRIGGER}, a young woman wearing a grey tank top, lying on a bed with linen pillows, selfie angle from above, soft warm morning light, relaxed expression",
    "lily_19": f"{TRIGGER}, a young woman wearing a floral print camisole top, selfie on a beach at sunset, ocean and sand in background, golden warm light, windswept hair, smiling",
    "lily_20": f"{TRIGGER}, a young woman wearing a green sports crop top and black leggings, standing in a park holding a rolled yoga mat, golden hour backlight, grass and trees in background",
    "lily_21": f"{TRIGGER}, a young woman wearing a knit beige scarf and dark sweater, close-up portrait outdoors at dusk, city lights bokeh in background, cool blue evening light, contemplative expression",
    "lily_22": f"{TRIGGER}, a young woman wearing a blue and white striped linen button-up shirt, browsing vegetables at an outdoor farmers market, looking down at tomatoes, bright natural daylight",
    "lily_23": f"{TRIGGER}, a young woman wearing a grey oversized t-shirt and blue jeans with white sneakers, sitting on stone steps outdoors, arms resting on knees, golden hour warm light, greenery in background",
    "lily_24": f"{TRIGGER}, a young woman wearing a dark grey denim jacket over a white t-shirt and jeans, standing on a city sidewalk, brick buildings in background, overcast daylight, slight smile",
    "lily_25": f"{TRIGGER}, a young woman wearing a green and red plaid flannel shirt, three-quarter portrait in a forest, green trees and foliage in background, dappled natural light, looking over shoulder",
    "lily_26": f"{TRIGGER}, a young woman wearing a floral print tank top, close-up portrait in a wildflower meadow, colorful flowers in background, bright summer sunlight, wide natural smile",
    "lily_27": f"{TRIGGER}, a young woman wearing a cream chunky knit sweater, sitting by a window holding a ceramic mug, rain drops on window glass, looking out pensively, soft grey natural light",
    "lily_28": f"{TRIGGER}, a young woman wearing a khaki t-shirt, lying on a beige sofa wrapped in a cream knit blanket, sleepy relaxed expression, warm lamp light, bookshelf and plant in background",
    "lily_29": f"{TRIGGER}, a young woman wearing a dark grey athletic t-shirt and black leggings, jogging on a park path, hair in ponytail, trees and dappled sunlight, mid-stride action",
    "lily_30": f"{TRIGGER}, a young woman wearing a dark denim jacket over a striped t-shirt with a canvas backpack, walking on a university campus, overcast rainy day, wet pavement, students in background",
    "lily_31": f"{TRIGGER}, a young woman wearing a cream silk blouse, sitting on a rooftop terrace at dusk, string lights and city skyline in background, warm golden light, slight smile, looking at camera",
    "lily_32": f"{TRIGGER}, a young woman wearing a cream cable-knit sweater, studying at a library table with open books, looking down at text, holding a pen, fluorescent overhead and window light",
    "lily_33": f"{TRIGGER}, a young woman wearing a beige linen long-sleeve top with sunglasses on her head, sitting at an outdoor cafe terrace, wicker chairs in background, warm afternoon light, slight smile",
    "lily_34": f"{TRIGGER}, a young woman wearing a dark grey t-shirt, standing in a kitchen cracking an egg into a bowl, morning sunlight through window, looking at camera with slight smile",
    "lily_35": f"{TRIGGER}, a young woman, extreme close-up headshot, eyes closed, peaceful smile, bare shoulders, white background, soft natural lighting",
    "lily_36": f"{TRIGGER}, a young woman wearing a dark navy t-shirt, head and shoulders portrait, neutral expression facing camera directly, white background, flat even lighting",
}


# ── Functions ───────────────────────────────────────────────────────────────

def resize_image(img: Image.Image, max_res: int) -> Image.Image:
    """Resize so longest side = max_res, preserve aspect ratio."""
    w, h = img.size
    if max(w, h) <= max_res:
        return img
    scale = max_res / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def create_dataset_toml(img_dir: Path, output_path: Path):
    """Create musubi-tuner dataset.toml for FLUX.1 Dev training."""
    # Pod path — will be adjusted when uploaded
    pod_img_dir = "/workspace/lora_training/lily_v001/img"
    content = f"""[general]
resolution = [1024, 1024]
caption_extension = ".txt"
enable_bucket = true
bucket_no_upscale = true

[[datasets]]
batch_size = 1
image_directory = "{pod_img_dir}"
"""
    output_path.write_text(content)
    print(f"  dataset.toml written to {output_path}")


def main():
    print(f"[prepare] Source: {SOURCE_DIR}")
    print(f"[prepare] Output: {OUTPUT_DIR}")
    print()

    # Validate source
    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

    # Create output dirs
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "output").mkdir(parents=True, exist_ok=True)

    # Process each image
    processed = 0
    for key in sorted(CAPTIONS.keys(), key=lambda x: int(x.split("_")[1])):
        idx = int(key.split("_")[1])
        src = SOURCE_DIR / f"{key}.jpg"

        if not src.exists():
            print(f"  WARNING: {src} not found, skipping")
            continue

        # Load, convert, resize
        with Image.open(src) as img:
            img = img.convert("RGB")
            original_size = img.size
            img = resize_image(img, MAX_RESOLUTION)

            # Save as PNG
            out_name = f"{idx:02d}"
            out_img = IMG_DIR / f"{out_name}.png"
            img.save(out_img, "PNG")

            # Write caption
            caption = CAPTIONS[key]
            (IMG_DIR / f"{out_name}.txt").write_text(caption)

            print(f"  [{idx:2d}/36] {src.name} -> {out_name}.png  {original_size[0]}x{original_size[1]} -> {img.size[0]}x{img.size[1]}  |  {caption[:60]}...")
            processed += 1

    # Create dataset.toml
    print()
    create_dataset_toml(IMG_DIR, OUTPUT_DIR / "dataset.toml")

    # Summary
    print(f"\n{'='*60}")
    print(f"[prepare] Dataset ready: {processed} images + captions")
    print(f"[prepare] Output: {OUTPUT_DIR}")
    print(f"[prepare] Trigger word: {TRIGGER}")
    print(f"[prepare] Resolution: max {MAX_RESOLUTION}px (bucketed)")

    # Validate
    pngs = list(IMG_DIR.glob("*.png"))
    txts = list(IMG_DIR.glob("*.txt"))
    print(f"[prepare] PNG files: {len(pngs)}")
    print(f"[prepare] TXT files: {len(txts)}")
    if len(pngs) != len(txts):
        print(f"  WARNING: PNG/TXT count mismatch!")
    else:
        print(f"  OK: counts match")

    # Dataset composition analysis
    close_ups = [k for k in CAPTIONS if any(x in CAPTIONS[k] for x in ["close-up", "headshot", "head and shoulders"])]
    lifestyle = [k for k in CAPTIONS if k not in close_ups]
    print(f"\n[prepare] Composition:")
    print(f"  Close-up/portrait: {len(close_ups)} ({len(close_ups)/len(CAPTIONS)*100:.0f}%)")
    print(f"  Lifestyle/scene:   {len(lifestyle)} ({len(lifestyle)/len(CAPTIONS)*100:.0f}%)")

    print(f"\n[prepare] Next step: upload to pod")
    print(f"  cd ~/Desktop && runpodctl send lily_v001_training/")


if __name__ == "__main__":
    main()
