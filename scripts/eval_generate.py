#!/usr/bin/env python3
"""
eval_generate.py — Checkpoint Evaluation: Image Generation via ComfyUI API

Generates images for each LoRA checkpoint using the running ComfyUI instance.
Uses the same API pattern as run_explore.py — no separate model loading.

Setup (on pod):
    # 1. Symlink LoRA checkpoints into ComfyUI loras directory:
    #    (script does this automatically)
    # 2. Set COMFYUI_URL if not default:
    export COMFYUI_URL=http://localhost:8188

Usage:
    python eval_generate.py
    python eval_generate.py --ref-dir /workspace/lora_training/lily_v001/img

Output:
    /workspace/eval/lily_v001/step_XXXX/prompt_name_sYYY.png
    /workspace/eval/lily_v001/manifest.json
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
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
LORA_DIR        = Path("/workspace/lora_training/lily_v001/output/lora_lily_v001")
OUTPUT_DIR      = Path("/workspace/eval/lily_v001")
COMFYUI_LORAS   = Path("/app/comfyui/models/loras")  # from feedback memory

# Workflow templates (relative to repo root on pod)
SCRIPT_DIR      = Path(__file__).resolve().parent
REPO_ROOT       = SCRIPT_DIR.parent
WF_LORA         = REPO_ROOT / "workflows" / "eval" / "IMG_eval_lora_v001.json"
WF_BASELINE     = REPO_ROOT / "workflows" / "explore" / "IMG_explore_v003.json"

# ── Checkpoints ────────────────────────────────────────────────────────────────
# 0 = baseline (no LoRA) — critical reference point
CHECKPOINTS = [0, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500]

# ── Inference config ───────────────────────────────────────────────────────────
LORA_STRENGTH  = 1.0    # fixed for fair comparison (from feedback: use 1.0 when comparing)
NUM_STEPS      = 28     # standard for FLUX.1 Dev
GUIDANCE       = 4.0    # standard for FLUX.1 Dev
WIDTH          = 1024
HEIGHT         = 1024
SEEDS          = [42, 123, 456]  # 3 seeds per prompt

# ── Prompts ────────────────────────────────────────────────────────────────────
# Research-backed asymmetry trick (v003: FaceSim 0.64 → 0.79):
#   Training captions = simple (no face features)
#   Generation prompts = detailed face description
# All face-forward for ArcFace detection.
PROMPTS = {
    "portrait_direct": (
        "portrait photo of lily, young woman, heart-shaped face, "
        "warm amber-brown hazel eyes, freckles scattered across nose bridge and cheeks, "
        "strong natural dark eyebrows, light brown wavy hair, "
        "direct gaze at camera, neutral expression, "
        "white studio background, soft beauty lighting, "
        "85mm f/2.0, photorealistic, sharp focus on face"
    ),
    "portrait_candid": (
        "candid portrait of lily, 20 year old woman, "
        "hazel amber eyes with freckles on nose bridge and cheeks, "
        "light brown wavy hair loose, slight natural smile, "
        "three-quarter face angle, natural window light, "
        "simple light background, photorealistic, 85mm lens, shallow depth of field"
    ),
    "lifestyle_face": (
        "photo of lily, young woman with hazel eyes and freckles across nose and cheeks, "
        "light brown wavy hair, wearing a simple white t-shirt, "
        "looking directly at camera, natural expression, "
        "soft outdoor daylight, upper body portrait, photorealistic"
    ),
}


# ── Checkpoint file mapping ────────────────────────────────────────────────────
def get_checkpoint_filename(step: int) -> str:
    """Returns the .safetensors filename for a given step."""
    if step == 2500:
        return "lora_lily_v001.safetensors"
    return f"lora_lily_v001_{step:09d}.safetensors"


def get_checkpoint_source(step: int) -> Path:
    """Full path to the checkpoint on the network volume."""
    return LORA_DIR / get_checkpoint_filename(step)


# ── Symlink LoRA checkpoints into ComfyUI ──────────────────────────────────────
def setup_lora_symlinks():
    """Create symlinks from training output → ComfyUI loras directory."""
    COMFYUI_LORAS.mkdir(parents=True, exist_ok=True)
    linked = 0
    for step in CHECKPOINTS:
        if step == 0:
            continue
        src = get_checkpoint_source(step)
        # Use eval-prefixed name to avoid collisions
        dst = COMFYUI_LORAS / f"eval_lily_step{step:04d}.safetensors"
        if dst.exists() or dst.is_symlink():
            continue
        if not src.exists():
            print(f"  WARN: checkpoint not found: {src}")
            continue
        dst.symlink_to(src)
        linked += 1
    print(f"  Symlinked {linked} checkpoints → {COMFYUI_LORAS}")


# ── Workflow injection ─────────────────────────────────────────────────────────
def load_workflow(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def build_workflow_baseline(wf_template: dict, prompt: str, seed: int,
                            prefix: str) -> dict:
    """Build baseline workflow (no LoRA) from v003 template."""
    wf = copy.deepcopy(wf_template)
    wf["4"]["inputs"]["text"] = prompt
    wf["7"]["inputs"]["width"] = WIDTH
    wf["7"]["inputs"]["height"] = HEIGHT
    wf["8"]["inputs"]["steps"] = NUM_STEPS
    wf["5"]["inputs"]["guidance"] = GUIDANCE
    wf["10"]["inputs"]["noise_seed"] = seed
    wf["13"]["inputs"]["filename_prefix"] = prefix
    return wf


def build_workflow_lora(wf_template: dict, prompt: str, seed: int,
                        prefix: str, lora_name: str,
                        lora_strength: float) -> dict:
    """Build LoRA workflow from eval template."""
    wf = copy.deepcopy(wf_template)
    wf["4"]["inputs"]["text"] = prompt
    wf["7"]["inputs"]["width"] = WIDTH
    wf["7"]["inputs"]["height"] = HEIGHT
    wf["8"]["inputs"]["steps"] = NUM_STEPS
    wf["5"]["inputs"]["guidance"] = GUIDANCE
    wf["10"]["inputs"]["noise_seed"] = seed
    wf["13"]["inputs"]["filename_prefix"] = prefix
    wf["14"]["inputs"]["lora_name"] = lora_name
    wf["14"]["inputs"]["strength_model"] = lora_strength
    return wf


# ── ComfyUI API (same pattern as run_explore.py) ──────────────────────────────
def submit_prompt(base_url: str, workflow: dict) -> str:
    """POST workflow to ComfyUI, return prompt_id."""
    payload = {"prompt": workflow}
    r = requests.post(f"{base_url}/prompt", json=payload, timeout=30)
    body = r.json()
    if r.status_code != 200 or "prompt_id" not in body:
        raise RuntimeError(f"ComfyUI rejected workflow: {body}")
    return body["prompt_id"]


def wait_for_completion(base_url: str, prompt_id: str, timeout: int = 600) -> None:
    """Poll /queue until the job finishes."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            q = requests.get(f"{base_url}/queue", timeout=10).json()
            running = q.get("queue_running", [])
            pending = q.get("queue_pending", [])
            active_ids = [item[1] for item in running + pending]
            if prompt_id not in active_ids:
                return
        except Exception:
            pass
        time.sleep(3)
    raise TimeoutError(f"Job {prompt_id} did not complete within {timeout}s")


def get_output_filename(base_url: str, prompt_id: str) -> str:
    """Get the output image filename from /history."""
    h = requests.get(f"{base_url}/history/{prompt_id}", timeout=15).json()
    job = h.get(prompt_id, {})
    status = job.get("status", {})
    if not status.get("completed", False):
        msgs = status.get("messages", [])
        raise RuntimeError(f"Job not completed: {status}\nMessages: {msgs}")
    outputs = job.get("outputs", {})
    for node_output in outputs.values():
        if isinstance(node_output, dict):
            images = node_output.get("images", [])
            if images:
                return images[0]["filename"]
    raise RuntimeError("No output images found in history")


def download_image(base_url: str, filename: str, save_path: Path) -> None:
    """Download an image from ComfyUI /view endpoint."""
    r = requests.get(
        f"{base_url}/view",
        params={"filename": filename, "subfolder": "", "type": "output"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Failed to download {filename}: HTTP {r.status_code}")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(r.content)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate eval images for LoRA checkpoint comparison")
    parser.add_argument("--comfyui-url", default=os.environ.get("COMFYUI_URL", "http://localhost:8188"),
                        help="ComfyUI API URL")
    args = parser.parse_args()
    base_url = args.comfyui_url

    # Verify ComfyUI is reachable
    try:
        r = requests.get(f"{base_url}/system_stats", timeout=10)
        r.raise_for_status()
        print(f"ComfyUI reachable at {base_url}")
    except Exception as e:
        print(f"ERROR: Cannot reach ComfyUI at {base_url}: {e}")
        sys.exit(1)

    # Setup symlinks
    print("\nSetting up LoRA symlinks...")
    setup_lora_symlinks()

    # Load workflow templates
    if not WF_LORA.exists():
        print(f"ERROR: Workflow template not found: {WF_LORA}")
        print("Make sure the repo is synced to the pod.")
        sys.exit(1)

    wf_lora_template = load_workflow(WF_LORA)

    if WF_BASELINE.exists():
        wf_baseline_template = load_workflow(WF_BASELINE)
    else:
        wf_baseline_template = None
        print(f"WARN: Baseline workflow not found: {WF_BASELINE}")
        print("  Skipping step 0 (baseline).")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    total_generated = 0
    total_skipped = 0
    total_errors = 0

    for step in CHECKPOINTS:
        step_dir = OUTPUT_DIR / f"step_{step:04d}"
        step_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'─' * 60}")

        if step == 0:
            if wf_baseline_template is None:
                continue
            print(f"Step    0 | baseline (no LoRA)")
        else:
            lora_name = f"eval_lily_step{step:04d}.safetensors"
            src = get_checkpoint_source(step)
            if not src.exists():
                print(f"Step {step:4d} | SKIP — checkpoint not found")
                continue
            print(f"Step {step:4d} | {lora_name}")

        for prompt_name, prompt_text in PROMPTS.items():
            for seed in SEEDS:
                fname = f"{prompt_name}_s{seed}.png"
                out_path = step_dir / fname

                if out_path.exists():
                    total_skipped += 1
                    manifest.append({
                        "step": step, "prompt": prompt_name,
                        "seed": seed, "path": str(out_path),
                    })
                    continue

                prefix = f"eval_step{step:04d}_{prompt_name}_s{seed}"

                try:
                    if step == 0:
                        wf = build_workflow_baseline(
                            wf_baseline_template, prompt_text, seed, prefix)
                    else:
                        wf = build_workflow_lora(
                            wf_lora_template, prompt_text, seed, prefix,
                            lora_name, LORA_STRENGTH)

                    prompt_id = submit_prompt(base_url, wf)
                    wait_for_completion(base_url, prompt_id, timeout=600)
                    output_file = get_output_filename(base_url, prompt_id)
                    download_image(base_url, output_file, out_path)
                    total_generated += 1
                    print(f"  saved: {fname}")

                except Exception as e:
                    total_errors += 1
                    print(f"  ERROR: {fname} — {e}")
                    continue

                manifest.append({
                    "step": step, "prompt": prompt_name,
                    "seed": seed, "path": str(out_path),
                })

    # Save manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Generated : {total_generated}")
    print(f"Skipped   : {total_skipped} (already existed)")
    print(f"Errors    : {total_errors}")
    print(f"Total     : {len(manifest)}")
    print(f"Manifest  : {manifest_path}")
    print(f"\nNext: python eval_arcface.py --ref-dir /workspace/lora_training/lily_v001/img")


if __name__ == "__main__":
    main()
