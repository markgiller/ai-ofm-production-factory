#!/usr/bin/env python3
# scripts/verify_comfyui.py
#
# End-to-end smoke test for ComfyUI headless API.
# Two modes:
#   --model-free  (default) EmptyImage → SaveImage. Proves API works, no models needed.
#   --flux        FLUX.2-klein full pipeline. Proves image generation works end-to-end.
#
# Checks:
#   1. /system_stats — ComfyUI is up, GPU visible
#   2. POST /prompt  — workflow accepted (prompt_id returned)
#   3. Poll /queue   — job leaves queue
#   4. GET /history  — job completed without error
#   5. Output file   — at least one image produced
#
# Exit 0 = all checks pass. Exit 1 = failure.
#
# Usage:
#   export COMFYUI_URL=https://<pod-id>-8188.proxy.runpod.net
#   python3 scripts/verify_comfyui.py              # model-free API test
#   python3 scripts/verify_comfyui.py --flux        # FLUX.2 generation test
#
# Options:
#   --flux         use FLUX.2-klein workflow (requires models on volume)
#   --model-free   use EmptyImage workflow (default, no models needed)
#   --steps N      KSampler steps (default: 4)
#   --width W      image width  (default: 512 model-free, 576 flux)
#   --height H     image height (default: 512 model-free, 1024 flux)
#   --timeout T    max seconds to wait for job (default: 300)

import argparse
import json
import sys
import time
import uuid
import os

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


# ── Workflow builders ────────────────────────────────────────────────────────

def build_model_free_workflow(width: int, height: int) -> dict:
    """
    Model-free pipeline: EmptyImage → SaveImage.
    Proves ComfyUI API accepts JSON + executes. No models needed.
    Phase 1 API gate.
    """
    return {
        "1": {
            "class_type": "EmptyImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
                "color": 0
            }
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["1", 0],
                "filename_prefix": "verify_test"
            }
        }
    }


def build_flux_workflow(steps: int, width: int, height: int, seed: int) -> dict:
    """
    FLUX.2-klein full pipeline. Proves image generation works end-to-end.
    Requires 3 model files on the volume:
      models/diffusion_models/flux-2-klein-4b.safetensors
      models/text_encoders/qwen_3_4b.safetensors
      models/vae/flux2-vae.safetensors

    Pipeline: UNETLoader + CLIPLoader + VAELoader →
              CLIPTextEncode → CFGGuider →
              EmptyFlux2LatentImage + Flux2Scheduler + KSamplerSelect + RandomNoise →
              SamplerCustomAdvanced → VAEDecode → SaveImage
    """
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux-2-klein-4b.safetensors",
                "weight_dtype": "default"
            }
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "flux2"
            }
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "flux2-vae.safetensors"
            }
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "A photorealistic portrait of a woman with soft studio lighting, looking directly at the camera, shallow depth of field, editorial photography",
                "clip": ["2", 0]
            }
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "",
                "clip": ["2", 0]
            }
        },
        "6": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "cfg": 1.0
            }
        },
        "7": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1
            }
        },
        "8": {
            "class_type": "Flux2Scheduler",
            "inputs": {
                "steps": steps,
                "width": width,
                "height": height
            }
        },
        "9": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler"
            }
        },
        "10": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": seed
            }
        },
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["6", 0],
                "sampler": ["9", 0],
                "sigmas": ["8", 0],
                "latent_image": ["7", 0]
            }
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["11", 0],
                "vae": ["3", 0]
            }
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["12", 0],
                "filename_prefix": "flux2_klein_verify"
            }
        }
    }


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "✓" if ok else "✗"
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return ok


def main():
    parser = argparse.ArgumentParser(description="ComfyUI end-to-end smoke test")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--flux", action="store_true",
                            help="FLUX.2-klein full pipeline (requires models)")
    mode_group.add_argument("--model-free", action="store_true", default=True,
                            help="EmptyImage test, no models needed (default)")
    parser.add_argument("--steps",   type=int, default=None, help="Steps (default: 4)")
    parser.add_argument("--width",   type=int, default=None, help="Image width")
    parser.add_argument("--height",  type=int, default=None, help="Image height")
    parser.add_argument("--timeout", type=int, default=300,  help="Max wait seconds (default: 300)")
    args = parser.parse_args()

    # Set defaults based on mode
    if args.flux:
        args.steps = args.steps or 4
        args.width = args.width or 576
        args.height = args.height or 1024
    else:
        args.steps = args.steps or 4
        args.width = args.width or 512
        args.height = args.height or 512

    base_url = os.environ.get("COMFYUI_URL", "").rstrip("/")
    if not base_url:
        print("Error: COMFYUI_URL not set.")
        print("  export COMFYUI_URL=https://<pod-id>-8188.proxy.runpod.net")
        sys.exit(1)

    seed = int(uuid.uuid4()) % (2**32)
    mode_name = "FLUX.2-klein" if args.flux else "model-free"
    results = []

    print(f"\n[comfyui] {base_url}")
    print(f"          mode={mode_name} steps={args.steps} size={args.width}x{args.height} seed={seed}")

    # ── 1. /system_stats ──────────────────────────────────────────────────────
    print("\n[1/5] system_stats...")
    try:
        r = requests.get(f"{base_url}/system_stats", timeout=15)
        data = r.json()
        devices = data.get("devices", [])
        gpu_info = devices[0]["name"] if devices else "no GPU device listed"
        results.append(check("ComfyUI up", r.status_code == 200, gpu_info))
    except Exception as e:
        results.append(check("ComfyUI up", False, str(e)))
        print("\n✗ Cannot reach ComfyUI. Is the pod running and URL correct?")
        sys.exit(1)

    # ── 2. POST /prompt ───────────────────────────────────────────────────────
    print("\n[2/5] submitting workflow...")
    if args.flux:
        workflow = build_flux_workflow(args.steps, args.width, args.height, seed)
    else:
        workflow = build_model_free_workflow(args.width, args.height)
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}

    try:
        r = requests.post(f"{base_url}/prompt", json=payload, timeout=30)
        body = r.json()
        prompt_id = body.get("prompt_id")
        ok = r.status_code == 200 and bool(prompt_id)
        results.append(check("workflow accepted", ok, f"prompt_id={prompt_id}"))
        if not ok:
            print(f"  Server response: {body}")
            sys.exit(1)
    except Exception as e:
        results.append(check("workflow accepted", False, str(e)))
        sys.exit(1)

    # ── 3. Poll /queue until job leaves ───────────────────────────────────────
    print(f"\n[3/5] waiting for job to complete (timeout={args.timeout}s)...")
    deadline = time.time() + args.timeout
    in_queue = True
    dot_count = 0

    while time.time() < deadline:
        try:
            q = requests.get(f"{base_url}/queue", timeout=10).json()
            running = q.get("queue_running", [])
            pending = q.get("queue_pending", [])
            ids_active = [item[1] for item in running + pending]
            if prompt_id not in ids_active:
                in_queue = False
                break
        except Exception:
            pass
        time.sleep(3)
        dot_count += 1
        if dot_count % 5 == 0:
            elapsed = int(time.time() - (deadline - args.timeout))
            print(f"    ... {elapsed}s elapsed")

    results.append(check("job left queue", not in_queue,
                         "timeout — job may still be running" if in_queue else ""))
    if in_queue:
        print("\n✗ Job did not complete within timeout. Increase --timeout or check pod logs.")
        sys.exit(1)

    # ── 4. GET /history — check for errors ────────────────────────────────────
    print("\n[4/5] checking history...")
    try:
        h = requests.get(f"{base_url}/history/{prompt_id}", timeout=15).json()
        job = h.get(prompt_id, {})
        outputs = job.get("outputs", {})
        status_node = job.get("status", {})
        completed = status_node.get("completed", False)
        errors = [
            msg for msgs in status_node.get("messages", [])
            for msg in ([msgs] if isinstance(msgs, str) else msgs)
            if "error" in str(msg).lower()
        ]
        results.append(check("job completed", completed,
                             f"errors: {errors}" if errors else ""))
    except Exception as e:
        results.append(check("history check", False, str(e)))

    # ── 5. Output files ───────────────────────────────────────────────────────
    print("\n[5/5] checking outputs...")
    try:
        # outputs dict: node_id → {images: [{filename, subfolder, type}]}
        image_count = sum(
            len(v.get("images", []))
            for v in outputs.values()
            if isinstance(v, dict)
        )
        first = None
        for v in outputs.values():
            imgs = v.get("images", []) if isinstance(v, dict) else []
            if imgs:
                first = imgs[0].get("filename", "")
                break
        results.append(check("output produced", image_count > 0,
                             first or "no filename"))
    except Exception as e:
        results.append(check("output produced", False, str(e)))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"  {passed}/{total} checks passed")

    if all(results):
        if args.flux:
            print("\nFLUX.2-klein pipeline OK. Image generation: PASS.")
            print("Phase 2 — FLUX integration: COMPLETE.")
        else:
            print("\nComfyUI API layer OK. Runtime gate: PASS.")
            print("Phase 1 — Skeleton: COMPLETE.")
        sys.exit(0)
    else:
        print("\nSome checks failed. See details above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
