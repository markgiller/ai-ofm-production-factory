#!/usr/bin/env python3
"""
Generate LoRA training dataset for Lily Harper using PuLID-FLUX identity guidance.
40 images: 15 headshots (white/neutral bg, angles, expressions) + 25 lifestyle scenes.
Prompts describe scene/pose/lighting only — NO face features (LoRA learns those).
"""
import json
import urllib.request
import time
import argparse

BASE_URL = "http://localhost:8188"

REF_IMAGE = "lily_canonical.png"
PULID_WEIGHT = 0.55  # 0.55 = identity without plastic skin (0.9 was too much)

# ── 15 HEADSHOTS (neutral/white bg, different angles & expressions) ──────────
HEADSHOTS = [
    "IMG_3001.HEIC, a candid raw photo of a young woman, close-up headshot, facing camera directly, neutral expression, plain white background, soft even studio light, shot on Canon EOS R5 85mm f/1.8",
    "IMG_3002.HEIC, a candid raw photo of a young woman, close-up headshot, slight smile, plain white background, soft diffused light, shot on Sony A7IV 85mm f/1.4",
    "IMG_3003.HEIC, a candid raw photo of a young woman, close-up headshot, head tilted slightly left, warm smile, white background, soft studio light, shot on Canon EOS R5 50mm f/1.2",
    "IMG_3004.HEIC, a candid raw photo of a young woman, close-up headshot, head tilted slightly right, neutral expression, white background, soft studio light, shot on Nikon Z8 85mm f/1.8",
    "IMG_3005.HEIC, a candid raw photo of a young woman, close-up headshot, looking slightly left of camera, relaxed expression, white background, soft even light, shot on Fujifilm X-T5 56mm f/1.2",
    "IMG_3006.HEIC, a candid raw photo of a young woman, close-up headshot, looking slightly right of camera, slight smile, white background, soft studio light, shot on Sony A7IV 85mm f/1.4",
    "IMG_3007.HEIC, a candid raw photo of a young woman, close-up headshot, three quarter view facing left, neutral expression, white background, soft light, shot on Canon EOS R5 85mm f/1.8",
    "IMG_3008.HEIC, a candid raw photo of a young woman, close-up headshot, three quarter view facing right, warm smile, white background, soft studio light, shot on Leica Q2",
    "IMG_3009.HEIC, a candid raw photo of a young woman, close-up headshot, laughing expression, eyes slightly squinting, white background, bright soft light, shot on Fujifilm X-T5",
    "IMG_3010.HEIC, a candid raw photo of a young woman, close-up headshot, serious thoughtful expression, white background, soft even light, shot on Canon EOS R5 50mm f/1.2",
    "IMG_3011.HEIC, a candid raw photo of a young woman, close-up headshot, looking down slightly, gentle smile, white background, soft overhead light, shot on Sony A7IV 85mm f/1.4",
    "IMG_3012.HEIC, a candid raw photo of a young woman, close-up headshot, chin slightly raised, confident expression, white background, soft studio light, shot on Nikon Z8 85mm f/1.8",
    "IMG_3013.HEIC, a candid raw photo of a young woman, close-up headshot, slight frown curious expression, white background, soft even light, shot on Canon EOS R5 85mm f/1.8",
    "IMG_3014.HEIC, a candid raw photo of a young woman, close-up headshot, hair tucked behind one ear, soft smile, plain grey background, soft studio light, shot on Fujifilm X-T5 56mm f/1.2",
    "IMG_3015.HEIC, a candid raw photo of a young woman, close-up headshot, slightly from below eye level, neutral expression, white background, soft light, shot on Sony A7IV 50mm f/1.4",
]

# ── 25 LIFESTYLE SCENES (diverse settings, poses, lighting, outfits) ─────────
LIFESTYLE = [
    # Indoor casual
    "IMG_4001.HEIC, a candid raw photo of a young woman, medium shot, sitting at a cafe table with a coffee cup, warm indoor light, cozy atmosphere, wearing a casual sweater, shot on Canon EOS R5 35mm f/1.8",
    "IMG_4002.HEIC, a candid raw photo of a young woman, 3/4 portrait, reading a book on a sofa, soft window light from left, wearing an oversized university hoodie, shot on Sony A7IV 50mm f/1.4",
    "IMG_4003.HEIC, a candid raw photo of a young woman, medium shot, standing in a kitchen making breakfast, morning light from window, wearing a simple t-shirt, shot on Fujifilm X-T5",
    "IMG_4004.HEIC, a candid raw photo of a young woman, 3/4 portrait, sitting at a desk with laptop and notebooks, warm desk lamp light, wearing glasses and a cardigan, shot on Canon EOS R5 50mm f/1.2",
    "IMG_4005.HEIC, a candid raw photo of a young woman, close-up portrait, lying on a bed looking at camera, soft warm light, wearing a simple tank top, relaxed expression, shot on Sony A7IV 35mm f/1.4",
    # Outdoor casual
    "IMG_4006.HEIC, a candid raw photo of a young woman, medium shot, walking down a city sidewalk, golden hour light, wearing jeans and a casual jacket, urban background, shot on Canon EOS R5 85mm f/1.8",
    "IMG_4007.HEIC, a candid raw photo of a young woman, 3/4 portrait, sitting on a park bench, dappled sunlight through trees, wearing a summer dress, shot on Fujifilm X-T5 56mm f/1.2",
    "IMG_4008.HEIC, a candid raw photo of a young woman, medium shot, leaning against a brick wall, overcast soft light, wearing a denim jacket and jeans, shot on Sony A7IV 50mm f/1.4",
    "IMG_4009.HEIC, a candid raw photo of a young woman, close-up portrait, at a farmers market, natural daylight, wearing a casual blouse, slight smile, shot on Leica Q2",
    "IMG_4010.HEIC, a candid raw photo of a young woman, 3/4 portrait, sitting on outdoor cafe terrace, warm afternoon sun, wearing sunglasses on head and a linen top, shot on Canon EOS R5 85mm f/1.8",
    # Campus / student life
    "IMG_4011.HEIC, a candid raw photo of a young woman, medium shot, walking on university campus with a backpack, bright overcast light, wearing casual student outfit, shot on iPhone 15 Pro",
    "IMG_4012.HEIC, a candid raw photo of a young woman, 3/4 portrait, sitting in a library with books, soft overhead fluorescent and window light, wearing a cozy knit sweater, shot on Sony A7IV 35mm f/1.4",
    "IMG_4013.HEIC, a candid raw photo of a young woman, close-up portrait, in a lecture hall, soft indoor light, wearing a simple top, focused expression, shot on Fujifilm X-T5",
    # Evening / night
    "IMG_4014.HEIC, a candid raw photo of a young woman, 3/4 portrait, at a rooftop bar in the evening, warm string lights bokeh, wearing a nice blouse, shot on Canon EOS R5 50mm f/1.2",
    "IMG_4015.HEIC, a candid raw photo of a young woman, close-up portrait, blue hour outdoor, city lights in background, wearing a light scarf, shot on Sony A7IV 85mm f/1.4",
    # Active / sport
    "IMG_4016.HEIC, a candid raw photo of a young woman, medium shot, jogging in a park, morning light, wearing athletic wear and ponytail, shot on Canon EOS R5 70mm f/2.8",
    "IMG_4017.HEIC, a candid raw photo of a young woman, 3/4 portrait, holding a yoga mat outdoors, soft golden hour light, wearing leggings and a crop top, shot on Fujifilm X-T5",
    # Cozy / intimate
    "IMG_4018.HEIC, a candid raw photo of a young woman, close-up portrait, wrapped in a blanket on a couch, soft warm lamp light, relaxed sleepy expression, shot on Sony A7IV 50mm f/1.4",
    "IMG_4019.HEIC, a candid raw photo of a young woman, 3/4 portrait, sitting by a window on a rainy day, soft diffused grey light, wearing an oversized sweater and holding a mug, shot on Canon EOS R5 35mm f/1.8",
    # Fashion / editorial light
    "IMG_4020.HEIC, a candid raw photo of a young woman, medium shot, standing in a doorway, dramatic side light, wearing a simple white shirt and jeans, shot on Nikon Z8 85mm f/1.8",
    "IMG_4021.HEIC, a candid raw photo of a young woman, 3/4 portrait, in a flower field, bright natural light, wearing a floral summer dress, shot on Canon EOS R5 85mm f/1.8",
    # Beach / nature
    "IMG_4022.HEIC, a candid raw photo of a young woman, medium shot, at the beach during golden hour, warm backlight, wearing a casual sundress, wind in hair, shot on Sony A7IV 85mm f/1.4",
    "IMG_4023.HEIC, a candid raw photo of a young woman, close-up portrait, in a forest, dappled green light through leaves, wearing a casual flannel shirt, shot on Fujifilm X-T5 56mm f/1.2",
    # Different lighting conditions
    "IMG_4024.HEIC, a candid raw photo of a young woman, close-up portrait, dramatic studio lighting one side, dark background, wearing a simple black top, shot on Canon EOS R5 85mm f/1.4",
    "IMG_4025.HEIC, a candid raw photo of a young woman, 3/4 portrait, in a sunlit greenhouse, bright warm natural light, wearing a light cotton dress, surrounded by plants, shot on Leica Q2",
]

ALL_PROMPTS = HEADSHOTS + LIFESTYLE

# 40 unique seeds
SEEDS = list(range(8000, 8000 + len(ALL_PROMPTS) * 100, 100))


def build_workflow(prompt_text, seed):
    return {
        "1":  {"class_type": "UNETLoader",           "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}},
        "2":  {"class_type": "DualCLIPLoader",        "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3":  {"class_type": "VAELoader",             "inputs": {"vae_name": "ae.safetensors"}},
        "4":  {"class_type": "CLIPTextEncode",        "inputs": {"text": prompt_text, "clip": ["2", 0]}},
        "5":  {"class_type": "FluxGuidance",          "inputs": {"conditioning": ["4", 0], "guidance": 3.5}},
        "14": {"class_type": "PulidFluxModelLoader",  "inputs": {"pulid_file": "pulid_flux_v0.9.1.safetensors"}},
        "15": {"class_type": "LoadImage",             "inputs": {"image": REF_IMAGE}},
        "16": {"class_type": "PulidFluxEvaClipLoader","inputs": {}},
        "17": {"class_type": "PulidFluxFaceNetLoader","inputs": {"provider": "CUDA"}},
        "18": {"class_type": "ApplyPulidFlux",        "inputs": {
            "model": ["1", 0], "pulid_flux": ["14", 0], "eva_clip": ["16", 0],
            "face_analysis": ["17", 0], "image": ["15", 0],
            "weight": PULID_WEIGHT, "start_at": 0.0, "end_at": 1.0,
        }},
        "6":  {"class_type": "BasicGuider",           "inputs": {"model": ["18", 0], "conditioning": ["5", 0]}},
        "7":  {"class_type": "EmptyLatentImage",      "inputs": {"width": 832, "height": 1024, "batch_size": 1}},
        "8":  {"class_type": "BasicScheduler",        "inputs": {"model": ["18", 0], "scheduler": "simple", "steps": 25, "denoise": 1.0}},
        "9":  {"class_type": "KSamplerSelect",        "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise",           "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["6", 0], "sampler": ["9", 0], "sigmas": ["8", 0], "latent_image": ["7", 0]}},
        "12": {"class_type": "VAEDecode",             "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",             "inputs": {"images": ["12", 0], "filename_prefix": "dataset_lily"}},
    }


def queue_job(workflow):
    data = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(BASE_URL + "/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print("ERROR:", e.read().decode())
        raise
    return resp["prompt_id"]


def main():
    parser = argparse.ArgumentParser(description="Generate Lily Harper LoRA training dataset")
    parser.add_argument("--weight", type=float, default=PULID_WEIGHT,
                        help=f"PuLID identity weight (default: {PULID_WEIGHT})")
    parser.add_argument("--headshots-only", action="store_true",
                        help="Generate only the 15 headshots")
    parser.add_argument("--lifestyle-only", action="store_true",
                        help="Generate only the 25 lifestyle shots")
    parser.add_argument("--test", type=int, default=0,
                        help="Generate only first N images (for testing)")
    parser.add_argument("--comfyui-url", default=BASE_URL,
                        help=f"ComfyUI API URL (default: {BASE_URL})")
    args = parser.parse_args()

    global BASE_URL, PULID_WEIGHT
    BASE_URL = args.comfyui_url
    PULID_WEIGHT = args.weight

    # Select prompts
    if args.headshots_only:
        prompts = HEADSHOTS
        print(f"[dataset] Mode: headshots only ({len(prompts)} images)")
    elif args.lifestyle_only:
        prompts = LIFESTYLE
        print(f"[dataset] Mode: lifestyle only ({len(prompts)} images)")
    else:
        prompts = ALL_PROMPTS
        print(f"[dataset] Mode: full dataset ({len(prompts)} images)")

    if args.test:
        prompts = prompts[:args.test]
        print(f"[dataset] TEST MODE: generating {len(prompts)} images only")

    seeds = SEEDS[:len(prompts)]

    # Copy reference to ComfyUI input if needed
    import shutil, os
    ref_src = "/workspace/refs/characters/chara/lily_canonical.png"
    ref_dst = f"/workspace/input/{REF_IMAGE}"
    if not os.path.exists(ref_dst):
        shutil.copy(ref_src, ref_dst)
        print(f"[dataset] Copied reference to {ref_dst}")

    print(f"[dataset] PuLID weight: {PULID_WEIGHT}")
    print(f"[dataset] Reference: {REF_IMAGE}")
    print(f"[dataset] Resolution: 832x1024 (close to 4:5)")
    print()

    # Queue all jobs
    jobs = []
    for i, (prompt, seed) in enumerate(zip(prompts, seeds)):
        wf = build_workflow(prompt, seed)
        pid = queue_job(wf)
        jobs.append(pid)
        shot_type = "headshot" if i < len(HEADSHOTS) and not args.lifestyle_only else "lifestyle"
        print(f"  Queued {i+1}/{len(prompts)}: seed={seed} [{shot_type}]")

    print(f"\n[dataset] All {len(jobs)} jobs queued. Waiting for results...\n")

    # Wait for completion
    done = []
    errors = []
    while len(done) < len(jobs):
        time.sleep(5)
        for pid in jobs:
            if pid in done:
                continue
            h = json.loads(urllib.request.urlopen(BASE_URL + "/history/" + pid).read())
            if pid in h:
                entry = h[pid]
                if entry.get("status", {}).get("status_str") == "error":
                    msgs = entry["status"].get("messages", [])
                    print(f"  ERROR job {pid}: {msgs}")
                    done.append(pid)
                    errors.append(pid)
                elif "13" in entry.get("outputs", {}):
                    fname = entry["outputs"]["13"]["images"][0]["filename"]
                    done.append(pid)
                    print(f"  Done {len(done)}/{len(jobs)}: {fname}")

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE")
    print(f"  Total: {len(jobs)} | Success: {len(jobs) - len(errors)} | Errors: {len(errors)}")
    print(f"  Images: /workspace/outputs/dataset_lily_*.png")
    print(f"{'='*60}")

    if errors:
        print(f"\nFailed jobs: {errors}")

    print(f"\nNext steps:")
    print(f"  1. Review images visually")
    print(f"  2. Run ArcFace selection:")
    print(f"     python scripts/select_training_candidates.py \\")
    print(f"       --reference /workspace/refs/characters/chara/lily_canonical.png \\")
    print(f"       --input /workspace/outputs/ \\")
    print(f"       --output /workspace/lora_training/lily_v001/dataset/ \\")
    print(f"       --top 35 --min-similarity 0.4 --report /workspace/lora_training/lily_v001/selection_report.json")
    print(f"  3. Delete any bad images from dataset/")
    print(f"  4. Caption remaining images")
    print(f"  5. Train LoRA")


if __name__ == "__main__":
    main()
