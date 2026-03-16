#!/usr/bin/env python3
"""
eval_arcface.py — Checkpoint Evaluation: ArcFace Scoring

Scores all generated images against reference images using ArcFace.
Supports aggregated reference embedding (mean of multiple refs) per our research:
  "Compare against aggregated reference embedding (mean of 5-20 clean refs), not single photo"

Setup (once per pod):
    apt-get update && apt-get install -y build-essential
    pip install insightface onnxruntime-gpu opencv-python-headless

Usage:
    # Single reference image:
    python eval_arcface.py --ref /workspace/lora_training/lily_v001/img/02.png

    # Aggregated reference (RECOMMENDED — uses mean of all faces in directory):
    python eval_arcface.py --ref-dir /workspace/lora_training/lily_v001/img

Output:
    /workspace/eval/lily_v001/arcface_results.csv
    /workspace/eval/lily_v001/checkpoint_summary.csv
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    from insightface.app import FaceAnalysis
except ImportError:
    print("Error: insightface not installed.")
    print("  Run: pip install insightface onnxruntime-gpu opencv-python-headless")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────
LORA_DIR   = Path("/workspace/lora_training/lily_v001/output/lora_lily_v001")
OUTPUT_DIR = Path("/workspace/eval/lily_v001")
MANIFEST   = OUTPUT_DIR / "manifest.json"
RESULTS    = OUTPUT_DIR / "arcface_results.csv"
SUMMARY    = OUTPUT_DIR / "checkpoint_summary.csv"


# ── ArcFace helpers ────────────────────────────────────────────────────────────
def load_app() -> FaceAnalysis:
    """Load InsightFace buffalo_l model (ArcFace R100)."""
    app = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def get_embedding(app: FaceAnalysis, image_path: str) -> Optional[np.ndarray]:
    """Extract ArcFace face embedding. Returns None if no face detected."""
    img = cv2.imread(image_path)
    if img is None:
        return None

    faces = app.get(img)
    if not faces:
        return None

    # Pick largest detected face
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return face.normed_embedding


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def build_aggregated_embedding(app: FaceAnalysis, image_dir: Path) -> np.ndarray:
    """Build mean embedding from all faces in a directory.

    Per research: aggregated reference embedding (mean of 5-20 clean refs)
    is more robust than a single photo for scoring.
    """
    embeddings = []
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}

    image_files = sorted([
        f for f in image_dir.iterdir()
        if f.suffix.lower() in image_extensions
    ])

    print(f"  Scanning {len(image_files)} images in {image_dir}...")

    for img_path in image_files:
        emb = get_embedding(app, str(img_path))
        if emb is not None:
            embeddings.append(emb)

    if not embeddings:
        print(f"  ERROR: no faces detected in any reference images")
        sys.exit(1)

    mean_emb = np.mean(embeddings, axis=0)
    # Re-normalize to unit length (important for cosine similarity)
    mean_emb = mean_emb / np.linalg.norm(mean_emb)

    print(f"  Aggregated embedding from {len(embeddings)}/{len(image_files)} faces")
    return mean_emb


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    ref_group = parser.add_mutually_exclusive_group(required=True)
    ref_group.add_argument("--ref", help="Path to single reference image")
    ref_group.add_argument("--ref-dir", help="Directory of reference images (aggregated embedding)")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}")
        print("Run eval_generate.py first.")
        sys.exit(1)

    print("Loading InsightFace (buffalo_l / ArcFace R100)...")
    app = load_app()
    print("Model ready.\n")

    # Build reference embedding
    if args.ref_dir:
        ref_dir = Path(args.ref_dir)
        if not ref_dir.is_dir():
            print(f"ERROR: not a directory: {ref_dir}")
            sys.exit(1)
        print(f"Building aggregated reference embedding from: {ref_dir}")
        ref_emb = build_aggregated_embedding(app, ref_dir)
    else:
        print(f"Reference image: {args.ref}")
        ref_emb = get_embedding(app, args.ref)
        if ref_emb is None:
            print("ERROR: no face detected in reference image.")
            sys.exit(1)
        print("  Single reference embedding extracted.")
        print("  TIP: use --ref-dir for aggregated embedding (more robust)")
    print()

    # Load manifest
    with open(MANIFEST) as f:
        manifest = json.load(f)

    # Score all images
    results       = []
    step_scores   = defaultdict(list)
    no_face_count = 0

    print(f"{'─' * 70}")
    print(f"{'STEP':<8} {'PROMPT':<22} {'SEED':<6} {'FACESIM':>8}")
    print(f"{'─' * 70}")

    for entry in manifest:
        path = entry["path"]
        step = entry["step"]
        emb  = get_embedding(app, path)

        if emb is not None:
            score = cosine_sim(ref_emb, emb)
            step_scores[step].append(score)
            score_str = f"{score:.4f}"
        else:
            score = None
            no_face_count += 1
            score_str = "NO FACE"

        results.append({**entry, "facesim": score})
        print(f"  {step:<6} {entry['prompt']:<22} {entry['seed']:<6} {score_str:>8}")

    # Save per-image CSV
    with open(RESULTS, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["step", "prompt", "seed", "facesim", "path"])
        writer.writeheader()
        writer.writerows(results)

    # Per-checkpoint summary
    print(f"\n{'=' * 60}")
    print(f"CHECKPOINT RANKING (by mean FaceSim)")
    print(f"{'─' * 60}")
    print(f"  {'STEP':<8} {'MEAN':>8} {'MAX':>8} {'MIN':>8} {'N':>4}  RANK")
    print(f"{'─' * 60}")

    summary = []
    for step in sorted(step_scores.keys()):
        scores = step_scores[step]
        summary.append({
            "step": step,
            "mean": round(float(np.mean(scores)), 4),
            "max":  round(float(np.max(scores)), 4),
            "min":  round(float(np.min(scores)), 4),
            "n":    len(scores),
        })

    # Sort by mean descending
    summary.sort(key=lambda r: r["mean"], reverse=True)
    for rank, row in enumerate(summary, 1):
        marker = " <- BEST" if rank == 1 else ""
        print(f"  {row['step']:<8} {row['mean']:>8.4f} {row['max']:>8.4f} {row['min']:>8.4f} {row['n']:>4}  #{rank}{marker}")

    best = summary[0]
    print(f"\n{'=' * 60}")
    print(f"  WINNER: step_{best['step']:04d}")
    print(f"  Mean FaceSim : {best['mean']:.4f}")
    print(f"  Max FaceSim  : {best['max']:.4f}")
    print(f"{'=' * 60}")

    if no_face_count > 0:
        print(f"\n  WARN: {no_face_count} images had no face detected (excluded)")

    # Save summary CSV
    with open(SUMMARY, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["step", "mean", "max", "min", "n"])
        writer.writeheader()
        writer.writerows(summary)

    # Next steps
    best_step = best["step"]
    if best_step == 2500:
        best_file = "lora_lily_v001.safetensors"
    else:
        best_file = f"lora_lily_v001_{best_step:09d}.safetensors"

    print(f"\n  Results : {RESULTS}")
    print(f"  Summary : {SUMMARY}")
    print(f"\nDeploy best checkpoint to ComfyUI:")
    print(f"  cp {LORA_DIR / best_file} /app/comfyui/models/loras/lora_lily_v001.safetensors")


if __name__ == "__main__":
    main()
