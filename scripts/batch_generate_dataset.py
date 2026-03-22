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

# Prompt file search paths (checked in order)
WORKFLOW_API_FILE = WORKSPACE / "user/default/workflows/Character_Chroma.json"

# Prompt file search paths (checked in order)
PROMPT_SEARCH_PATHS = [
    WORKSPACE / "ai-ofm-production-factory/creative/prompts",
    WORKSPACE / "repo/creative/prompts",
    WORKSPACE / "creative/prompts",
    Path(__file__).parent.parent / "creative" / "prompts",
]

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


# ─── UI → API Format Converter ────────────────────────────────────────────────

def convert_ui_to_api(ui_workflow: dict) -> dict:
    """Convert ComfyUI UI-format workflow to API format.

    Uses /object_info from a running ComfyUI instance to map widget values
    to parameter names. Falls back to embedded workflow if ComfyUI unreachable.
    """
    # Check if it's already API format (no "nodes" key, has string node IDs)
    if "nodes" not in ui_workflow and all(isinstance(v, dict) for v in ui_workflow.values()):
        return ui_workflow

    # Build link lookup: link_id → (source_node_id, source_output_slot)
    links = {}
    for link in ui_workflow.get("links", []):
        link_id = link[0]
        source_node = link[1]
        source_slot = link[2]
        links[link_id] = (str(source_node), source_slot)

    # Get node definitions from ComfyUI
    node_info = {}
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/object_info", timeout=10) as resp:
            node_info = json.loads(resp.read())
    except Exception:
        print("  WARNING: Cannot reach ComfyUI for node info — using embedded workflow")
        return get_embedded_workflow()

    api = {}
    for node in ui_workflow.get("nodes", []):
        node_id = str(node["id"])
        node_type = node["type"]

        # Skip muted/bypassed nodes (mode 4 = muted, mode 2 = bypassed)
        if node.get("mode", 0) in (2, 4):
            continue

        entry = {"class_type": node_type, "inputs": {}}

        # Get input definitions from object_info
        info = node_info.get(node_type, {})
        required = info.get("input", {}).get("required", {})
        optional = info.get("input", {}).get("optional", {})
        all_inputs = {**required, **optional}

        # Map connected inputs
        connected_names = set()
        for inp in node.get("inputs", []):
            inp_name = inp["name"]
            link_id = inp.get("link")
            if link_id is not None and link_id in links:
                src_node, src_slot = links[link_id]
                entry["inputs"][inp_name] = [src_node, src_slot]
                connected_names.add(inp_name)

        # Map widget values to remaining input names
        widget_names = [name for name in all_inputs if name not in connected_names]
        widgets = node.get("widgets_values", [])
        wi = 0
        for wname in widget_names:
            if wi < len(widgets):
                entry["inputs"][wname] = widgets[wi]
                wi += 1

        api[node_id] = entry

    return api


def get_embedded_workflow() -> dict:
    """Return the Character_Chroma workflow in API format (hardcoded fallback)."""
    return {
        "58": {"class_type": "LoadImage", "inputs": {"image": "05.png"}},
        "172": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "178": {"class_type": "SaveImage", "inputs": {"filename_prefix": "lily_v002_dataset/output", "images": ["477", 0]}},
        "204": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_2s"}},
        "206": {"class_type": "CFGGuider", "inputs": {"cfg": 3.2, "model": ["429", 0], "positive": ["425", 0], "negative": ["370", 0]}},
        "207": {"class_type": "RandomNoise", "inputs": {"noise_seed": 100500}},
        "208": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["207", 0], "guider": ["433", 0], "sampler": ["204", 0], "sigmas": ["484", 0], "latent_image": ["479", 0]}},
        "251": {"class_type": "ttN text", "inputs": {"text": "placeholder"}},
        "364": {"class_type": "CLIPTextEncode", "inputs": {"text": ["251", 0], "clip": ["367", 0]}},
        "366": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "chroma", "device": "default"}},
        "367": {"class_type": "T5TokenizerOptions", "inputs": {"min_padding": 1, "min_length": 0, "clip": ["366", 0]}},
        "370": {"class_type": "CLIPTextEncode", "inputs": {"text": ["468", 0], "clip": ["367", 0]}},
        "385": {"class_type": "ApplyPulidFlux", "inputs": {"weight": 1, "start_at": 0, "end_at": 0.55, "fusion": "train_weight", "fusion_weight_max": 1, "fusion_weight_min": 0, "train_step": 8000, "use_gray": True, "model": ["482", 0], "pulid_flux": ["386", 0], "eva_clip": ["391", 0], "face_analysis": ["392", 0], "image": ["58", 0], "prior_image": ["58", 0]}},
        "386": {"class_type": "PulidFluxModelLoader", "inputs": {"pulid_file": "pulid_flux_v0.9.0.safetensors"}},
        "391": {"class_type": "PulidFluxEvaClipLoader", "inputs": {}},
        "392": {"class_type": "PulidFluxInsightFaceLoader", "inputs": {"provider": "CPU"}},
        "425": {"class_type": "unCLIPConditioning", "inputs": {"strength": 10, "noise_augmentation": 0, "conditioning": ["364", 0], "clip_vision_output": ["426", 0]}},
        "426": {"class_type": "CLIPVisionEncode", "inputs": {"crop": "none", "clip_vision": ["436", 0], "image": ["439", 0]}},
        "429": {"class_type": "ModelSamplingFlux", "inputs": {"max_shift": 1, "base_shift": 0.5, "width": 768, "height": 1024, "model": ["385", 0]}},
        "433": {"class_type": "easy cleanGpuUsed", "inputs": {"anything": ["206", 0]}},
        "436": {"class_type": "AdvancedVisionLoader", "inputs": {"clip_name": "siglip2-so400m-patch16-512.safetensors"}},
        "437": {"class_type": "easy imageRemBg", "inputs": {"rem_mode": "RMBG-1.4", "image_output": "Preview", "save_prefix": "ComfyUI", "torchscript_jit": False, "add_background": "none", "refine_foreground": False, "images": ["58", 0]}},
        "439": {"class_type": "PrepImageForClipVisionV2", "inputs": {"interpolation": "LANCZOS", "crop_position": "center", "sharpening": 0, "image": ["437", 0]}},
        "441": {"class_type": "PreviewImage", "inputs": {"images": ["439", 0]}},
        "468": {"class_type": "ttN text", "inputs": {"text": "placeholder negative"}},
        "469": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "Hyper-Chroma-low-step-LoRA.safetensors", "strength_model": 1.0, "model": ["481", 0]}},
        "477": {"class_type": "VAEDecode", "inputs": {"samples": ["208", 0], "vae": ["172", 0]}},
        "479": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
        "481": {"class_type": "UNETLoader", "inputs": {"unet_name": "Chroma1-HD.safetensors", "weight_dtype": "fp8_e4m3fn"}},
        "482": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "lora_lily_chroma_v001.safetensors", "strength_model": 1.5, "model": ["469", 0]}},
        "484": {"class_type": "SigmoidOffsetScheduler", "inputs": {"steps": 20, "square_k": 1, "base_c": 0.5, "model": ["429", 0]}},
    }


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
    if workflow_path.exists():
        with open(workflow_path) as f:
            raw = json.load(f)
        print(f"\nWorkflow: {workflow_path}")
        workflow_template = convert_ui_to_api(raw)
    else:
        print(f"\nWorkflow file not found: {workflow_path}")
        print("Using embedded Character_Chroma workflow")
        workflow_template = get_embedded_workflow()

    # Validate critical nodes exist
    for node_id, name in [(NODE_PROMPT, "prompt"), (NODE_SEED, "seed"), (NODE_SAVE, "save")]:
        if node_id not in workflow_template:
            print(f"ERROR: Node {node_id} ({name}) not found in workflow.")
            print(f"Available nodes: {list(workflow_template.keys())[:20]}...")
            return

    print(f"Nodes: {len(workflow_template)} | prompt={NODE_PROMPT}, negative={NODE_NEGATIVE}, seed={NODE_SEED}, save={NODE_SAVE}")

    # ── Load prompts ──
    waves = [int(w.strip()) for w in args.waves.split(",")]
    all_prompts = []

    wave_files = {
        1: "lily_v002_dataset_prompts.json",
        2: "lily_v002_dataset_prompts_wave2.json",
    }

    for wave_num in waves:
        fname = wave_files.get(wave_num)
        if not fname:
            print(f"WARNING: Unknown wave {wave_num}")
            continue

        # Search multiple paths
        path = None
        for search_dir in PROMPT_SEARCH_PATHS:
            candidate = search_dir / fname
            if candidate.exists():
                path = candidate
                break

        if not path:
            print(f"WARNING: Wave {wave_num} file '{fname}' not found in any search path")
            for sp in PROMPT_SEARCH_PATHS:
                print(f"  checked: {sp}")
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
