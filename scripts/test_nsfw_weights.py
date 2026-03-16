#!/usr/bin/env python3
"""
test_nsfw_weights.py — NSFW LoRA weight combination test

One explicit prompt, multiple lily/NSFW strength combos.
Goal: find optimal weights for step 1 of inpainting workflow
(face drift irrelevant — will be fixed in step 2).

Usage:
    python test_nsfw_weights.py
    python test_nsfw_weights.py --comfyui-url http://localhost:8188

Output:
    /workspace/test_nsfw_weights/lily{L}_nsfw{N}_s{seed}.png
"""

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: pip install requests")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("/workspace/test_nsfw_weights")

LORA_LILY = "lora_lily_v001.safetensors"
LORA_NSFW = "nsfw_flux_lora_v1.safetensors"

# Weight combos to test — pushing NSFW higher since face will be inpainted
COMBOS = [
    (1.0, 0.45),  # current baseline
    (1.0, 0.55),
    (1.0, 0.65),
    (1.0, 0.75),
    (0.9, 0.75),
    (0.8, 0.80),
    (0.7, 0.85),
]

SEEDS = [42, 123]

# One explicit prompt — stress test pose compliance
PROMPT = (
    "AiArtV explicit erotic photo, lily, young woman with hazel eyes and freckles on nose and cheeks, "
    "on all fours doggy style position, back arched, nude, bare ass toward camera, "
    "bedroom setting, warm natural light, 35mm f/1.4, photorealistic, shot on Canon"
)

# Standard FLUX settings
NUM_STEPS = 28
GUIDANCE  = 4.0
WIDTH     = 1024
HEIGHT    = 1024

# ── Workflow builder ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
WF_PATH    = REPO_ROOT / "workflows" / "eval" / "IMG_eval_lora_v001.json"


def build_workflow(wf_template: dict, prompt: str, seed: int,
                   lily_strength: float, nsfw_strength: float,
                   prefix: str) -> dict:
    wf = copy.deepcopy(wf_template)

    # Prompt / sampler settings
    wf["4"]["inputs"]["text"]           = prompt
    wf["7"]["inputs"]["width"]          = WIDTH
    wf["7"]["inputs"]["height"]         = HEIGHT
    wf["8"]["inputs"]["steps"]          = NUM_STEPS
    wf["5"]["inputs"]["guidance"]       = GUIDANCE
    wf["10"]["inputs"]["noise_seed"]    = seed
    wf["13"]["inputs"]["filename_prefix"] = prefix

    # Node 14 = lily LoRA
    wf["14"]["inputs"]["lora_name"]     = LORA_LILY
    wf["14"]["inputs"]["strength_model"] = lily_strength

    # Node 15 = NSFW LoRA (chained after lily)
    wf["15"] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "model": ["14", 0],
            "lora_name": NSFW_LORA_NAME,
            "strength_model": nsfw_strength,
        },
    }

    # Guider and scheduler must reference node 15, not 14
    wf["6"]["inputs"]["model"] = ["15", 0]
    wf["8"]["inputs"]["model"] = ["15", 0]

    return wf


# ── ComfyUI API ────────────────────────────────────────────────────────────────
def submit_prompt(base_url: str, workflow: dict) -> str:
    r = requests.post(f"{base_url}/prompt", json={"prompt": workflow}, timeout=30)
    body = r.json()
    if r.status_code != 200 or "prompt_id" not in body:
        raise RuntimeError(f"ComfyUI rejected: {body}")
    return body["prompt_id"]


def wait_for_completion(base_url: str, prompt_id: str, timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            q = requests.get(f"{base_url}/queue", timeout=10).json()
            active = [item[1] for item in q.get("queue_running", []) + q.get("queue_pending", [])]
            if prompt_id not in active:
                return
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError(f"Job {prompt_id} timed out")


def get_output_filename(base_url: str, prompt_id: str) -> str:
    h = requests.get(f"{base_url}/history/{prompt_id}", timeout=15).json()
    job = h.get(prompt_id, {})
    for node_output in job.get("outputs", {}).values():
        if isinstance(node_output, dict):
            images = node_output.get("images", [])
            if images:
                return images[0]["filename"]
    raise RuntimeError("No output images found")


def download_image(base_url: str, filename: str, save_path: Path) -> None:
    r = requests.get(
        f"{base_url}/view",
        params={"filename": filename, "subfolder": "", "type": "output"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Download failed: HTTP {r.status_code}")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(r.content)


# ── Main ───────────────────────────────────────────────────────────────────────
NSFW_LORA_NAME = LORA_NSFW  # alias used in build_workflow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfyui-url",
                        default=os.environ.get("COMFYUI_URL", "http://localhost:8188"))
    args = parser.parse_args()
    base_url = args.comfyui_url

    # Verify ComfyUI
    try:
        requests.get(f"{base_url}/system_stats", timeout=10).raise_for_status()
        print(f"ComfyUI reachable at {base_url}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Load workflow template
    if not WF_PATH.exists():
        print(f"ERROR: workflow not found: {WF_PATH}")
        sys.exit(1)
    with open(WF_PATH) as f:
        wf_template = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(COMBOS) * len(SEEDS)
    done = 0

    print(f"\n{len(COMBOS)} combos × {len(SEEDS)} seeds = {total} images\n")
    print(f"{'─' * 55}")
    print(f"  {'LILY':>6} {'NSFW':>6} {'SEED':>6}  STATUS")
    print(f"{'─' * 55}")

    for lily_s, nsfw_s in COMBOS:
        for seed in SEEDS:
            tag    = f"lily{int(lily_s*100):03d}_nsfw{int(nsfw_s*100):03d}_s{seed}"
            prefix = f"nsfw_test_{tag}"
            out    = OUTPUT_DIR / f"{tag}.png"

            if out.exists():
                print(f"  {lily_s:>6.2f} {nsfw_s:>6.2f} {seed:>6}  skip (exists)")
                done += 1
                continue

            try:
                wf = build_workflow(wf_template, PROMPT, seed, lily_s, nsfw_s, prefix)
                pid = submit_prompt(base_url, wf)
                wait_for_completion(base_url, pid)
                fname = get_output_filename(base_url, pid)
                download_image(base_url, fname, out)
                done += 1
                print(f"  {lily_s:>6.2f} {nsfw_s:>6.2f} {seed:>6}  saved → {out.name}")
            except Exception as e:
                print(f"  {lily_s:>6.2f} {nsfw_s:>6.2f} {seed:>6}  ERROR: {e}")

    print(f"{'─' * 55}")
    print(f"\nDone: {done}/{total}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"\nReview images — looking for:")
    print(f"  - Pose compliance (doggy style correct?)")
    print(f"  - Anatomy quality (smoothed or detailed?)")
    print(f"  - Face drift is OK — will be fixed by inpainting")


if __name__ == "__main__":
    main()
