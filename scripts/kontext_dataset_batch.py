#!/usr/bin/env python3
"""
Generate LoRA training dataset using FLUX.1 Kontext Dev.

Takes a single reference face image and generates 40 diverse variations
preserving character identity through Kontext's native token architecture.
No IP-Adapter, no PuLID — Kontext sees the reference as context tokens.

Dataset composition:
  - 15 headshots on white background (angles, expressions)
  - 25 lifestyle shots (scenes, outfits, lighting)

Usage:
    # Full batch (40 images):
    python3 scripts/kontext_dataset_batch.py

    # Test single image first:
    python3 scripts/kontext_dataset_batch.py --test

    # Custom reference:
    python3 scripts/kontext_dataset_batch.py --ref my_face.png

Prerequisites:
    - ComfyUI v0.16+ running on localhost:8188
    - flux1-dev-kontext_fp8_scaled.safetensors in models/diffusion_models/
    - reference.png in ComfyUI input folder (/workspace/input/)
"""

import json
import urllib.request
import time
import sys
import argparse

BASE_URL = "http://localhost:8188"

# ═══════════════════════════════════════════════════════════════════════════════
# Part 1: HEADSHOTS — white bg, angles & expressions (15)
# Teach the model WHAT the character looks like from every angle
# ═══════════════════════════════════════════════════════════════════════════════

HEADSHOTS = [
    # Direct angles — turntable style
    ("hs_front", 0.75,
     "The woman standing on a clean white studio background, looking directly at camera, "
     "neutral expression, mouth closed, hands at sides, upper body portrait photograph, "
     "natural skin texture, visible pores, subtle skin imperfections, shot on Canon EOS R5 85mm f/1.4"),

    ("hs_left45", 0.75,
     "The woman has turned 45 degrees to the left, white studio background, neutral expression, "
     "upper body portrait, natural skin texture, visible pores, shot on Canon EOS R5"),

    ("hs_right45", 0.75,
     "The woman has turned 45 degrees to the right, white studio background, neutral expression, "
     "upper body portrait, natural skin texture, visible pores"),

    ("hs_34left", 0.75,
     "The woman in 3/4 view from the left, white studio background, calm natural expression, "
     "portrait photograph, natural skin, shot on Sony A7IV 85mm"),

    ("hs_34right", 0.75,
     "The woman in 3/4 view from the right, white studio background, natural relaxed expression, "
     "portrait photograph, visible skin texture"),

    ("hs_over_shoulder", 0.75,
     "The woman looking over her left shoulder toward camera, back partially visible, "
     "white studio background, natural expression, portrait, shot on Canon EOS R5"),

    # Expressions
    ("hs_smile", 0.75,
     "The woman smiling warmly with teeth showing, eyes slightly squinted naturally, "
     "white studio background, close-up portrait, natural skin texture, visible pores"),

    ("hs_laugh", 0.75,
     "The woman laughing naturally with mouth open, genuine candid laugh, "
     "white studio background, upper body, natural skin texture, subtle skin imperfections"),

    ("hs_serious", 0.75,
     "The woman with serious focused expression, intense eye contact with camera, "
     "white studio background, extreme close-up of face, natural pores visible, raw"),

    ("hs_frown", 0.75,
     "The woman frowning slightly, subtle forehead creasing, white studio background, "
     "close-up portrait, natural skin, visible texture"),

    ("hs_eyes_closed", 0.75,
     "The woman has closed her eyes, peaceful relaxed expression, slight serene smile, "
     "white studio background, close-up portrait, natural skin"),

    # Angle + expression combos
    ("hs_lookup_smile", 0.75,
     "The woman looking up slightly, white studio background, soft natural smile, "
     "portrait photograph, natural skin texture, subtle imperfections, shot on Sony A7IV"),

    ("hs_tilt_left", 0.75,
     "The woman tilting her head to the left, white studio background, slight playful smile, "
     "close-up portrait, natural skin, visible pores"),

    ("hs_below_angle", 0.75,
     "The woman photographed from slightly below looking up at her, white studio background, "
     "confident expression, portrait, natural skin, shot on Canon EOS R5"),

    ("hs_above_angle", 0.75,
     "The woman photographed from slightly above, she looks up at camera, white studio background, "
     "natural expression, close-up, natural skin texture, visible pores"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Part 2: LIFESTYLE — scenes, outfits, lighting (25)
# Teach the model the character IN CONTEXT — varied but identity locked
# ═══════════════════════════════════════════════════════════════════════════════

LIFESTYLE = [
    # ── Indoor casual ──
    ("lf_cafe", 0.90,
     "The same woman sitting at a cafe table, wearing a cream knit sweater, holding a coffee cup, "
     "warm indoor lighting, candid medium shot, natural skin texture, visible pores, "
     "shot on Canon EOS R5 85mm f/1.8, shallow depth of field"),

    ("lf_restaurant", 0.90,
     "The same woman at a restaurant, wearing a simple black top with thin straps, "
     "warm evening candlelight, slight smile, close-up portrait, natural skin, "
     "shot on Sony A7IV 50mm f/1.4"),

    ("lf_couch", 0.90,
     "The same woman on a couch in a cozy living room, wearing gray loungewear, "
     "soft indoor lamp light, relaxed, looking at camera, natural, medium shot, "
     "shot on Fujifilm X-T5"),

    ("lf_kitchen", 0.90,
     "The same woman in a bright kitchen cooking, wearing a casual striped shirt, "
     "natural window light from the side, candid, medium shot, natural skin texture, "
     "shot on Canon EOS R5 35mm"),

    ("lf_desk", 0.90,
     "The same woman at a desk with laptop, wearing a business casual white blouse, "
     "office with natural window light, focused expression, medium shot, natural, "
     "shot on Sony A7IV"),

    # ── Outdoor urban ──
    ("lf_street", 0.90,
     "The same woman on a city street, wearing a white t-shirt and blue jeans, "
     "natural daylight, urban background slightly blurred, medium shot, candid, "
     "natural skin, shot on Sony A7IV 50mm f/1.4"),

    ("lf_brick_wall", 0.90,
     "The same woman leaning against a brick wall, wearing a black leather jacket over white tee, "
     "overcast outdoor light, 3/4 portrait, moody, natural skin texture, "
     "shot on Canon EOS R5 85mm f/1.8"),

    ("lf_sidewalk", 0.90,
     "The same woman walking on a sidewalk, wearing a summer floral dress and white sneakers, "
     "bright sunny day, medium shot, candid, natural, shot on Fujifilm X-T5 56mm"),

    ("lf_steps", 0.90,
     "The same woman sitting on stone steps outdoors, wearing ripped jeans and a tank top, "
     "golden hour warm light, relaxed pose, medium shot, natural skin, "
     "shot on Sony A7IV 85mm f/1.4"),

    ("lf_bicycle", 0.90,
     "The same woman on a bicycle in a city park, wearing casual athletic clothes, "
     "sunny day, medium shot, candid, natural, shot on Canon EOS R5 35mm"),

    # ── Outdoor nature ──
    ("lf_beach", 0.90,
     "The same woman at a beach, wearing a loose white linen top, sunset golden light, "
     "wind in hair, 3/4 portrait, natural skin, warm tones, "
     "shot on Canon EOS R5 85mm f/1.4"),

    ("lf_garden", 0.90,
     "The same woman in a garden surrounded by flowers, wearing a floral sundress, "
     "dappled sunlight through trees, candid, natural skin, medium shot, "
     "shot on Fujifilm X-T5"),

    ("lf_park_grass", 0.90,
     "The same woman sitting on green grass in a park, wearing a simple white tee and denim shorts, "
     "golden hour, relaxed, looking at camera, natural, medium shot, "
     "shot on Sony A7IV 50mm"),

    ("lf_lake", 0.90,
     "The same woman standing at a lake shore, wearing a casual denim jacket, "
     "overcast dramatic sky, 3/4 portrait, moody natural light, natural skin, "
     "shot on Nikon Z8 85mm"),

    ("lf_hike", 0.90,
     "The same woman hiking on a forest trail, wearing athletic wear, "
     "bright natural outdoor light, candid, slightly sweaty natural glow, medium shot, "
     "shot on iPhone 15 Pro"),

    # ── Styled / fashion ──
    ("lf_rooftop", 0.90,
     "The same woman at a rooftop bar, wearing an elegant black dress, city skyline behind, "
     "blue hour evening light, close-up portrait, glamorous, natural makeup, natural skin, "
     "shot on Canon EOS R5 85mm f/1.4"),

    ("lf_gallery", 0.90,
     "The same woman at an art gallery, wearing a smart navy blazer and trousers, "
     "clean white gallery walls, professional, 3/4 portrait, natural lighting, natural skin, "
     "shot on Leica Q2"),

    ("lf_mirror_selfie", 0.90,
     "The same woman taking a mirror selfie in a bathroom, wearing simple cotton pajamas, "
     "soft warm bathroom light, natural morning look, candid, phone visible in hand"),

    ("lf_pool", 0.90,
     "The same woman at a pool edge, wearing a black bikini, bright sunny day, "
     "natural tan skin, wet hair, candid medium shot, summer vibes, "
     "shot on iPhone 15 Pro"),

    ("lf_morning_bed", 0.90,
     "The same woman in bed with white sheets, wearing a simple white tank top, "
     "soft morning light through sheer curtains, just woke up, close-up, natural, no makeup, "
     "shot on Canon EOS R5 50mm f/1.2"),

    # ── Night / dramatic lighting ──
    ("lf_rain_night", 0.90,
     "The same woman walking on a rainy city street at night, wearing a beige trench coat, "
     "wet pavement reflections, neon signs in background, moody cinematic, 3/4 portrait, "
     "natural skin, shot on Sony A7IV 35mm"),

    ("lf_car_night", 0.90,
     "The same woman sitting in a car at night, illuminated by soft dashboard lights and passing streetlights, "
     "wearing a hoodie, looking out window, contemplative, candid, natural"),

    ("lf_bonfire", 0.90,
     "The same woman at a bonfire on a beach, warm orange firelight illuminating her face, "
     "wearing a cozy knit sweater, night, close-up portrait, natural skin, "
     "shot on Sony A7IV 85mm f/1.8"),

    ("lf_golden_sunset", 0.90,
     "The same woman at golden hour sunset, wearing a flowing maxi dress, "
     "dramatic warm backlight, hair glowing, 3/4 portrait, stunning natural light, "
     "shot on Canon EOS R5 85mm f/1.4"),

    ("lf_train_window", 0.90,
     "The same woman sitting by a train window, wearing a wool coat and scarf, "
     "soft diffused window light, looking outside, contemplative, candid, natural skin, "
     "shot on Fujifilm X-T5"),
]

ALL_PROMPTS = HEADSHOTS + LIFESTYLE
SEEDS = list(range(7000, 7000 + len(ALL_PROMPTS)))


# ═══════════════════════════════════════════════════════════════════════════════
# ComfyUI API helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_node_info(node_name):
    """Query ComfyUI for a node's input specification."""
    url = f"{BASE_URL}/object_info/{node_name}"
    try:
        data = json.loads(urllib.request.urlopen(url).read())
        return data.get(node_name, {})
    except Exception as e:
        print(f"  WARNING: Could not query {node_name}: {e}")
        return None


def preflight_check():
    """Verify all required nodes exist and print their input specs."""
    print("\n[preflight] Checking Kontext node APIs...\n")

    critical_nodes = [
        "FluxKontextImageScale",
        "KSampler",
        "UNETLoader",
        "VAEEncode",
    ]

    all_ok = True
    node_specs = {}

    for name in critical_nodes:
        info = get_node_info(name)
        if info is None:
            print(f"  MISSING: {name}")
            all_ok = False
            continue

        inputs = info.get("input", {})
        required = inputs.get("required", {})
        optional = inputs.get("optional", {})
        node_specs[name] = {"required": required, "optional": optional}

        print(f"  {name}:")
        print(f"    required: {list(required.keys())}")
        if optional:
            print(f"    optional: {list(optional.keys())}")

    if not all_ok:
        print("\n  ERROR: Missing nodes. Update ComfyUI or install required nodes.")
        sys.exit(1)

    return node_specs


def build_workflow(prompt_text, seed, denoise, prefix, ref_image, node_specs):
    """Build Kontext img2img editing workflow.

    Kontext encodes the input image as context tokens concatenated
    to output tokens — identity is preserved through architecture,
    not through external injection like IP-Adapter/PuLID.
    """
    # Determine FluxKontextImageScale params from preflight
    scale_node_params = {"image": ["4", 0]}
    scale_spec = node_specs.get("FluxKontextImageScale", {})
    scale_required = scale_spec.get("required", {})

    # Add width/height/megapixels based on what the node accepts
    if "width" in scale_required:
        scale_node_params["width"] = 1024
    if "height" in scale_required:
        scale_node_params["height"] = 1024
    if "megapixels" in scale_required:
        scale_node_params["megapixels"] = 1.0

    workflow = {
        # ── Model loaders ──
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "flux1-dev-kontext_fp8_scaled.safetensors",
            "weight_dtype": "default",
        }},
        "2": {"class_type": "DualCLIPLoader", "inputs": {
            "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
            "clip_name2": "clip_l.safetensors",
            "type": "flux",
        }},
        "3": {"class_type": "VAELoader", "inputs": {
            "vae_name": "ae.safetensors",
        }},

        # ── Reference image → scale → encode to latent ──
        "4": {"class_type": "LoadImage", "inputs": {
            "image": ref_image,
        }},
        "5": {"class_type": "FluxKontextImageScale", "inputs": scale_node_params},
        "6": {"class_type": "VAEEncode", "inputs": {
            "pixels": ["5", 0],
            "vae": ["3", 0],
        }},

        # ── Text conditioning ──
        "7": {"class_type": "CLIPTextEncode", "inputs": {
            "text": prompt_text,
            "clip": ["2", 0],
        }},
        "8": {"class_type": "CLIPTextEncode", "inputs": {
            "text": "",
            "clip": ["2", 0],
        }},

        # ── Sample (img2img with Kontext) ──
        "9": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0],
            "positive": ["7", 0],
            "negative": ["8", 0],
            "latent_image": ["6", 0],
            "seed": seed,
            "steps": 28,
            "cfg": 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": denoise,
        }},

        # ── Decode + save ──
        "10": {"class_type": "VAEDecode", "inputs": {
            "samples": ["9", 0],
            "vae": ["3", 0],
        }},
        "11": {"class_type": "SaveImage", "inputs": {
            "images": ["10", 0],
            "filename_prefix": f"dataset_{prefix}",
        }},
    }

    return workflow


def queue_job(workflow):
    """Submit workflow to ComfyUI queue and return prompt_id."""
    data = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        BASE_URL + "/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP ERROR {e.code}: {body[:500]}")
        raise
    return resp["prompt_id"]


def wait_for_jobs(jobs, total):
    """Poll ComfyUI history until all jobs complete."""
    done = []
    errors = 0

    while len(done) < len(jobs):
        time.sleep(5)
        for pid, prefix in jobs:
            if pid in [d[0] for d in done]:
                continue
            try:
                h = json.loads(urllib.request.urlopen(
                    f"{BASE_URL}/history/{pid}"
                ).read())
            except Exception:
                continue

            if pid not in h:
                continue

            entry = h[pid]
            status = entry.get("status", {}).get("status_str", "")

            if status == "error":
                msgs = entry["status"].get("messages", [])
                print(f"  ERROR [{prefix}]: {msgs}")
                done.append((pid, prefix))
                errors += 1
            elif "11" in entry.get("outputs", {}):
                fname = entry["outputs"]["11"]["images"][0]["filename"]
                done.append((pid, prefix))
                print(f"  Done {len(done)}/{total}: {fname}")

    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate LoRA dataset with Kontext")
    parser.add_argument("--ref", default="reference.png",
                        help="Reference image filename in ComfyUI input/ (default: reference.png)")
    parser.add_argument("--test", action="store_true",
                        help="Run single test image only (first headshot)")
    parser.add_argument("--headshots-only", action="store_true",
                        help="Generate only the 15 headshot images")
    parser.add_argument("--lifestyle-only", action="store_true",
                        help="Generate only the 25 lifestyle images")
    args = parser.parse_args()

    print("=" * 64)
    print("  KONTEXT DATASET GENERATOR — FLUX.1 Kontext Dev fp8")
    print("  Identity preservation through native token architecture")
    print("=" * 64)

    # Preflight
    node_specs = preflight_check()

    # Select which prompts to run
    if args.test:
        prompts = [HEADSHOTS[0]]
        seeds = [SEEDS[0]]
        print(f"\n  MODE: TEST (1 image)")
    elif args.headshots_only:
        prompts = HEADSHOTS
        seeds = SEEDS[:len(HEADSHOTS)]
        print(f"\n  MODE: HEADSHOTS ONLY ({len(prompts)} images)")
    elif args.lifestyle_only:
        prompts = LIFESTYLE
        seeds = SEEDS[len(HEADSHOTS):]
        print(f"\n  MODE: LIFESTYLE ONLY ({len(prompts)} images)")
    else:
        prompts = ALL_PROMPTS
        seeds = SEEDS
        print(f"\n  MODE: FULL DATASET ({len(prompts)} images)")

    # Ensure reference is in ComfyUI input
    import shutil, os
    ref_candidates = [
        "/workspace/refs/characters/chara/reference.png",
        "/workspace/input/reference.png",
    ]
    ref_dst = f"/workspace/input/{args.ref}"
    if not os.path.exists(ref_dst):
        for src in ref_candidates:
            if os.path.exists(src):
                shutil.copy(src, ref_dst)
                print(f"\n  Copied reference → {ref_dst}")
                break
        else:
            print(f"\n  WARNING: Reference not found at {ref_dst}")
            print(f"  Make sure '{args.ref}' exists in /workspace/input/")

    print(f"\n  Reference: {args.ref}")
    print(f"  Headshot denoise: {HEADSHOTS[0][1]}")
    print(f"  Lifestyle denoise: {LIFESTYLE[0][1]}")
    print(f"  Steps: 28 | CFG: 3.5 | Sampler: euler")
    print(f"  Output: /workspace/outputs/dataset_*.png")
    print()

    # Queue all jobs
    jobs = []
    for i, (prefix, denoise, prompt) in enumerate(prompts):
        seed = seeds[i]
        wf = build_workflow(prompt, seed, denoise, prefix, args.ref, node_specs)
        try:
            pid = queue_job(wf)
        except Exception as e:
            print(f"\n  FATAL: Failed to queue {prefix}. Check ComfyUI logs.")
            print(f"  Error: {e}")
            if i == 0:
                print("  First job failed — likely a workflow structure issue.")
                print("  Check node inputs with: curl -s http://localhost:8188/object_info/FluxKontextImageScale | python3 -m json.tool")
                sys.exit(1)
            continue

        jobs.append((pid, prefix))
        category = "HEADSHOT" if prefix.startswith("hs_") else "LIFESTYLE"
        print(f"  Queued {i+1}/{len(prompts)} [{category}]: {prefix} (seed={seed})")

    print(f"\n  All {len(jobs)} jobs queued. Waiting for results...\n")

    # Wait
    errors = wait_for_jobs(jobs, len(jobs))

    # Summary
    print()
    print("=" * 64)
    if errors == 0:
        print("  DATASET GENERATION COMPLETE — ALL SUCCESS")
    else:
        print(f"  DATASET GENERATION COMPLETE — {errors} ERRORS")
    print(f"  Images: /workspace/outputs/dataset_*.png")
    print(f"  Total: {len(jobs) - errors} successful / {len(jobs)} queued")
    print("=" * 64)

    if not args.test:
        print("\n  Next steps:")
        print("  1. Review images — delete any with artifacts or wrong face")
        print("  2. Run ArcFace scoring vs reference")
        print("  3. Caption each image (trigger word + scene description)")
        print("  4. Train LoRA with kohya_ss / FluxGym")


if __name__ == "__main__":
    main()
