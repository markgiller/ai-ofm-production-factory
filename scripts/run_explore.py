#!/usr/bin/env python3
"""
IMG Explore — generate variations to find winning compositions.

Sends the same prompt with different seeds to ComfyUI and collects results
into a contact sheet + results.json for easy selection.

Supports two model backends:
    flux2-klein  — FLUX.2 Klein 4B (legacy, v001/v002 workflows)
    flux1-dev    — FLUX.1 Dev 12B (v003 workflows, IP-Adapter support)

Usage:
    # FLUX.1 Dev text-only:
    python scripts/run_explore.py \\
        --prompt "woman, 25yo, soft studio lighting" \\
        --model flux1-dev --count 20

    # FLUX.1 Dev + IP-Adapter (identity bridge):
    python scripts/run_explore.py \\
        --prompt "close-up portrait, soft light" \\
        --model flux1-dev --ipadapter-ref /path/to/reference.png \\
        --ipadapter-strength 0.6 --count 50

    # Legacy FLUX.2 Klein:
    python scripts/run_explore.py \\
        --prompt "woman, looking at camera" --count 20

Requires:
    - ComfyUI running (set COMFYUI_URL env var or use --comfyui-url)
    - Model files on the volume (see docs/sops/lora_training_workflow.md)
    - requests, Pillow
"""

import argparse
import copy
import json
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    print("Warning: Pillow not installed. Contact sheet will be skipped.")
    print("  Install with: pip install Pillow")


# ── Format presets ────────────────────────────────────────────────────────────

FORMATS = {
    "9:16": (576, 1024),
    "4:5":  (576, 720),
    "1:1":  (576, 576),
    "16:9": (1024, 576),
    "3:4":  (576, 768),
    "2:3":  (576, 864),
}

_WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows" / "explore"
WORKFLOW_TEMPLATE = _WORKFLOWS_DIR / "IMG_explore_v001.json"
WORKFLOW_TEMPLATE_V002 = _WORKFLOWS_DIR / "IMG_explore_v002.json"
WORKFLOW_TEMPLATE_V002_BASE = _WORKFLOWS_DIR / "IMG_explore_v002_base.json"
WORKFLOW_TEMPLATE_V003 = _WORKFLOWS_DIR / "IMG_explore_v003.json"
WORKFLOW_TEMPLATE_V003_IPA = _WORKFLOWS_DIR / "IMG_explore_v003_ipadapter.json"


# ── Workflow injection ────────────────────────────────────────────────────────

def load_workflow(version: str = "v001") -> dict:
    """Load the explore workflow template by version."""
    paths = {
        "v001": WORKFLOW_TEMPLATE,
        "v002": WORKFLOW_TEMPLATE_V002,
        "v002_base": WORKFLOW_TEMPLATE_V002_BASE,
        "v003": WORKFLOW_TEMPLATE_V003,
        "v003_ipadapter": WORKFLOW_TEMPLATE_V003_IPA,
    }
    path = paths.get(version)
    if path is None or not path.exists():
        raise FileNotFoundError(f"Workflow template not found: {version} ({path})")
    with open(path, "r") as f:
        return json.load(f)


def inject_params(workflow: dict, prompt: str, width: int, height: int, seed: int, prefix: str) -> dict:
    """Inject parameters into a copy of the v001 workflow template (Mode A)."""
    wf = copy.deepcopy(workflow)
    wf["4"]["inputs"]["text"] = prompt          # positive prompt
    wf["7"]["inputs"]["width"] = width          # EmptyFlux2LatentImage
    wf["7"]["inputs"]["height"] = height
    wf["8"]["inputs"]["width"] = width          # Flux2Scheduler
    wf["8"]["inputs"]["height"] = height
    wf["10"]["inputs"]["noise_seed"] = seed     # RandomNoise
    wf["13"]["inputs"]["filename_prefix"] = prefix  # SaveImage
    return wf


def inject_params_v002(workflow: dict, prompt: str, width: int, height: int,
                       seed: int, prefix: str, lora_name: str,
                       lora_strength: float) -> dict:
    """Inject parameters into a copy of the v002 workflow template (Mode B with LoRA)."""
    wf = copy.deepcopy(workflow)
    wf["4"]["inputs"]["text"] = prompt
    wf["7"]["inputs"]["width"] = width
    wf["7"]["inputs"]["height"] = height
    wf["8"]["inputs"]["width"] = width
    wf["8"]["inputs"]["height"] = height
    wf["10"]["inputs"]["noise_seed"] = seed
    wf["13"]["inputs"]["filename_prefix"] = prefix
    wf["14"]["inputs"]["lora_name"] = lora_name
    wf["14"]["inputs"]["strength_model"] = lora_strength
    wf["14"]["inputs"]["strength_clip"] = lora_strength
    return wf


def inject_params_v003(workflow: dict, prompt: str, width: int, height: int,
                       seed: int, prefix: str) -> dict:
    """Inject parameters into a v003 FLUX.1 Dev workflow (text-only)."""
    wf = copy.deepcopy(workflow)
    wf["4"]["inputs"]["text"] = prompt          # CLIPTextEncode
    wf["7"]["inputs"]["width"] = width          # EmptyLatentImage
    wf["7"]["inputs"]["height"] = height
    wf["10"]["inputs"]["noise_seed"] = seed     # RandomNoise
    wf["13"]["inputs"]["filename_prefix"] = prefix  # SaveImage
    return wf


def inject_params_v003_ipadapter(workflow: dict, prompt: str, width: int,
                                 height: int, seed: int, prefix: str,
                                 ref_filename: str,
                                 ipadapter_strength: float) -> dict:
    """Inject parameters into a v003 FLUX.1 Dev + IP-Adapter workflow."""
    wf = inject_params_v003(workflow, prompt, width, height, seed, prefix)
    wf["15"]["inputs"]["image"] = ref_filename        # LoadImage
    wf["17"]["inputs"]["weight"] = ipadapter_strength  # ApplyIPAdapterFlux
    return wf


# ── ComfyUI API ───────────────────────────────────────────────────────────────

def upload_image(base_url: str, image_path: str) -> str:
    """Upload an image to ComfyUI input directory. Returns the stored filename."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    with open(path, "rb") as f:
        r = requests.post(
            f"{base_url}/upload/image",
            files={"image": (path.name, f, "image/png")},
            timeout=30,
        )
    if r.status_code != 200:
        raise RuntimeError(f"Failed to upload image: HTTP {r.status_code}")
    return r.json()["name"]


def submit_prompt(base_url: str, workflow: dict) -> str:
    """POST workflow to ComfyUI, return prompt_id."""
    payload = {"prompt": workflow}
    r = requests.post(f"{base_url}/prompt", json=payload, timeout=30)
    body = r.json()
    if r.status_code != 200 or "prompt_id" not in body:
        raise RuntimeError(f"ComfyUI rejected workflow: {body}")
    return body["prompt_id"]


def wait_for_completion(base_url: str, prompt_id: str, timeout: int = 300) -> None:
    """Poll /queue until the job leaves."""
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
        raise RuntimeError(f"Job not completed: {status}")

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
    save_path.write_bytes(r.content)


# ── Contact sheet ─────────────────────────────────────────────────────────────

def build_contact_sheet(image_paths: list, seeds: list, output_path: Path,
                        thumb_width: int = 200, columns: int = 5,
                        padding: int = 10, label_height: int = 20) -> None:
    """Build a grid contact sheet from generated images with seed labels."""
    if Image is None:
        return

    if not image_paths:
        return

    # Auto-adjust columns for small batches
    columns = min(columns, len(image_paths))
    rows = (len(image_paths) + columns - 1) // columns

    # Load first image to get aspect ratio
    with Image.open(image_paths[0]) as sample:
        aspect = sample.height / sample.width
    thumb_height = int(thumb_width * aspect)

    cell_w = thumb_width + padding
    cell_h = thumb_height + label_height + padding
    sheet_w = columns * cell_w + padding
    sheet_h = rows * cell_h + padding

    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)

    # Try to load a font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for i, (img_path, seed) in enumerate(zip(image_paths, seeds)):
        col = i % columns
        row = i // columns
        x = padding + col * cell_w
        y = padding + row * cell_h

        try:
            with Image.open(img_path) as img:
                thumb = img.resize((thumb_width, thumb_height), Image.LANCZOS)
                sheet.paste(thumb, (x, y))
        except Exception:
            # Draw placeholder for failed images
            draw.rectangle([x, y, x + thumb_width, y + thumb_height], fill="#eeeeee")

        # Seed label centered below thumbnail
        label = f"seed={seed}"
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = x + (thumb_width - text_w) // 2
        text_y = y + thumb_height + 2
        draw.text((text_x, text_y), label, fill="black", font=font)

    sheet.save(output_path, quality=95)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_explore(
    prompt: str,
    count: int,
    fmt: str,
    seed_start: int,
    base_url: str,
    output_dir: Path,
    lora: Optional[str] = None,
    lora_strength: float = 0.8,
    base_model: bool = False,
    model: str = "flux2-klein",
    ipadapter_ref: Optional[str] = None,
    ipadapter_strength: float = 0.6,
) -> dict:
    """Core explore function. Returns results dict."""

    width, height = FORMATS[fmt]
    fmt_label = fmt.replace(":", "x")
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = output_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Upload IP-Adapter reference image if provided
    ref_filename = None
    if ipadapter_ref:
        print(f"[explore] Uploading IP-Adapter reference: {ipadapter_ref}")
        ref_filename = upload_image(base_url, ipadapter_ref)
        print(f"[explore] Reference uploaded as: {ref_filename}")

    # Select workflow based on model backend
    if model == "flux1-dev":
        if ipadapter_ref:
            version = "v003_ipadapter"
            mode_label = "C_ipadapter"
            prefix_tag = "explore_ipa"
        else:
            version = "v003"
            mode_label = "A_text"
            prefix_tag = "explore"
        template = load_workflow(version)
        steps = 20
        guidance = 3.5
        model_name = "flux1_dev_12b"
    else:
        # Legacy FLUX.2 Klein
        mode_b = lora is not None
        if mode_b:
            version = "v002_base" if base_model else "v002"
            template = load_workflow(version)
            steps = 20 if base_model else 4
            guidance = 4.0 if base_model else 1.0
            mode_label = "B_identity"
            prefix_tag = "explore_b"
        else:
            template = load_workflow("v001")
            steps = 4
            guidance = 1.0
            mode_label = "A_text"
            prefix_tag = "explore"
        model_name = "flux2_klein_4b"

    print(f"[explore] Session: {session_id}")
    print(f"[explore] Model: {model_name} ({version})")
    if ipadapter_ref:
        print(f"[explore] Mode C: IP-Adapter identity (ref={Path(ipadapter_ref).name}, strength={ipadapter_strength})")
    elif lora and model == "flux2-klein":
        model_tag = "BASE" if base_model else "distilled"
        print(f"[explore] Mode B: LoRA identity-locked ({lora}, strength={lora_strength}, {model_tag})")
    else:
        print(f"[explore] Mode A: text-only explore")
    print(f"[explore] Prompt: \"{prompt[:80]}{'...' if len(prompt) > 80 else ''}\"")
    print(f"[explore] Config: {width}x{height} ({fmt}), {steps} steps, guidance {guidance}")
    print(f"[explore] Generating {count} images...\n")

    results = []
    image_paths = []
    success_seeds = []
    times = []

    for i in range(count):
        seed = seed_start + i
        filename = f"{prefix_tag}_{fmt_label}_seed{seed}.png"
        save_path = session_dir / filename

        t0 = time.time()
        status = "ok"
        gen_time = None

        try:
            prefix_str = f"{prefix_tag}_{fmt_label}_{seed}"
            if model == "flux1-dev":
                if ipadapter_ref:
                    wf = inject_params_v003_ipadapter(
                        template, prompt, width, height, seed, prefix_str,
                        ref_filename, ipadapter_strength)
                else:
                    wf = inject_params_v003(
                        template, prompt, width, height, seed, prefix_str)
            elif lora is not None:
                wf = inject_params_v002(template, prompt, width, height, seed,
                                        prefix_str, lora, lora_strength)
            else:
                wf = inject_params(template, prompt, width, height, seed,
                                   prefix_str)
            prompt_id = submit_prompt(base_url, wf)
            wait_for_completion(base_url, prompt_id, timeout=300)
            output_name = get_output_filename(base_url, prompt_id)
            download_image(base_url, output_name, save_path)
            gen_time = round(time.time() - t0, 1)
            times.append(gen_time)
            image_paths.append(save_path)
            success_seeds.append(seed)
        except KeyboardInterrupt:
            print(f"\n\n[explore] Interrupted at [{i + 1}/{count}]. Saving progress...")
            break
        except Exception as e:
            gen_time = round(time.time() - t0, 1)
            status = f"error: {e}"

        results.append({
            "seed": seed,
            "file": filename if status == "ok" else None,
            "time_sec": gen_time,
            "status": status,
            "selected": False,
        })

        # Progress line
        eta_str = ""
        if len(times) >= 3:
            avg = sum(times) / len(times)
            remaining = count - (i + 1)
            eta_min = int(avg * remaining / 60)
            eta_str = f"   ETA: ~{eta_min} min"

        mark = "\u2713" if status == "ok" else "\u2717"
        time_str = f"{gen_time}s" if gen_time else "---"
        print(f"  [{i + 1}/{count}]  seed={seed}  {mark}  {time_str}{eta_str}")

    # Summary
    succeeded = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - succeeded
    total_time = sum(t for t in times)

    # Build contact sheet
    contact_sheet_name = "contact_sheet.png"
    contact_sheet_path = session_dir / contact_sheet_name
    if image_paths:
        build_contact_sheet(image_paths, success_seeds, contact_sheet_path)

    # Build results JSON
    results_data = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode_label,
        "prompt": prompt,
        "format": fmt,
        "size": f"{width}x{height}",
        "model": model_name,
        "model_variant": "base" if (model == "flux2-klein" and base_model) else None,
        "steps": steps,
        "guidance": guidance,
        "lora": lora,
        "lora_strength": lora_strength if lora else None,
        "ipadapter_ref": ipadapter_ref,
        "ipadapter_strength": ipadapter_strength if ipadapter_ref else None,
        "results": results,
        "contact_sheet": contact_sheet_name if image_paths else None,
        "succeeded": succeeded,
        "failed": failed,
        "total_requested": count,
        "total_time_sec": round(total_time, 1),
    }

    results_path = session_dir / "results.json"
    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)

    # Print summary
    total_min = int(total_time // 60)
    total_sec = int(total_time % 60)
    print(f"\n[explore] Done: {succeeded} ok, {failed} failed ({total_min}m {total_sec:02d}s)")
    if image_paths:
        print(f"[explore] Contact sheet \u2192 {contact_sheet_path}")
    print(f"[explore] Results       \u2192 {results_path}")

    return results_data


def cleanup_old_sessions(output_dir: Path, days: int) -> None:
    """Remove explore sessions older than N days."""
    if not output_dir.exists():
        return

    cutoff = time.time() - (days * 86400)
    removed = 0

    for entry in sorted(output_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Session dirs are named YYYYMMDD_HHMMSS
        try:
            session_time = datetime.strptime(entry.name, "%Y%m%d_%H%M%S").timestamp()
            if session_time < cutoff:
                import shutil
                shutil.rmtree(entry)
                removed += 1
        except ValueError:
            continue

    if removed:
        print(f"[explore] Cleaned up {removed} session(s) older than {days} days")


def main():
    parser = argparse.ArgumentParser(
        description="IMG Explore \u2014 generate variations to find winning compositions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prompt tips:
  Structure: [who] [features] [action/pose] [setting] [lighting] [camera] [mood]
  Example:   "woman, 25yo, brown hair, sitting on couch, soft window light,
              shot on iPhone, casual authentic feel"

  Specific > vague:  "85mm f/1.4" better than "nice photo"
  Front = priority:  most important details first

Formats:  9:16  4:5  1:1  16:9  3:4  2:3

Mode B (LoRA identity lock):
  %(prog)s --prompt "same girl, red dress, rooftop" --lora lora_lily_v001.safetensors --count 30
  %(prog)s --prompt "same girl, cozy bedroom" --lora lora_lily_v001.safetensors --base-model --count 30

  --lora-strength guide: 0.5=soft, 0.7=balanced, 0.8=production, 0.9=hard lock, 1.0=max

Examples:
  %(prog)s --prompt "woman, 25yo, soft studio lighting, looking at camera" --count 20
  %(prog)s --prompt "woman in red dress, golden hour, rooftop" --count 10 --format 4:5
  %(prog)s --cleanup 7    # remove sessions older than 7 days
""",
    )
    parser.add_argument("--prompt", type=str,
                        help="What to generate (required unless --cleanup)")
    parser.add_argument("--count", type=int, default=20,
                        help="Number of variations to generate (default: 20)")
    parser.add_argument("--format", type=str, default="9:16", choices=list(FORMATS.keys()),
                        help="Aspect ratio (default: 9:16)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Starting seed (default: random)")
    parser.add_argument("--output-dir", type=str, default="./explore_output",
                        help="Output directory (default: ./explore_output)")
    parser.add_argument("--comfyui-url", type=str, default=None,
                        help="ComfyUI API URL (default: from COMFYUI_URL env)")
    parser.add_argument("--model", type=str, default="flux2-klein",
                        choices=["flux2-klein", "flux1-dev"],
                        help="Model backend (default: flux2-klein)")
    parser.add_argument("--lora", type=str, default=None,
                        help="LoRA filename for Mode B identity lock (e.g. lora_lily_v001.safetensors)")
    parser.add_argument("--lora-strength", type=float, default=0.8,
                        help="LoRA strength 0.0-1.0 (default: 0.8)")
    parser.add_argument("--base-model", action="store_true",
                        help="[flux2-klein only] Use BASE model (20 steps, CFG 4.0) instead of distilled")
    parser.add_argument("--ipadapter-ref", type=str, default=None,
                        help="[flux1-dev] Reference face image for IP-Adapter identity guidance")
    parser.add_argument("--ipadapter-strength", type=float, default=0.6,
                        help="[flux1-dev] IP-Adapter strength 0.0-1.0 (default: 0.6)")
    parser.add_argument("--cleanup", type=int, metavar="DAYS",
                        help="Remove explore sessions older than N days and exit")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Cleanup mode
    if args.cleanup is not None:
        cleanup_old_sessions(output_dir, args.cleanup)
        return

    # Require prompt for generation
    if not args.prompt:
        parser.error("--prompt is required")

    # Resolve ComfyUI URL
    base_url = args.comfyui_url or os.environ.get("COMFYUI_URL", "")
    base_url = base_url.rstrip("/")
    if not base_url:
        print("Error: ComfyUI URL not set.")
        print("  export COMFYUI_URL=https://<pod-id>-8188.proxy.runpod.net")
        print("  or use --comfyui-url")
        sys.exit(1)

    # Verify ComfyUI is reachable
    try:
        r = requests.get(f"{base_url}/system_stats", timeout=10)
        if r.status_code != 200:
            raise ConnectionError(f"HTTP {r.status_code}")
    except Exception as e:
        print(f"Error: Cannot reach ComfyUI at {base_url}")
        print(f"  {e}")
        sys.exit(1)

    # Validate flag combinations
    if args.base_model and args.model != "flux2-klein":
        print("Warning: --base-model only applies to flux2-klein, ignoring")
    if args.base_model and not args.lora:
        print("Warning: --base-model has no effect without --lora (Mode A always uses distilled)")
    if args.ipadapter_ref and args.model != "flux1-dev":
        print("Warning: --ipadapter-ref requires --model flux1-dev, switching to flux1-dev")
        args.model = "flux1-dev"

    # Default seed
    seed_start = args.seed if args.seed is not None else random.randint(1000, 999999)

    run_explore(
        prompt=args.prompt,
        count=args.count,
        fmt=args.format,
        seed_start=seed_start,
        base_url=base_url,
        output_dir=output_dir,
        lora=args.lora,
        lora_strength=args.lora_strength,
        base_model=args.base_model,
        model=args.model,
        ipadapter_ref=args.ipadapter_ref,
        ipadapter_strength=args.ipadapter_strength,
    )


if __name__ == "__main__":
    main()
