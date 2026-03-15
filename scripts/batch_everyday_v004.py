#!/usr/bin/env python3
"""
Batch generate ~300 everyday lifestyle photos using LoRA v004 (step 660 best).
Diverse scenes, natural/imperfect lighting, authentic feel.

Usage:
    python scripts/batch_everyday_v004.py \
        --comfyui-url https://<pod-id>-8188.proxy.runpod.net \
        --count-per-prompt 6
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from run_explore import run_explore
from pathlib import Path
import random

# ── Everyday prompts — natural, imperfect, authentic ──────────────────────

EVERYDAY_PROMPTS = [
    # Morning / Home
    "a photo of chara, young woman just woke up, messy bed hair, oversized t-shirt, sitting in bed with phone, soft morning light from window, sleepy expression, no makeup, cozy bedroom",
    "a photo of chara, young woman brushing teeth in bathroom mirror, wearing pajamas, messy hair, harsh bathroom lighting, candid morning routine",
    "a photo of chara, young woman making coffee in small kitchen, wearing oversized hoodie and shorts, morning sunlight, slightly messy counter, yawning",
    "a photo of chara, young woman eating cereal at kitchen table, hair in messy bun, wearing glasses, morning light, scrolling phone, casual",

    # University / Study
    "a photo of chara, young woman studying at library desk, books and laptop open, wearing reading glasses and cardigan, focused expression, warm indoor lighting",
    "a photo of chara, young woman sitting in lecture hall, notebook open, pen in hand, wearing casual sweater, fluorescent lighting, candid",
    "a photo of chara, young woman studying in bed with laptop, blanket over legs, messy notes around her, warm lamp light, tired but focused",
    "a photo of chara, young woman walking through university campus, backpack on one shoulder, autumn leaves, natural daylight, candid walking shot",

    # Cafe / Coffee
    "a photo of chara, young woman working as barista behind counter, black apron, hair tied back, steam from coffee machine, warm cafe lighting",
    "a photo of chara, young woman sitting alone in cafe with latte, looking out rainy window, cream sweater, contemplative mood, soft overcast light",
    "a photo of chara, young woman laughing at cafe table, holding coffee cup with both hands, messy hair, natural daylight from window, candid moment",
    "a photo of chara, young woman reading book in corner of cozy cafe, legs curled up on chair, wearing jeans and knit sweater, warm ambient lighting",

    # Walking / Outdoors
    "a photo of chara, young woman walking on rainy street with umbrella, denim jacket, wet pavement reflections, overcast grey sky, candid street photo",
    "a photo of chara, young woman sitting on park bench, autumn park, wearing scarf and coat, leaves on ground, soft golden hour light, peaceful expression",
    "a photo of chara, young woman walking dog in neighborhood, leash in hand, wearing athletic wear, morning light, candid walking shot",
    "a photo of chara, young woman waiting at bus stop, headphones around neck, backpack, looking at phone, overcast day, urban background",
    "a photo of chara, young woman riding bicycle on residential street, hair blowing, casual outfit, sunny day, motion blur background, happy expression",

    # Social / Friends
    "a photo of chara, young woman taking mirror selfie in bedroom, phone covering part of face, messy room background, wearing jeans and crop top, warm lighting",
    "a photo of chara, young woman at house party, holding red cup, slightly flushed cheeks, dim warm lighting, laughing, casual outfit",
    "a photo of chara, young woman sitting on floor with pizza box, watching tv, wearing sweatpants and tank top, dim room with screen glow, cozy night in",
    "a photo of chara, young woman at picnic in park, sitting on blanket, sundress, sunglasses pushed up, dappled shade under tree, natural light",

    # Cooking / Domestic
    "a photo of chara, young woman chopping vegetables in kitchen, wearing apron over casual clothes, messy counter, warm kitchen lighting, focused on cutting board",
    "a photo of chara, young woman tasting food from wooden spoon, standing at stove, steam rising from pot, kitchen background, playful expression",
    "a photo of chara, young woman doing laundry, holding basket of clothes, wearing simple tee and shorts, laundry room, fluorescent light, everyday task",

    # Fitness / Active
    "a photo of chara, young woman stretching on yoga mat in living room, wearing leggings and sports bra, morning light from window, home workout",
    "a photo of chara, young woman jogging on sidewalk, earbuds in, ponytail, light sweat, wearing running shorts and tank top, early morning light",
    "a photo of chara, young woman sitting on gym floor after workout, water bottle, sweaty, tired smile, fluorescent gym lighting, candid",
    "a photo of chara, young woman walking home from gym with gym bag, wearing hoodie and leggings, evening light, residential street, relaxed",

    # Evening / Night
    "a photo of chara, young woman watching movie on laptop in bed, face lit by screen glow, wearing oversized shirt, blankets, dark room, cozy",
    "a photo of chara, young woman on video call on laptop, waving at screen, wearing casual top, desk lamp lighting, evening at home",
    "a photo of chara, young woman journaling on couch with tea, wearing cozy socks and sweater, warm lamp light, blanket, peaceful evening",
    "a photo of chara, young woman getting ready to go out, doing makeup in mirror, bathroom lighting, wearing robe, half-ready candid",

    # Seasonal / Weather
    "a photo of chara, young woman in heavy rain without umbrella, wet hair plastered to face, laughing, denim jacket soaked, grey sky, spontaneous",
    "a photo of chara, young woman building snowman in park, wearing puffer jacket and beanie, red cheeks and nose, snowy background, playful",
    "a photo of chara, young woman at beach in oversized shirt over swimsuit, wind in hair, cloudy beach day, barefoot on sand, natural light",
    "a photo of chara, young woman sitting on windowsill watching rain, knees pulled up, wearing sweater, cup of tea, moody grey light, reflective",

    # Shopping / Errands
    "a photo of chara, young woman at grocery store with basket, reaching for item on shelf, casual outfit, supermarket fluorescent lighting, everyday errand",
    "a photo of chara, young woman trying on sunglasses at street market, laughing, summer dress, bright outdoor light, fun candid moment",
    "a photo of chara, young woman carrying shopping bags on city street, wearing casual outfit, walking shot, natural daylight, urban background",

    # Travel / Adventure
    "a photo of chara, young woman on train looking out window, reflection in glass, wearing headphones, countryside passing by, soft natural light",
    "a photo of chara, young woman at airport with backpack, tired, holding boarding pass, airport terminal lighting, travel candid",
    "a photo of chara, young woman exploring old european town, cobblestone street, wearing casual summer outfit, golden hour, tourist candid",

    # Relaxing / Lazy Day
    "a photo of chara, young woman lying on couch scrolling phone, wearing oversized hoodie, legs up, messy living room, afternoon light, lazy day",
    "a photo of chara, young woman taking bath, only shoulders and face visible above bubbles, candles on edge, warm soft lighting, relaxed expression",
    "a photo of chara, young woman napping on couch with book on chest, afternoon sun patch, blanket half off, peaceful sleeping face",

    # Work / Professional (casual)
    "a photo of chara, young woman at desk with laptop, glasses on, hair in ponytail, office casual outfit, desk clutter, natural window light",
    "a photo of chara, young woman presenting at whiteboard, casual blazer, nervous smile, office meeting room, fluorescent lighting",
    "a photo of chara, young woman on lunch break sitting outside office building, eating sandwich, casual work outfit, midday sun",
]

LORA_NAME = "lora_chara_v004_best.safetensors"
LORA_STRENGTH = 1.0
FORMAT = "4:5"
OUTPUT_DIR = Path("./explore_output/batch_everyday_v004")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch everyday photos with LoRA v004")
    parser.add_argument("--comfyui-url", type=str, required=True)
    parser.add_argument("--count-per-prompt", type=int, default=6,
                        help="Seeds per prompt (default: 6, total = prompts x count)")
    parser.add_argument("--lora-strength", type=float, default=0.8)
    parser.add_argument("--start-prompt", type=int, default=0,
                        help="Skip first N prompts (for resuming)")
    args = parser.parse_args()

    prompts = EVERYDAY_PROMPTS[args.start_prompt:]
    total = len(prompts) * args.count_per_prompt
    print(f"[batch] {len(prompts)} prompts x {args.count_per_prompt} seeds = {total} images")
    print(f"[batch] LoRA: {LORA_NAME} @ {args.lora_strength}")
    print(f"[batch] Output: {OUTPUT_DIR}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, prompt in enumerate(prompts):
        prompt_idx = i + args.start_prompt
        seed_start = random.randint(100000, 999999)
        short = prompt[20:70].replace(",", "").strip()
        print(f"\n{'='*60}")
        print(f"[batch] Prompt {prompt_idx+1}/{len(EVERYDAY_PROMPTS)}: {short}...")
        print(f"{'='*60}")

        try:
            run_explore(
                prompt=prompt,
                count=args.count_per_prompt,
                fmt=FORMAT,
                seed_start=seed_start,
                base_url=args.comfyui_url.rstrip("/"),
                output_dir=OUTPUT_DIR,
                lora=LORA_NAME,
                lora_strength=args.lora_strength,
            )
        except KeyboardInterrupt:
            print(f"\n[batch] Stopped at prompt {prompt_idx+1}. Resume with --start-prompt {prompt_idx}")
            sys.exit(0)
        except Exception as e:
            print(f"[batch] ERROR on prompt {prompt_idx+1}: {e}")
            continue

    print(f"\n[batch] DONE. All images in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
