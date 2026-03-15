#!/usr/bin/env python3
"""
Select best training candidates from generated images using face similarity.

Compares each generated image against a reference face photo using ArcFace
embeddings (insightface). Ranks by face similarity, filters by quality,
and clusters for diversity to avoid selecting near-duplicates.

Usage:
    # Basic — select top 20 from all explore sessions:
    python scripts/select_training_candidates.py \
        --reference /path/to/reference_face.png \
        --input /workspace/ai-ofm-production-factory/explore_output/ \
        --output /workspace/lora_training/chara_v002/candidates/ \
        --top 20

    # From specific sessions:
    python scripts/select_training_candidates.py \
        --reference /path/to/reference_face.png \
        --input /workspace/ai-ofm-production-factory/explore_output/explore_20260314_* \
        --output /workspace/lora_training/chara_v002/candidates/ \
        --top 20

    # Adjust similarity threshold:
    python scripts/select_training_candidates.py \
        --reference /path/to/reference_face.png \
        --input /workspace/ai-ofm-production-factory/explore_output/ \
        --min-similarity 0.4 \
        --top 25

Requires:
    pip install insightface onnxruntime-gpu opencv-python-headless numpy

First run downloads ArcFace model (~300MB) to ~/.insightface/
"""

import argparse
import json
import shutil
import sys
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


# ── Face Analysis ─────────────────────────────────────────────────────────────

def init_face_analyzer(gpu_id: int = 0) -> FaceAnalysis:
    """Initialize insightface analyzer with ArcFace model."""
    app = FaceAnalysis(
        name="buffalo_l",
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    app.prepare(ctx_id=gpu_id, det_size=(640, 640))
    return app


def get_face_embedding(app: FaceAnalysis, img_path: str) -> dict | None:
    """Extract face embedding and quality metrics from image.

    Returns dict with:
        - embedding: 512-dim ArcFace vector
        - bbox: face bounding box [x1, y1, x2, y2]
        - face_size: face area as fraction of image area
        - det_score: detection confidence
        - sharpness: Laplacian variance of face region (higher = sharper)
    Returns None if no face detected.
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return None

    faces = app.get(img)
    if not faces:
        return None

    # Take the largest face (most prominent)
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    # Face size relative to image
    img_h, img_w = img.shape[:2]
    img_area = img_h * img_w
    fx1, fy1, fx2, fy2 = face.bbox
    face_area = (fx2 - fx1) * (fy2 - fy1)
    face_size = face_area / img_area

    # Sharpness of face region (Laplacian variance)
    x1 = max(0, int(fx1))
    y1 = max(0, int(fy1))
    x2 = min(img_w, int(fx2))
    y2 = min(img_h, int(fy2))
    face_crop = img[y1:y2, x1:x2]
    if face_crop.size == 0:
        return None
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()

    return {
        "embedding": face.embedding,
        "bbox": [float(fx1), float(fy1), float(fx2), float(fy2)],
        "face_size": float(face_size),
        "det_score": float(face.det_score),
        "sharpness": float(sharpness),
    }


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ── Diversity Clustering ──────────────────────────────────────────────────────

def select_diverse(candidates: list[dict], top_n: int, diversity_threshold: float = 0.85) -> list[dict]:
    """Select top_n candidates maximizing diversity.

    Greedy selection: take best candidate, then skip any too similar
    to already-selected ones (embedding cosine > diversity_threshold).
    """
    selected = []
    for c in candidates:
        if len(selected) >= top_n:
            break
        # Check if too similar to any already selected
        too_similar = False
        for s in selected:
            sim = cosine_similarity(c["embedding"], s["embedding"])
            if sim > diversity_threshold:
                too_similar = True
                break
        if not too_similar:
            selected.append(c)
    return selected


# ── Score ─────────────────────────────────────────────────────────────────────

def compute_score(face_sim: float, face_size: float, sharpness: float, det_score: float) -> float:
    """Composite score: face similarity is primary, quality is secondary.

    Weights:
        - face_similarity: 70% (the whole point)
        - face_size: 10% (larger face = more training signal)
        - sharpness: 10% (sharper = better quality)
        - det_score: 10% (higher confidence = cleaner face)
    """
    # Normalize sharpness (typical range 50-2000, cap at 1000)
    sharpness_norm = min(sharpness / 1000.0, 1.0)
    # Normalize face_size (typical range 0.05-0.5, cap at 0.4)
    face_size_norm = min(face_size / 0.4, 1.0)

    return (
        0.70 * face_sim
        + 0.10 * face_size_norm
        + 0.10 * sharpness_norm
        + 0.10 * det_score
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def find_images(input_paths: list[str]) -> list[Path]:
    """Recursively find all PNG/JPG images in input paths."""
    images = []
    for p in input_paths:
        path = Path(p)
        if path.is_file() and path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            images.append(path)
        elif path.is_dir():
            for ext in ("*.png", "*.jpg", "*.jpeg"):
                images.extend(path.rglob(ext))
    # Filter out contact sheets and thumbnails
    images = [
        img for img in images
        if "contact_sheet" not in img.name
        and "thumb" not in img.name
        and not img.name.startswith(".")
    ]
    return sorted(set(images))


def main():
    parser = argparse.ArgumentParser(
        description="Select best training candidates by face similarity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--reference", required=True,
                        help="Reference face image path")
    parser.add_argument("--input", nargs="+", required=True,
                        help="Input directories or image files to scan")
    parser.add_argument("--output", default=None,
                        help="Output directory to copy selected images (optional)")
    parser.add_argument("--top", type=int, default=20,
                        help="Number of candidates to select (default: 20)")
    parser.add_argument("--min-similarity", type=float, default=0.35,
                        help="Minimum face similarity threshold (default: 0.35)")
    parser.add_argument("--diversity", type=float, default=0.85,
                        help="Diversity threshold — skip if cosine > this to already-selected (default: 0.85)")
    parser.add_argument("--gpu", type=int, default=0,
                        help="GPU ID for face detection (default: 0)")
    parser.add_argument("--report", default=None,
                        help="Save JSON report to this path (optional)")

    args = parser.parse_args()

    # Validate reference
    ref_path = Path(args.reference)
    if not ref_path.exists():
        print(f"Error: Reference image not found: {ref_path}")
        sys.exit(1)

    # Find all candidate images
    print(f"[select] Scanning input paths...")
    images = find_images(args.input)
    print(f"[select] Found {len(images)} images")

    if not images:
        print("Error: No images found in input paths")
        sys.exit(1)

    # Initialize face analyzer
    print(f"[select] Loading ArcFace model...")
    app = init_face_analyzer(args.gpu)

    # Get reference embedding
    print(f"[select] Analyzing reference: {ref_path.name}")
    ref_data = get_face_embedding(app, str(ref_path))
    if ref_data is None:
        print(f"Error: No face detected in reference image: {ref_path}")
        sys.exit(1)
    ref_embedding = ref_data["embedding"]
    print(f"[select] Reference face: det_score={ref_data['det_score']:.3f}, "
          f"face_size={ref_data['face_size']:.1%}")

    # Analyze all candidates
    print(f"\n[select] Analyzing {len(images)} candidates...")
    candidates = []
    no_face = 0
    below_threshold = 0

    for i, img_path in enumerate(images, 1):
        if i % 20 == 0 or i == len(images):
            print(f"  [{i}/{len(images)}] processed...")

        data = get_face_embedding(app, str(img_path))
        if data is None:
            no_face += 1
            continue

        face_sim = cosine_similarity(ref_embedding, data["embedding"])
        if face_sim < args.min_similarity:
            below_threshold += 1
            continue

        score = compute_score(face_sim, data["face_size"], data["sharpness"], data["det_score"])

        candidates.append({
            "path": str(img_path),
            "filename": img_path.name,
            "face_similarity": face_sim,
            "face_size": data["face_size"],
            "sharpness": data["sharpness"],
            "det_score": data["det_score"],
            "score": score,
            "embedding": data["embedding"],
        })

    print(f"\n[select] Results:")
    print(f"  Total scanned: {len(images)}")
    print(f"  No face detected: {no_face}")
    print(f"  Below similarity threshold ({args.min_similarity}): {below_threshold}")
    print(f"  Candidates passing filter: {len(candidates)}")

    if not candidates:
        print("\nError: No candidates passed the similarity threshold.")
        print("  Try lowering --min-similarity (current: {args.min_similarity})")
        sys.exit(1)

    # Sort by score (descending)
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Select with diversity
    selected = select_diverse(candidates, args.top, args.diversity)
    print(f"  Selected (with diversity): {len(selected)}")

    # Print results
    print(f"\n{'='*80}")
    print(f"  TOP {len(selected)} CANDIDATES")
    print(f"{'='*80}")
    print(f"{'#':>3}  {'Score':>6}  {'FaceSim':>7}  {'Size':>6}  {'Sharp':>7}  {'File'}")
    print(f"{'-'*3}  {'-'*6}  {'-'*7}  {'-'*6}  {'-'*7}  {'-'*40}")

    for i, c in enumerate(selected, 1):
        print(f"{i:3d}  {c['score']:.4f}  {c['face_similarity']:.4f}  "
              f"{c['face_size']:.1%}  {c['sharpness']:7.1f}  {c['filename']}")

    # Copy to output directory
    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[select] Copying {len(selected)} images to {out_dir}/")
        for i, c in enumerate(selected, 1):
            src = Path(c["path"])
            # Rename with rank prefix for easy review
            dst = out_dir / f"{i:02d}_sim{c['face_similarity']:.2f}_{src.name}"
            shutil.copy2(src, dst)
            print(f"  {dst.name}")

        print(f"\n[select] Done! Review images in: {out_dir}")
        print(f"[select] Delete any you don't like, then use remaining for v002 training.")

    # Save report
    if args.report:
        report = {
            "reference": str(ref_path),
            "total_scanned": len(images),
            "no_face": no_face,
            "below_threshold": below_threshold,
            "candidates_passing": len(candidates),
            "selected": len(selected),
            "settings": {
                "min_similarity": args.min_similarity,
                "diversity_threshold": args.diversity,
                "top_n": args.top,
            },
            "results": [
                {
                    "rank": i,
                    "path": c["path"],
                    "filename": c["filename"],
                    "score": round(c["score"], 4),
                    "face_similarity": round(c["face_similarity"], 4),
                    "face_size": round(c["face_size"], 4),
                    "sharpness": round(c["sharpness"], 1),
                    "det_score": round(c["det_score"], 4),
                }
                for i, c in enumerate(selected, 1)
            ],
            # Also include runners-up for manual review
            "runners_up": [
                {
                    "path": c["path"],
                    "filename": c["filename"],
                    "score": round(c["score"], 4),
                    "face_similarity": round(c["face_similarity"], 4),
                }
                for c in candidates[: args.top * 3]
                if c not in selected
            ][:20],
        }
        report_path = Path(args.report)
        report_path.write_text(json.dumps(report, indent=2))
        print(f"[select] Report saved: {report_path}")


if __name__ == "__main__":
    main()
