#!/bin/bash
# infra/docker/staging/start.sh
# Runs on every pod startup.
# Wires the Runpod network volume into ComfyUI, then starts the server.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

VOLUME_PATH="${NETWORK_VOLUME_PATH:-/workspace}"
COMFYUI_DIR="/app/comfyui"
COMFYUI_PORT="${COMFYUI_PORT:-8188}"
VRAM_MODE="${VRAM_MODE:-highvram}"

echo "[start] env=staging | volume=${VOLUME_PATH} | port=${COMFYUI_PORT} | vram=${VRAM_MODE}"

# ── Create volume directory structure ─────────────────────────────────────────
# mkdir -p is idempotent — safe to run on an already-initialised volume.

echo "[start] ensuring volume directory structure..."

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

# ── Symlink volume into ComfyUI ───────────────────────────────────────────────
# ComfyUI ships with its own models/, custom_nodes/, output/, input/ dirs.
# Replace them with symlinks to the network volume so all data is persistent.

echo "[start] wiring symlinks: volume → comfyui..."

rm -rf "${COMFYUI_DIR}/models"
ln -sf "${VOLUME_PATH}/models"       "${COMFYUI_DIR}/models"

rm -rf "${COMFYUI_DIR}/custom_nodes"
ln -sf "${VOLUME_PATH}/custom_nodes" "${COMFYUI_DIR}/custom_nodes"

rm -rf "${COMFYUI_DIR}/output"
ln -sf "${VOLUME_PATH}/outputs"      "${COMFYUI_DIR}/output"

rm -rf "${COMFYUI_DIR}/input"
ln -sf "${VOLUME_PATH}/input"        "${COMFYUI_DIR}/input"

echo "[start] symlinks ready."

# ── Install dependencies ──────────────────────────────────────────────────────
# Two-tier system for repeatability.
#
# TIER 1 — pinned manifest (deterministic):
#   requirements_pinned.txt on the volume is the source of truth for stable nodes.
#   Maintained by the operator with explicit package==version pins.
#   Install this first so it takes precedence over anything in the sweep.
#
# TIER 2 — sweep fallback (for nodes under test in staging):
#   Each custom_nodes/<node>/requirements.txt gets installed for nodes not yet pinned.
#   pip skips packages already satisfied by tier 1.
#
# Upgrade path:
#   Once a node's deps are stable → pin them in requirements_pinned.txt.
#   Production: tier 1 only, no sweep.

echo "[start] installing dependencies..."

PINNED_REQ="${VOLUME_PATH}/requirements_pinned.txt"
if [ -f "${PINNED_REQ}" ]; then
    echo "[start] tier 1: installing pinned requirements..."
    pip install --quiet --no-cache-dir -r "${PINNED_REQ}"
else
    echo "[start] tier 1: no requirements_pinned.txt found — skipping."
fi

echo "[start] tier 2: sweeping custom node requirements..."
for node_dir in "${VOLUME_PATH}/custom_nodes"/*/; do
    if [ -f "${node_dir}requirements.txt" ]; then
        echo "[start]   installing: $(basename "${node_dir}")"
        pip install --quiet --no-cache-dir -r "${node_dir}requirements.txt" || \
            echo "[start]   WARNING: pip install failed for $(basename "${node_dir}") — continuing"
    fi
done

echo "[start] dependencies done."

# ── Build VRAM flag ───────────────────────────────────────────────────────────
# Valid VRAM_MODE values and their ComfyUI flags:
#   highvram   → --highvram   (RTX 4090 24GB default — keep models in VRAM)
#   normalvram → (no flag)    (balanced offloading)
#   lowvram    → --lowvram    (aggressive offloading for <12GB)
#   cpu        → --cpu        (CPU-only, debugging without GPU)

case "${VRAM_MODE}" in
    highvram)   VRAM_FLAG="--highvram" ;;
    normalvram) VRAM_FLAG="" ;;
    lowvram)    VRAM_FLAG="--lowvram" ;;
    cpu)        VRAM_FLAG="--cpu" ;;
    *)
        echo "[start] WARNING: unknown VRAM_MODE '${VRAM_MODE}' — defaulting to --highvram"
        VRAM_FLAG="--highvram"
        ;;
esac

# ── Launch ComfyUI ────────────────────────────────────────────────────────────
# exec replaces the shell process with Python so Python receives OS signals
# directly (SIGTERM on pod stop → graceful shutdown).
#
# --listen 0.0.0.0     required for Runpod port forwarding
# --disable-auto-launch do not attempt to open a browser in headless env
# VRAM_FLAG            controls memory strategy (empty string = no flag added)

echo "[start] launching comfyui on port ${COMFYUI_PORT}..."

cd "${COMFYUI_DIR}"

exec python main.py \
    --listen 0.0.0.0 \
    --port "${COMFYUI_PORT}" \
    --disable-auto-launch \
    ${VRAM_FLAG} \
    --output-directory "${VOLUME_PATH}/outputs" \
    --input-directory  "${VOLUME_PATH}/input"
