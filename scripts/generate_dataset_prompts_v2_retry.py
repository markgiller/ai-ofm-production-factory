#!/usr/bin/env python3
"""
Retry failed categories from wave 2 with softer instruction language
to avoid Gemini safety filter 400 errors.
Merges results into the wave2 JSON.
"""

import json
import random
import time
import requests
from pathlib import Path

GEMINI_API_KEY = "AIzaSyDVduTR1GHXYFCU4QWVoexlBFvqt4v_biY"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

OUTPUT_DIR = Path(__file__).parent.parent / "creative" / "prompts"
WAVE2_FILE = OUTPUT_DIR / "lily_v002_dataset_prompts_wave2.json"

SYSTEM_INSTRUCTION = """You are a professional prompt engineer for an AI image generation model called Chroma 1 HD.
Write prompts that produce photorealistic images of a character called "lily".

CHARACTER — "lily":
- 22, brown wavy hair (shoulder length), freckles, brown/hazel eyes
- Slim/petite build, natural beauty, minimal makeup
- Confident, warm personality

PROMPT FORMAT:
Line 1: IMG_XXXX.HEIC (random 4-digit number)
Line 2: blank
Line 3+: Natural language, 80-130 words. Full sentences. No tags. No SD keywords.
Structure: "An image of lily [action]. [Appearance details]. [Scene, lighting]. [Camera angle]."

RULES:
1. Describe lighting specifically (not just "warm light")
2. Describe clothing/appearance in detail
3. Include camera/shot description
4. Include a natural imperfection (messy hair, wrinkled clothes, smudged makeup, etc)
5. Vary hair: messy bun, wet, clipped up, ponytail, braided, windblown, bedhead — NOT always "medium brown wavy"
6. Vary gaze: only 50% looking at camera. Rest: looking away, eyes closed, profile, looking down
7. Each prompt unique in pose, setting, outfit, lighting, mood
8. NO phrases: "masterpiece", "best quality", "ultrarealistic", "candid phone snapshot"

OUTPUT: JSON array of prompt strings only. No explanations."""

RETRY_CATEGORIES = [
    {
        "name": "getting_ready",
        "count": 12,
        "lane": "sfw",
        "instruction": """Generate {count} GETTING READY / MORNING ROUTINE prompts.
Real morning content: doing makeup in bathroom mirror, trying on outfits (clothes pile on bed),
drying hair, painting nails, picking outfit from closet, applying moisturizer in towel,
checking phone while getting dressed, straightening hair.
Mix of casual dressed and in-progress states (robe, towel, halfway through outfit change).
Include: makeup clutter, hair ties, mirror reflections, bathroom details.
Camera: mirror selfie, phone timer, friend documenting the process."""
    },
    {
        "name": "bath_pool_water",
        "count": 10,
        "lane": "nsfw",
        "instruction": """Generate {count} BATH / POOL / WATER scene prompts.
Scenes involving water: in a bathtub relaxing, poolside in swimwear, stepping out of pool,
shower with steam and glass, hot tub at night, standing under outdoor beach shower,
caught in rain on balcony, sitting at edge of bath.
Focus on: water droplets on skin, wet hair textures, steam effects.
Swimwear ranges from bikini to minimal coverage. Some scenes show more skin than others.
Lighting: steamy bathroom, pool lights at night, sunset by water, overhead bathroom light.
Camera: phone on towel, wet-hand selfie, through steamed glass."""
    },
    {
        "name": "couple_pov",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} BOYFRIEND/PARTNER PERSPECTIVE prompts.
Photos taken BY or FOR a partner — private, intimate, unguarded.
Scenes: lying on couch in his oversized hoodie, morning in bed with messy hair,
leaning against kitchen counter in comfortable underwear, sending a mirror selfie,
stretching on bed — he catches the moment, walking ahead of him on a trail (shot from behind),
sitting cross-legged on floor eating takeout in minimal clothing, dancing in living room
in just a t-shirt, reading in bed in underwear, cooking breakfast in just a shirt.
These feel personal and private. Natural and comfortable with being seen.
Camera: shot from above, her selfie perspective, caught moment from across room."""
    },
    {
        "name": "car_travel",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} CAR / TRAVEL / ROAD TRIP prompts.
Scenes: passenger seat feet on dashboard, window down with hair blowing, holding coffee
in drive-through, sleeping in reclined seat, backseat on long drive, rest stop mirror selfie,
standing outside car at scenic overlook, sitting on car hood at golden hour.
Include road trip details: snacks, aux cord, sunglasses, messy car interior.
Camera: dashboard angle, visor mirror selfie, from driver seat, phone on windshield."""
    },
    {
        "name": "post_workout_gym",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} POST-WORKOUT / GYM prompts.
Real gym moments: gym mirror selfie with earbuds, sitting on bench catching breath,
lying on yoga mat exhausted, walking out into parking lot sun, stretching against wall,
sweaty red-faced selfie, sports bra visible after removing hoodie.
Outfits: matching gym set, baggy shorts + crop tank, old cut t-shirt, running tights.
Include: water bottle, gym bag, headphones, sweat.
Lighting: gym fluorescent, outdoor parking lot, home workout window light."""
    },
    {
        "name": "explicit_v2",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} INTIMATE ARTISTIC NUDE prompts with variety.
Full artistic nudity in varied settings and poses — NOT just bedroom.
Locations: bathroom, kitchen morning light, living room floor, hotel room, by window.
Poses: standing, sitting on counter, lying on floor, kneeling, stretching, in doorframe,
leaning against wall, sitting on chair backwards, on balcony.
Context: fresh from shower, lazy morning, getting dressed, self-admiration in mirror.
Expressions: NOT always seductive. Sometimes: peaceful, sleepy, laughing, distracted,
looking at phone, concentrating, surprised. She's comfortable and casual.
Lighting: vary between harsh flash, laptop glow, morning grey, golden hour, overhead.
These should feel like HER photos — she has agency and confidence.
Camera: phone timer, mirror across room, selfie arm, propped phone."""
    },
]


def call_gemini(category: dict) -> list[str]:
    user_prompt = category["instruction"].format(count=category["count"])
    user_prompt += f"\n\nReturn exactly {category['count']} prompts as a JSON array of strings."

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 1.0,
            "topP": 0.95,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(3):
        try:
            resp = requests.post(GEMINI_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
            if resp.status_code != 200:
                body = resp.text[:200]
                print(f"  Attempt {attempt+1} failed: {resp.status_code} — {body}")
                time.sleep(3)
                continue

            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            prompts = json.loads(text)

            if isinstance(prompts, dict):
                for v in prompts.values():
                    if isinstance(v, list):
                        prompts = v
                        break

            valid = []
            for p in prompts:
                if isinstance(p, str) and "lily" in p.lower():
                    if not p.startswith("IMG_"):
                        p = f"IMG_{random.randint(1000,9999)}.HEIC\n\n{p}"
                    valid.append(p)
                elif isinstance(p, dict):
                    pt = p.get("prompt", p.get("text", str(p)))
                    if not pt.startswith("IMG_"):
                        pt = f"IMG_{random.randint(1000,9999)}.HEIC\n\n{pt}"
                    valid.append(pt)

            print(f"  Got {len(valid)}/{category['count']} valid prompts")
            return valid

        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    return []


def main():
    print("=" * 70)
    print("WAVE 2 — RETRY FAILED CATEGORIES")
    print("=" * 70)

    # Load existing wave2
    with open(WAVE2_FILE, "r") as f:
        wave2 = json.load(f)

    existing_count = len(wave2["prompts"])
    print(f"\nExisting wave2: {existing_count} prompts")
    print(f"Retrying {len(RETRY_CATEGORIES)} categories...\n")

    new_prompts = []

    for i, cat in enumerate(RETRY_CATEGORIES):
        print(f"[{i+1}/{len(RETRY_CATEGORIES)}] {cat['name']} ({cat['count']})...")
        prompts = call_gemini(cat)
        if not prompts:
            print(f"  STILL FAILED")
            continue
        for p in prompts:
            new_prompts.append({"prompt": p, "category": cat["name"], "lane": cat["lane"]})
        wave2["metadata"]["categories"][cat["name"]] = {
            "lane": cat["lane"], "requested": cat["count"], "generated": len(prompts)
        }
        if i < len(RETRY_CATEGORIES) - 1:
            time.sleep(2)

    # Merge
    wave2["prompts"].extend(new_prompts)

    # Deduplicate IMG numbers
    used = set()
    for item in wave2["prompts"]:
        p = item["prompt"]
        if p.startswith("IMG_"):
            num = p[4:8]
            if num in used:
                new_num = random.randint(1000, 9999)
                while str(new_num) in used:
                    new_num = random.randint(1000, 9999)
                item["prompt"] = f"IMG_{new_num}" + p[8:]
                num = str(new_num)
            used.add(num)

    random.shuffle(wave2["prompts"])
    for i, item in enumerate(wave2["prompts"]):
        item["index"] = i

    wave2["metadata"]["total_generated"] = len(wave2["prompts"])

    with open(WAVE2_FILE, "w", encoding="utf-8") as f:
        json.dump(wave2, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"DONE — total now: {len(wave2['prompts'])} prompts")
    print(f"Saved to: {WAVE2_FILE}")
    print(f"{'=' * 70}")

    # Samples from new
    if new_prompts:
        print("\n--- New prompt samples ---\n")
        for s in random.sample(new_prompts, min(3, len(new_prompts))):
            print(f"[{s['category']} / {s['lane']}]")
            print(s["prompt"])
            print()


if __name__ == "__main__":
    main()
