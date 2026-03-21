#!/usr/bin/env python3
"""
caption_dataset_gemini.py

Re-captions the Lily training dataset using Gemini Flash.
Sends each image through Gemini with the Chroma-native captioning system instruction.
Overwrites existing .txt caption files.

Usage:
    python scripts/caption_dataset_gemini.py
    python scripts/caption_dataset_gemini.py --dry-run      # print captions, don't save
    python scripts/caption_dataset_gemini.py --start 10     # resume from image 10
"""

import os
import sys
import time
import argparse
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyB-6UubmYbXgbF-1yZC3dTIb2bPnlc1cP4")

MODEL = "gemini-2.5-flash"

DATASET_DIR = Path("/Users/markgiller/Desktop/Ace Girls Agency/Lily Harper/lily_v001_training/img")

# Delay between API calls to avoid rate limits (seconds)
REQUEST_DELAY = 2.0

# ── System Instruction ────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are a training data captioner for an image generation model.
Caption each image in natural language following this exact format:

An image of lily [what she is doing in one sentence]. [Any notable clothing, expression, or pose details in one sentence]. [Scene description: location, lighting, background in 1-2 sentences].

Rules:
- Natural language only, full sentences, no tags or commas as separators
- 60-130 words total
- Always describe lighting explicitly
- Describe everything visible
- Never use words like "illustrated", "rendered", "drawn" — she is a real person in a photograph
- Output ONLY the caption text, nothing else — no titles, no explanations"""

# ── Main ──────────────────────────────────────────────────────────────────────

def caption_image(client, image_path: Path) -> str:
    img = Image.open(image_path)
    response = client.models.generate_content(
        model=MODEL,
        contents=[img],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )
    return response.text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print captions without saving")
    parser.add_argument("--start", type=int, default=1, help="Start from image number (for resume)")
    args = parser.parse_args()

    # Init Gemini
    client = genai.Client(api_key=API_KEY)

    # Find all images
    images = sorted(DATASET_DIR.glob("*.png")) + sorted(DATASET_DIR.glob("*.jpg"))
    images = sorted(images)

    if not images:
        print(f"No images found in {DATASET_DIR}")
        sys.exit(1)

    print(f"Found {len(images)} images in {DATASET_DIR}")
    print(f"Model: {MODEL}")
    print(f"Dry run: {args.dry_run}")
    print(f"Starting from image #{args.start}")
    print("-" * 60)

    success = 0
    errors = 0

    for img_path in images:
        # Extract number from filename (01.png → 1)
        num = int(img_path.stem)
        if num < args.start:
            continue

        txt_path = img_path.with_suffix(".txt")

        print(f"[{num:02d}/{len(images)}] {img_path.name} → ", end="", flush=True)

        try:
            caption = caption_image(client, img_path)
            # Normalize trigger word capitalization
            caption = caption.replace("An image of Lily", "An image of lily")

            if args.dry_run:
                print(f"\n{caption}\n")
            else:
                txt_path.write_text(caption, encoding="utf-8")
                print(f"saved ({len(caption.split())} words)")
                success += 1

        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1

        time.sleep(REQUEST_DELAY)

    print("-" * 60)
    if not args.dry_run:
        print(f"Done. {success} saved, {errors} errors.")


if __name__ == "__main__":
    main()
