#!/bin/bash
# scripts/setup_volume.sh
# One-time initialisation script for the Runpod network volume.
#
# Run this ONCE after creating a new network volume, before the first pod launch.
# After this, the volume structure is ready and start.sh can wire it on every startup.
#
# Usage:
#   bash scripts/setup_volume.sh [VOLUME_PATH]
#
# Default VOLUME_PATH: /workspace (Runpod default mount point)
# Override example:    bash scripts/setup_volume.sh /mnt/my_volume

set -euo pipefail

VOLUME_PATH="${1:-/workspace}"
MARKER="${VOLUME_PATH}/.volume_initialized"

echo "============================================================"
echo "  OFM Network Volume — One-Time Initialisation"
echo "  Volume path: ${VOLUME_PATH}"
echo "============================================================"

# ── Guard: skip if already initialised ───────────────────────────────────────

if [ -f "${MARKER}" ]; then
    echo ""
    echo "Volume already initialised. Found: ${MARKER}"
    echo "To force re-init, delete that file and re-run."
    exit 0
fi

# ── Create directory structure ────────────────────────────────────────────────

echo ""
echo "[1/4] Creating directory structure..."

mkdir -p \
    "${VOLUME_PATH}/models/checkpoints" \
    "${VOLUME_PATH}/models/vae" \
    "${VOLUME_PATH}/models/loras/characters" \
    "${VOLUME_PATH}/models/loras/styles" \
    "${VOLUME_PATH}/models/video_models" \
    "${VOLUME_PATH}/models/upscale_models" \
    "${VOLUME_PATH}/models/controlnet" \
    "${VOLUME_PATH}/models/clip" \
    "${VOLUME_PATH}/custom_nodes" \
    "${VOLUME_PATH}/outputs" \
    "${VOLUME_PATH}/input"

echo "  Done."

# ── Create requirements_pinned.txt ────────────────────────────────────────────
# This file is the tier 1 dependency manifest for start.sh.
# Once custom node deps are stable, pin them here with explicit versions.
# Format: standard pip requirements (package==version, one per line).
# start.sh installs this file first on every pod startup, then sweeps
# individual custom_nodes/*/requirements.txt for anything not yet pinned.

echo ""
echo "[2/4] Creating requirements_pinned.txt..."

cat > "${VOLUME_PATH}/requirements_pinned.txt" << 'EOF'
# requirements_pinned.txt
# Pinned dependencies for custom nodes.
#
# HOW TO USE:
#   Once a custom node's requirements are stable, move them here with
#   explicit version pins (e.g. numpy==1.26.4) instead of bare names.
#   start.sh installs this file first (tier 1) before sweeping
#   individual node requirements.txt files (tier 2).
#
# PRODUCTION PATH:
#   When all node deps are pinned here, the tier 2 sweep becomes a no-op.
#   Production will use tier 1 only (no sweep).
#
# FORMAT: standard pip requirements, one per line.
#   package==version
#   git+https://github.com/author/repo.git@commit_hash

EOF

echo "  Created: ${VOLUME_PATH}/requirements_pinned.txt"

# ── Write initialisation marker ───────────────────────────────────────────────

echo ""
echo "[3/4] Writing initialisation marker..."
echo "initialized_at: $(date -u +%Y_%m_%d_%H%M%S)" > "${MARKER}"

# ── Print next steps ──────────────────────────────────────────────────────────

echo ""
echo "[4/4] Volume structure ready."
echo ""
echo "============================================================"
echo "  NEXT: Download models to the network volume"
echo ""
echo "  Run from inside a pod attached to this volume."
echo "  Use huggingface-cli for Hugging Face models."
echo "  Verify model hashes after download."
echo "============================================================"
echo ""
echo "  Image model — FLUX.2 [klein] 4B"
echo "  Destination: ${VOLUME_PATH}/models/checkpoints/"
echo ""
echo "    huggingface-cli download <flux2_klein_repo_id> \\"
echo "        --local-dir ${VOLUME_PATH}/models/checkpoints/flux2_klein_4b"
echo ""
echo "  NOTE: Replace <flux2_klein_repo_id> with the correct Hugging Face"
echo "  repo ID. Verify model hash against the official release."
echo ""
echo "  Video model — Wan 2.2 TI2V-5B"
echo "  Destination: ${VOLUME_PATH}/models/video_models/"
echo ""
echo "    huggingface-cli download <wan22_ti2v_repo_id> \\"
echo "        --local-dir ${VOLUME_PATH}/models/video_models/wan22_ti2v_5b"
echo ""
echo "  Upscale model (e.g. 4x-UltraSharp or Real-ESRGAN 4x)"
echo "  Destination: ${VOLUME_PATH}/models/upscale_models/"
echo ""
echo "    wget -P ${VOLUME_PATH}/models/upscale_models/ <upscale_model_url>"
echo ""
echo "============================================================"
echo "  NEXT: Install custom nodes (staging only)"
echo ""
echo "  Clone into ${VOLUME_PATH}/custom_nodes/"
echo "  requirements.txt for each node is auto-installed by start.sh"
echo "  on the next pod startup."
echo ""
echo "  IMPORTANT: Custom nodes are STAGING ONLY."
echo "  Production uses an allowlist with pinned versions + hash discipline."
echo "============================================================"
echo ""
echo "  Recommended nodes for this stack:"
echo ""
echo "    cd ${VOLUME_PATH}/custom_nodes"
echo ""
echo "    # Video workflows (Wan 2.2)"
echo "    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git"
echo ""
echo "    # Video helper utilities"
echo "    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
echo ""
echo "    # Reference image injection (for character/style LoRA workflows)"
echo "    git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
echo ""
echo "  Once cloned, restart the pod. start.sh will auto-install requirements."
echo ""
echo "============================================================"
echo "  Setup complete. See docs/system/naming_convention.md"
echo "  for all file naming rules before placing models."
echo "============================================================"
echo ""
