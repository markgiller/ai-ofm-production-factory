#!/usr/bin/env python3
"""
Batch generate Lily v002 dataset images via ComfyUI API.

Prerequisites:
  1. ComfyUI running on the pod (port 8188)
  2. Workflow saved in API format: /workspace/workflow_api.json
     (ComfyUI → Settings → Dev Mode → Save API Format)
  3. Prompts JSON: wave1 and/or wave2

Usage (run on pod):
  python3 batch_generate_dataset.py
  python3 batch_generate_dataset.py --waves 2          # wave2 only
  python3 batch_generate_dataset.py --waves 1,2        # both waves
  python3 batch_generate_dataset.py --seeds 3           # 3 seeds per prompt (default)
  python3 batch_generate_dataset.py --start-seed 200000 # custom starting seed
  python3 batch_generate_dataset.py --resume             # resume from last completed
  python3 batch_generate_dataset.py --dry-run            # print plan, don't generate
"""

import argparse
import copy
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

COMFYUI_URL = "http://127.0.0.1:8188"
WORKSPACE = Path("/workspace")

WORKFLOW_API_FILE = WORKSPACE / "workflow_api.json"
PROMPTS_WAVE1 = WORKSPACE / "repo/creative/prompts/lily_v002_dataset_prompts.json"
PROMPTS_WAVE2 = WORKSPACE / "repo/creative/prompts/lily_v002_dataset_prompts_wave2.json"

# Fallback paths (if repo not cloned yet)
PROMPTS_WAVE1_ALT = Path("/workspace/creative/prompts/lily_v002_dataset_prompts.json")
PROMPTS_WAVE2_ALT = Path("/workspace/creative/prompts/lily_v002_dataset_prompts_wave2.json")

OUTPUT_PREFIX = "lily_v002_dataset"
PROGRESS_FILE = WORKSPACE / "lily_v002_generation_progress.json"

# Node IDs in the workflow (from Character_Chroma.json)
# These are the node IDs that the script modifies per-job.
NODE_PROMPT = "251"       # ttN text → positive prompt
NODE_NEGATIVE = "468"     # ttN text → negative prompt
NODE_SEED = "207"         # RandomNoise → noise_seed
NODE_SAVE = "178"         # SaveImage → filename_prefix

# Standard negative prompt (from chroma_prompting.md)
NEGATIVE_PROMPT = (
    "This greyscale unfinished sketch has bad proportions, is featureless and disfigured. "
    "It is a blurry ugly mess and with excessive gaussian blur. It is riddled with watermarks "
    "and signatures. Everything is smudged with leaking colors and nonsensical orientation of "
    "objects. Messy and abstract image filled with artifacts disrupt the coherency of the "
    "overall composition. The image has extreme chromatic abberations and inconsistent lighting. "
    "Dull, monochrome colors and countless artistic errors."
)


# ─── ComfyUI API ─────────────────────────────────────────────────────────────

def queue_prompt(workflow: dict) -> str:
    """Submit a prompt to ComfyUI. Returns prompt_id."""
    payload = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    return result["prompt_id"]


def get_queue_status() -> dict:
    """Get current queue status."""
    with urllib.request.urlopen(f"{COMFYUI_URL}/queue") as resp:
        return json.loads(resp.read())


def get_history(prompt_id: str) -> dict:
    """Get execution history for a prompt_id."""
    with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
        return json.loads(resp.read())


def wait_for_completion(prompt_id: str, timeout: int = 300) -> bool:
    """Poll until prompt_id appears in history (completed). Returns True on success."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            history = get_history(prompt_id)
            if prompt_id in history:
                status = history[prompt_id].get("status", {})
                if status.get("completed", False):
                    return True
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    print(f"    ERROR: {msgs}")
                    return False
        except Exception:
            pass
        time.sleep(2)
    print(f"    TIMEOUT after {timeout}s")
    return False


def check_comfyui() -> bool:
    """Check if ComfyUI is running and responsive."""
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5) as resp:
            data = json.loads(resp.read())
            gpu = data.get("devices", [{}])[0]
            print(f"  GPU: {gpu.get('name', 'unknown')}")
            print(f"  VRAM: {gpu.get('vram_total', 0) / 1e9:.1f} GB")
            return True
    except Exception as e:
        print(f"  ComfyUI not reachable: {e}")
        return False


# ─── Workflow Modification ────────────────────────────────────────────────────

def modify_workflow(template: dict, prompt_text: str, seed: int, filename: str) -> dict:
    """Create a modified copy of the workflow template for one generation job."""
    wf = copy.deepcopy(template)

    # Set positive prompt
    if NODE_PROMPT in wf:
        wf[NODE_PROMPT]["inputs"]["text"] = prompt_text
    else:
        print(f"  WARNING: prompt node {NODE_PROMPT} not found in workflow")

    # Set negative prompt
    if NODE_NEGATIVE in wf:
        wf[NODE_NEGATIVE]["inputs"]["text"] = NEGATIVE_PROMPT
    else:
        print(f"  WARNING: negative node {NODE_NEGATIVE} not found in workflow")

    # Set seed
    if NODE_SEED in wf:
        wf[NODE_SEED]["inputs"]["noise_seed"] = seed
    else:
        print(f"  WARNING: seed node {NODE_SEED} not found in workflow")

    # Set output filename
    if NODE_SAVE in wf:
        wf[NODE_SAVE]["inputs"]["filename_prefix"] = filename
    else:
        print(f"  WARNING: save node {NODE_SAVE} not found in workflow")

    return wf


# ─── Progress Tracking ───────────────────────────────────────────────────────

def load_progress() -> set:
    """Load set of completed job keys from progress file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            data = json.load(f)
        return set(data.get("completed", []))
    return set()


def save_progress(completed: set):
    """Save completed job keys to progress file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"completed": sorted(completed), "count": len(completed)}, f, indent=2)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch generate Lily v002 dataset")
    parser.add_argument("--waves", default="2", help="Which prompt waves to use: 1, 2, or 1,2 (default: 2)")
    parser.add_argument("--seeds", type=int, default=3, help="Number of seeds per prompt (default: 3)")
    parser.add_argument("--start-seed", type=int, default=100500, help="Starting seed (default: 100500)")
    parser.add_argument("--resume", action="store_true", help="Resume from last completed job")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without generating")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per image in seconds (default: 300)")
    parser.add_argument("--workflow", type=str, default=str(WORKFLOW_API_FILE), help="Path to workflow API JSON")
    args = parser.parse_args()

    print("=" * 70)
    print("LILY V002 DATASET BATCH GENERATOR")
    print("=" * 70)

    # ── Load workflow template ──
    workflow_path = Path(args.workflow)
    if not workflow_path.exists():
        print(f"\nERROR: Workflow API file not found: {workflow_path}")
        print("\nTo create it:")
        print("  1. Open ComfyUI in browser")
        print("  2. Settings → Enable Dev Mode")
        print("  3. Click 'Save (API Format)'")
        print(f"  4. Save as: {WORKFLOW_API_FILE}")
        return

    with open(workflow_path) as f:
        workflow_template = json.load(f)

    # Validate critical nodes exist
    for node_id, name in [(NODE_PROMPT, "prompt"), (NODE_SEED, "seed"), (NODE_SAVE, "save")]:
        if node_id not in workflow_template:
            print(f"ERROR: Node {node_id} ({name}) not found in workflow.")
            print(f"Available nodes: {list(workflow_template.keys())[:20]}...")
            return

    print(f"\nWorkflow: {workflow_path}")
    print(f"Nodes: prompt={NODE_PROMPT}, negative={NODE_NEGATIVE}, seed={NODE_SEED}, save={NODE_SAVE}")

    # ── Load prompts ──
    waves = [int(w.strip()) for w in args.waves.split(",")]
    all_prompts = []

    for wave_num in waves:
        if wave_num == 1:
            path = PROMPTS_WAVE1 if PROMPTS_WAVE1.exists() else PROMPTS_WAVE1_ALT
        else:
            path = PROMPTS_WAVE2 if PROMPTS_WAVE2.exists() else PROMPTS_WAVE2_ALT

        if not path.exists():
            print(f"WARNING: Wave {wave_num} file not found: {path}")
            continue

        with open(path) as f:
            data = json.load(f)

        prompts = data.get("prompts", [])
        print(f"Wave {wave_num}: {len(prompts)} prompts from {path.name}")
        for p in prompts:
            p["wave"] = wave_num
        all_prompts.extend(prompts)

    if not all_prompts:
        print("ERROR: No prompts loaded.")
        return

    # ── Build job list ──
    seeds = [args.start_seed + i for i in range(args.seeds)]
    jobs = []

    for prompt_data in all_prompts:
        category = prompt_data.get("category", "unknown")
        lane = prompt_data.get("lane", "unknown")
        wave = prompt_data.get("wave", 0)
        idx = prompt_data.get("index", 0)
        prompt_text = prompt_data["prompt"]

        for seed in seeds:
            job_key = f"w{wave}_{category}_{idx:03d}_s{seed}"
            filename = f"{OUTPUT_PREFIX}/w{wave}/{lane}/{category}/{idx:03d}_s{seed}"
            jobs.append({
                "key": job_key,
                "prompt": prompt_text,
                "seed": seed,
                "filename": filename,
                "category": category,
                "lane": lane,
                "wave": wave,
            })

    print(f"\nTotal jobs: {len(jobs)} ({len(all_prompts)} prompts × {args.seeds} seeds)")
    print(f"Seeds: {seeds}")
    print(f"Output: /workspace/outputs/{OUTPUT_PREFIX}/")

    # Category breakdown
    cat_counts = {}
    for j in jobs:
        cat = f"[w{j['wave']}] {j['category']}"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print("\nJobs per category:")
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat}: {count}")

    # ── Resume check ──
    completed = set()
    if args.resume:
        completed = load_progress()
        remaining = len(jobs) - len([j for j in jobs if j["key"] in completed])
        print(f"\nResume: {len(completed)} completed, {remaining} remaining")

    # ── Dry run ──
    if args.dry_run:
        print("\n--- DRY RUN (first 5 jobs) ---\n")
        for j in jobs[:5]:
            print(f"  {j['key']}")
            print(f"    prompt: {j['prompt'][:80]}...")
            print(f"    seed: {j['seed']}")
            print(f"    file: {j['filename']}")
            print()

        est_seconds = len(jobs) * 25  # ~25 sec per image estimate
        est_hours = est_seconds / 3600
        print(f"Estimated time: ~{est_hours:.1f} hours ({len(jobs)} images × ~25 sec/image)")
        print("\nRemove --dry-run to start generation.")
        return

    # ── Check ComfyUI ──
    print("\nChecking ComfyUI...")
    if not check_comfyui():
        print("ERROR: ComfyUI is not running. Start it first.")
        return

    # ── Generate ──
    print(f"\n{'=' * 70}")
    print("STARTING GENERATION")
    print(f"{'=' * 70}\n")

    start_time = time.time()
    success_count = 0
    fail_count = 0

    for i, job in enumerate(jobs):
        if job["key"] in completed:
            continue

        elapsed = time.time() - start_time
        done = success_count + fail_count
        if done > 0:
            avg_time = elapsed / done
            remaining = (len(jobs) - len(completed) - done) * avg_time
            eta = f" | ETA: {remaining/60:.0f}min"
        else:
            eta = ""

        print(f"[{i+1}/{len(jobs)}] {job['key']}{eta}")

        try:
            wf = modify_workflow(workflow_template, job["prompt"], job["seed"], job["filename"])
            prompt_id = queue_prompt(wf)
            success = wait_for_completion(prompt_id, timeout=args.timeout)

            if success:
                completed.add(job["key"])
                success_count += 1
                print(f"    ✓ done ({success_count} total)")
            else:
                fail_count += 1
                print(f"    ✗ failed")

        except Exception as e:
            fail_count += 1
            print(f"    ✗ error: {e}")

        # Save progress every 10 jobs
        if (success_count + fail_count) % 10 == 0:
            save_progress(completed)

    # ── Final save ──
    save_progress(completed)

    total_time = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"DONE in {total_time/60:.1f} minutes")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")
    print(f"  Skipped: {len(completed) - success_count} (already done)")
    print(f"  Output:  /workspace/outputs/{OUTPUT_PREFIX}/")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
