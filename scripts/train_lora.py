#!/usr/bin/env python3
"""
LoRA Training Pipeline — prepare dataset and train character LoRA.

Two modes:
  prepare  — collect images, resize, generate captions, create ai-toolkit config
  train    — run ai-toolkit training from prepared config

Usage:
    # Standard (3+ images):
    python scripts/train_lora.py prepare \\
        --images img1.png img2.png img3.png \\
        --character lily \\
        --output /workspace/lora_training/lily_v001/

    # Bootstrap (1-2 images, with augmentations):
    python scripts/train_lora.py prepare \\
        --images target.png \\
        --character lily \\
        --augment \\
        --output /workspace/lora_training/lily_v001/

    # Train:
    python scripts/train_lora.py train \\
        --config /workspace/lora_training/lily_v001/config.yaml

Requires:
    - Pillow (for prepare)
    - ai-toolkit installed at /workspace/ai-toolkit (for train)
"""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:
    Image = None

# ── Constants ────────────────────────────────────────────────────────────────

AI_TOOLKIT_DIR = Path("/workspace/ai-toolkit")
DEFAULT_TRIGGER = "ohwx woman"
DEFAULT_RANK = 16
DEFAULT_LR = 0.0001
DEFAULT_WEIGHT_DECAY = 0.0001
TARGET_REPEATS_STANDARD = 90
TARGET_REPEATS_HIGH = 120
MAX_RESOLUTION = 1024


# ── Prepare ──────────────────────────────────────────────────────────────────

def resize_for_training(img: "Image.Image", max_res: int = MAX_RESOLUTION) -> "Image.Image":
    """Resize image so longest side = max_res, preserve aspect ratio."""
    w, h = img.size
    if max(w, h) <= max_res:
        return img.copy()
    scale = max_res / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def generate_augmentations(img: "Image.Image"):
    """Generate augmented versions of a single image for bootstrap training."""
    augmented = []

    # Horizontal flip
    flipped = ImageOps.mirror(img)
    augmented.append((flipped, "flip"))

    # Crop variations (±5%)
    w, h = img.size
    crop_pct = 0.05
    for idx, (left_f, top_f) in enumerate([(crop_pct, 0), (0, crop_pct), (crop_pct, crop_pct)]):
        left = int(w * left_f)
        top = int(h * top_f)
        right = w - int(w * crop_pct) + left
        bottom = h - int(h * crop_pct) + top
        cropped = img.crop((left, top, right, bottom))
        cropped = cropped.resize((w, h), Image.LANCZOS)
        augmented.append((cropped, f"crop{idx + 1}"))

    # Color temperature shift (warm)
    enhancer = ImageEnhance.Color(img)
    warm = enhancer.enhance(1.1)
    augmented.append((warm, "warm"))

    # Brightness adjustment
    enhancer = ImageEnhance.Brightness(img)
    bright = enhancer.enhance(1.1)
    augmented.append((bright, "bright"))

    return augmented


def generate_caption(trigger: str, filename: str) -> str:
    """Generate a simple caption. Only describes context, NOT facial features."""
    # Keep it simple — trigger word + generic context
    # Facial features bind to trigger word automatically during training
    return f"{trigger}, looking at camera, portrait, natural lighting"


def calculate_steps(num_images: int, high_likeness: bool = False) -> int:
    """Calculate training steps based on number of images."""
    target = TARGET_REPEATS_HIGH if high_likeness else TARGET_REPEATS_STANDARD
    # steps = target_repeats * num_images / (batch_size * grad_accum)
    # batch_size=1, grad_accum=1
    steps = target * num_images
    # Minimum 300, round to nearest 50
    steps = max(300, steps)
    steps = int(math.ceil(steps / 50) * 50)
    return steps


def write_config(output_dir: Path, character: str, trigger: str,
                 num_images: int, rank: int, model_path: str,
                 high_likeness: bool = False) -> Path:
    """Write ai-toolkit training config YAML."""
    steps = calculate_steps(num_images, high_likeness)
    save_every = max(50, steps // 10)
    config_name = f"lora_{character}_v001"
    img_dir = output_dir / "img"
    train_output = output_dir / "output"

    config = f"""job: "extension"
config:
  name: "{config_name}"
  process:
    - type: "diffusion_trainer"
      training_folder: "{train_output}"
      device: "cuda"
      trigger_word: "{trigger}"
      network:
        type: "lora"
        linear: {rank}
        linear_alpha: {rank}
        conv: {max(8, rank // 2)}
        conv_alpha: {max(4, rank // 4)}
      save:
        dtype: "bf16"
        save_every: {save_every}
        max_step_saves_to_keep: 20
      datasets:
        - folder_path: "{img_dir}"
          caption_ext: "txt"
          resolution: [512, 768, 1024]
      train:
        batch_size: 1
        steps: {steps}
        lr: {DEFAULT_LR}
        optimizer: "adamw8bit"
        timestep_type: "shift"
        content_or_style: "balanced"
        optimizer_params:
          weight_decay: {DEFAULT_WEIGHT_DECAY}
      model:
        name_or_path: "{model_path}"
        quantize: true
        low_vram: true
"""

    config_path = output_dir / "config.yaml"
    config_path.write_text(config)
    return config_path


def cmd_prepare(args):
    """Prepare training dataset from selected images."""
    if Image is None:
        print("Error: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    output_dir = Path(args.output)
    img_dir = output_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    trigger = args.trigger_word or DEFAULT_TRIGGER
    image_paths = [Path(p) for p in args.images]

    # Validate inputs
    for p in image_paths:
        if not p.exists():
            print(f"Error: Image not found: {p}")
            sys.exit(1)

    print(f"[train_lora] Preparing dataset for character: {args.character}")
    print(f"[train_lora] Trigger word: {trigger}")
    print(f"[train_lora] Source images: {len(image_paths)}")

    saved_count = 0

    for idx, src_path in enumerate(image_paths, 1):
        with Image.open(src_path) as img:
            img = img.convert("RGB")
            img = resize_for_training(img)

            # Save original
            prefix = f"{idx:02d}"
            out_img = img_dir / f"{prefix}.png"
            img.save(out_img, quality=95)
            saved_count += 1

            # Caption
            caption = generate_caption(trigger, src_path.name)
            (img_dir / f"{prefix}.txt").write_text(caption)

            print(f"  [{idx}/{len(image_paths)}] {src_path.name} -> {out_img.name} ({img.size[0]}x{img.size[1]})")

            # Augmentations (bootstrap mode)
            if args.augment:
                augmented = generate_augmentations(img)
                for aug_img, aug_label in augmented:
                    aug_name = f"{prefix}_{aug_label}"
                    aug_path = img_dir / f"{aug_name}.png"
                    aug_img.save(aug_path, quality=95)
                    (img_dir / f"{aug_name}.txt").write_text(caption)
                    saved_count += 1
                print(f"           + {len(augmented)} augmentations")

    # Determine effective image count for step calculation
    effective_count = saved_count
    high_likeness = len(image_paths) <= 3

    # Model path
    model_path = args.model_path or "black-forest-labs/FLUX.1-dev"
    rank = args.rank or DEFAULT_RANK

    # Write config
    config_path = write_config(
        output_dir, args.character, trigger,
        effective_count, rank, model_path, high_likeness
    )

    steps = calculate_steps(effective_count, high_likeness)
    print(f"\n[train_lora] Dataset ready: {saved_count} images in {img_dir}")
    print(f"[train_lora] Config: {config_path}")
    print(f"[train_lora] Training plan: {steps} steps, rank {rank}, lr {DEFAULT_LR}")
    print(f"[train_lora] Estimated repeats/image: {steps // effective_count}")
    if high_likeness:
        print(f"[train_lora] High-likeness mode (<=3 source images)")
    print(f"\n[train_lora] Next: python scripts/train_lora.py train --config {config_path}")


def cmd_train(args):
    """Run ai-toolkit training from config."""
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)

    # Check ai-toolkit
    toolkit_run = AI_TOOLKIT_DIR / "run.py"
    if not toolkit_run.exists():
        print(f"Error: ai-toolkit not found at {AI_TOOLKIT_DIR}")
        print(f"  Install: cd /workspace && git clone https://github.com/ostris/ai-toolkit.git")
        print(f"           cd ai-toolkit && pip install -r requirements.txt")
        sys.exit(1)

    print(f"[train_lora] Starting training with config: {config_path}")
    print(f"[train_lora] ai-toolkit: {AI_TOOLKIT_DIR}")
    print(f"[train_lora] IMPORTANT: Make sure ComfyUI is stopped (VRAM conflict)")
    print()

    # Run ai-toolkit
    cmd = [sys.executable, str(toolkit_run), str(config_path)]
    try:
        result = subprocess.run(cmd, cwd=str(AI_TOOLKIT_DIR), check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[train_lora] Training failed with exit code {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n[train_lora] Training interrupted by user")
        sys.exit(1)

    # Find output
    config_dir = config_path.parent
    output_dir = config_dir / "output"
    if output_dir.exists():
        safetensors = list(output_dir.rglob("*.safetensors"))
        if safetensors:
            latest = max(safetensors, key=lambda p: p.stat().st_mtime)
            print(f"\n[train_lora] Training complete!")
            print(f"[train_lora] Latest checkpoint: {latest}")
            print(f"[train_lora] Size: {latest.stat().st_size / 1024 / 1024:.1f} MB")
            print(f"\n[train_lora] Next steps:")
            print(f"  1. Copy to ComfyUI: cp {latest} /workspace/models/loras/")
            print(f"  2. Restart ComfyUI")
            print(f"  3. Test: python scripts/run_explore.py --lora {latest.name} --count 10 --prompt '...'")
        else:
            print(f"\n[train_lora] Warning: No .safetensors files found in {output_dir}")
    else:
        print(f"\n[train_lora] Warning: Output directory not found: {output_dir}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LoRA Training Pipeline — prepare dataset and train character LoRA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare dataset (3+ images, standard):
  %(prog)s prepare --images face1.png face2.png face3.png --character lily

  # Prepare dataset (1 image, bootstrap with augmentations):
  %(prog)s prepare --images target.png --character lily --augment

  # Train LoRA:
  %(prog)s train --config /workspace/lora_training/lily_v001/config.yaml

Training tips:
  - Train on BASE model (not distilled) — required for proper gradient signal
  - Use 3-10 images with different angles/expressions/backgrounds for best results
  - With 1-2 images, use --augment for bootstrap (weaker but workable)
  - Keep rank at 16 (safe for 24GB VRAM), increase to 32 if underfitting
  - Stop ComfyUI before training (VRAM conflict)
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # prepare subcommand
    prep = subparsers.add_parser("prepare", help="Prepare training dataset")
    prep.add_argument("--images", nargs="+", required=True,
                      help="Source image paths")
    prep.add_argument("--character", type=str, required=True,
                      help="Character name (e.g. lily, chara)")
    prep.add_argument("--trigger-word", type=str, default=None,
                      help=f"Trigger word (default: {DEFAULT_TRIGGER})")
    prep.add_argument("--augment", action="store_true",
                      help="Generate augmentations (for 1-2 image bootstrap)")
    prep.add_argument("--output", type=str, default=None,
                      help="Output directory (default: /workspace/lora_training/<character>_v001/)")
    prep.add_argument("--model-path", type=str, default=None,
                      help="Model path/HF ID (default: black-forest-labs/FLUX.1-dev)")
    prep.add_argument("--rank", type=int, default=None,
                      help=f"LoRA rank (default: {DEFAULT_RANK})")

    # train subcommand
    trn = subparsers.add_parser("train", help="Run LoRA training")
    trn.add_argument("--config", type=str, required=True,
                     help="Path to ai-toolkit config YAML")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "prepare":
        if args.output is None:
            args.output = f"/workspace/lora_training/{args.character}_v001"
        cmd_prepare(args)
    elif args.command == "train":
        cmd_train(args)


if __name__ == "__main__":
    main()
