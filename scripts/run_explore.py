#!/usr/bin/env python3
"""
IMG Explore — generate variations to find winning compositions.

Sends the same prompt with different seeds to ComfyUI and collects results
into a contact sheet + results.json for easy selection.

Usage:
    python scripts/run_explore.py \\
        --prompt "woman, 25yo, brown hair, soft studio lighting, looking at camera" \\
        --count 20 --format 4:5

Requires:
    - ComfyUI running (set COMFYUI_URL env var or use --comfyui-url)
    - FLUX.2-klein-4B models on the volume
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

WORKFLOW_TEMPLATE = Path(__file__).resolve().parent.parent / "workflows" / "explore" / "IMG_explore_v001.json"


# ── Workflow injection ────────────────────────────────────────────────────────

def load_workflow() -> dict:
    """Load the explore workflow template."""
    with open(WORKFLOW_TEMPLATE, "r") as f:
        return json.load(f)


def inject_params(workflow: dict, prompt: str, width: int, height: int, seed: int, prefix: str) -> dict:
    """Inject parameters into a copy of the workflow template."""
    wf = copy.deepcopy(workflow)
    wf["4"]["inputs"]["text"] = prompt          # positive prompt
    wf["7"]["inputs"]["width"] = width          # EmptyFlux2LatentImage
    wf["7"]["inputs"]["height"] = height
    wf["8"]["inputs"]["width"] = width          # Flux2Scheduler
    wf["8"]["inputs"]["height"] = height
    wf["10"]["inputs"]["noise_seed"] = seed     # RandomNoise
    wf["13"]["inputs"]["filename_prefix"] = prefix  # SaveImage
    return wf


# ── ComfyUI API ───────────────────────────────────────────────────────────────

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
) -> dict:
    """Core explore function. Returns results dict."""

    width, height = FORMATS[fmt]
    fmt_label = fmt.replace(":", "x")
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = output_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Load workflow template
    template = load_workflow()

    print(f"[explore] Session: {session_id}")
    print(f"[explore] Prompt: \"{prompt[:80]}{'...' if len(prompt) > 80 else ''}\"")
    print(f"[explore] Config: {width}x{height} ({fmt}), 4 steps, CFG 1.0")
    print(f"[explore] Generating {count} images...\n")

    results = []
    image_paths = []
    success_seeds = []
    times = []

    for i in range(count):
        seed = seed_start + i
        filename = f"explore_{fmt_label}_seed{seed}.png"
        save_path = session_dir / filename

        t0 = time.time()
        status = "ok"
        gen_time = None

        try:
            wf = inject_params(template, prompt, width, height, seed, f"explore_{fmt_label}_{seed}")
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
        "prompt": prompt,
        "format": fmt,
        "size": f"{width}x{height}",
        "model": "flux2_klein_4b",
        "steps": 4,
        "cfg": 1.0,
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

    # Default seed
    seed_start = args.seed if args.seed is not None else random.randint(1000, 999999)

    run_explore(
        prompt=args.prompt,
        count=args.count,
        fmt=args.format,
        seed_start=seed_start,
        base_url=base_url,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
