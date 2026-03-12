#!/bin/bash
# scripts/diagnose_flux.sh
# Read-only diagnostic script for the Runpod pod.
# Checks everything needed for FLUX.2-klein-4B to work in ComfyUI.
#
# Usage (on the pod):
#   bash scripts/diagnose_flux.sh [COMFYUI_URL]
#
# Default COMFYUI_URL: http://localhost:8188

set -uo pipefail

COMFYUI_URL="${1:-http://localhost:8188}"
VOLUME_PATH="${NETWORK_VOLUME_PATH:-/workspace}"
PASS=0
FAIL=0
WARN=0

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }
warn() { echo "  [WARN] $1"; ((WARN++)); }

echo "============================================================"
echo "  FLUX.2-klein-4B Diagnostic"
echo "  Volume: ${VOLUME_PATH}"
echo "  ComfyUI: ${COMFYUI_URL}"
echo "============================================================"

# ── Check 1: GPU ─────────────────────────────────────────────────────────────

echo ""
echo "[1/8] GPU check..."
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "${GPU_NAME}" ]; then
        pass "GPU detected: ${GPU_NAME}"
    else
        fail "nvidia-smi found but no GPU detected"
    fi
else
    fail "nvidia-smi not found"
fi

# ── Check 2: ComfyUI version ─────────────────────────────────────────────────

echo ""
echo "[2/8] ComfyUI version..."
if [ -d "/app/comfyui/.git" ]; then
    COMFY_VER=$(cd /app/comfyui && git describe --tags 2>/dev/null || git log --oneline -1)
    pass "ComfyUI version: ${COMFY_VER}"
else
    warn "Cannot determine ComfyUI version (no .git directory)"
fi

# ── Check 3: Symlinks ────────────────────────────────────────────────────────

echo ""
echo "[3/8] Symlink check..."
if [ -L "/app/comfyui/models" ]; then
    LINK_TARGET=$(readlink -f /app/comfyui/models)
    if [ "${LINK_TARGET}" = "$(readlink -f ${VOLUME_PATH}/models)" ]; then
        pass "models symlink OK: /app/comfyui/models → ${VOLUME_PATH}/models"
    else
        fail "models symlink points to wrong target: ${LINK_TARGET}"
    fi
else
    fail "/app/comfyui/models is not a symlink"
fi

# ── Check 4: Model directories and files ──────────────────────────────────────

echo ""
echo "[4/8] Model directories and files..."

# Check required directories exist
for DIR in diffusion_models text_encoders vae; do
    if [ -d "${VOLUME_PATH}/models/${DIR}" ]; then
        pass "Directory exists: models/${DIR}/"
    else
        fail "Directory missing: models/${DIR}/ — run: mkdir -p ${VOLUME_PATH}/models/${DIR}"
    fi
done

# Check for expected model files
echo ""
echo "  Scanning model files..."

if [ -f "${VOLUME_PATH}/models/diffusion_models/flux-2-klein-4b.safetensors" ]; then
    SIZE=$(ls -lh "${VOLUME_PATH}/models/diffusion_models/flux-2-klein-4b.safetensors" | awk '{print $5}')
    pass "Diffusion model found: flux-2-klein-4b.safetensors (${SIZE})"
else
    fail "Diffusion model missing: models/diffusion_models/flux-2-klein-4b.safetensors"
fi

if [ -f "${VOLUME_PATH}/models/text_encoders/qwen_3_4b.safetensors" ]; then
    SIZE=$(ls -lh "${VOLUME_PATH}/models/text_encoders/qwen_3_4b.safetensors" | awk '{print $5}')
    pass "Text encoder found: qwen_3_4b.safetensors (${SIZE})"
else
    fail "Text encoder missing: models/text_encoders/qwen_3_4b.safetensors"
fi

if [ -f "${VOLUME_PATH}/models/vae/flux2-vae.safetensors" ]; then
    SIZE=$(ls -lh "${VOLUME_PATH}/models/vae/flux2-vae.safetensors" | awk '{print $5}')
    pass "VAE found: flux2-vae.safetensors (${SIZE})"
else
    fail "VAE missing: models/vae/flux2-vae.safetensors"
fi

# Also show what's in legacy directories
echo ""
echo "  Legacy directories (for reference):"
echo "  checkpoints/:"
ls -lh "${VOLUME_PATH}/models/checkpoints/" 2>/dev/null || echo "    (empty or missing)"
echo "  clip/:"
ls -lh "${VOLUME_PATH}/models/clip/" 2>/dev/null || echo "    (empty or missing)"

# ── Check 5: ComfyUI API health ──────────────────────────────────────────────

echo ""
echo "[5/8] ComfyUI API health..."
STATS=$(curl -sf "${COMFYUI_URL}/system_stats" 2>/dev/null)
if [ $? -eq 0 ] && [ -n "${STATS}" ]; then
    pass "ComfyUI API responding at ${COMFYUI_URL}/system_stats"
    echo "  ${STATS}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    gpu = d.get('devices', [{}])[0]
    print(f'    GPU: {gpu.get(\"name\", \"?\")}')
    print(f'    VRAM total: {gpu.get(\"vram_total\", 0) / 1e9:.1f} GB')
    print(f'    VRAM free:  {gpu.get(\"vram_free\", 0) / 1e9:.1f} GB')
    print(f'    Torch: {gpu.get(\"torch_vram_total\", 0) / 1e9:.1f} GB')
except: pass
" 2>/dev/null
else
    fail "ComfyUI API not responding at ${COMFYUI_URL}/system_stats"
    echo "  ComfyUI may not be running. Start it first, then re-run diagnostics."
fi

# ── Check 6: Node directory scanning (which dirs each node sees) ──────────────

echo ""
echo "[6/8] Node directory scanning (via /object_info)..."

if [ -n "${STATS}" ]; then
    # UNETLoader — should scan diffusion_models/
    echo ""
    echo "  UNETLoader available files:"
    curl -sf "${COMFYUI_URL}/object_info/UNETLoader" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    files = d['UNETLoader']['input']['required']['unet_name'][0]
    if files:
        for f in files: print(f'    {f}')
    else:
        print('    (none)')
except Exception as e:
    print(f'    ERROR: {e}')
" 2>/dev/null || echo "    (could not query)"

    # CLIPLoader — should scan text_encoders/
    echo ""
    echo "  CLIPLoader available files:"
    curl -sf "${COMFYUI_URL}/object_info/CLIPLoader" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    files = d['CLIPLoader']['input']['required']['clip_name'][0]
    if files:
        for f in files: print(f'    {f}')
    else:
        print('    (none)')
except Exception as e:
    print(f'    ERROR: {e}')
" 2>/dev/null || echo "    (could not query)"

    # VAELoader
    echo ""
    echo "  VAELoader available files:"
    curl -sf "${COMFYUI_URL}/object_info/VAELoader" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    files = d['VAELoader']['input']['required']['vae_name'][0]
    if files:
        for f in files: print(f'    {f}')
    else:
        print('    (none)')
except Exception as e:
    print(f'    ERROR: {e}')
" 2>/dev/null || echo "    (could not query)"
else
    warn "Skipping node scan — ComfyUI API not available"
fi

# ── Check 7: FLUX.2-specific nodes ───────────────────────────────────────────

echo ""
echo "[7/8] FLUX.2-specific nodes..."

if [ -n "${STATS}" ]; then
    for NODE in Flux2Scheduler EmptyFlux2LatentImage UNETLoader CLIPLoader CFGGuider SamplerCustomAdvanced; do
        RESULT=$(curl -sf "${COMFYUI_URL}/object_info/${NODE}" 2>/dev/null)
        if [ $? -eq 0 ] && echo "${RESULT}" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '${NODE}' in d" 2>/dev/null; then
            pass "Node exists: ${NODE}"
        else
            fail "Node missing: ${NODE}"
        fi
    done
else
    warn "Skipping node check — ComfyUI API not available"
fi

# ── Check 8: HuggingFace token ────────────────────────────────────────────────

echo ""
echo "[8/8] HuggingFace token..."
HF_TOKEN_FILE="${VOLUME_PATH}/.cache/huggingface/token"
if [ -f "${HF_TOKEN_FILE}" ]; then
    pass "HuggingFace token file exists: ${HF_TOKEN_FILE}"
else
    # Also check default location
    if [ -f "${HOME}/.cache/huggingface/token" ]; then
        pass "HuggingFace token found at default location"
    else
        warn "No HuggingFace token found (models from Comfy-Org are public, but may need for BFL repo)"
    fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "============================================================"
echo "  RESULTS: ${PASS} passed, ${FAIL} failed, ${WARN} warnings"
echo "============================================================"

if [ ${FAIL} -gt 0 ]; then
    echo ""
    echo "  Fix the FAIL items above before proceeding."
    echo ""
    echo "  Quick fix for missing model files:"
    echo ""
    echo "  mkdir -p ${VOLUME_PATH}/models/diffusion_models ${VOLUME_PATH}/models/text_encoders"
    echo ""
    echo "  wget -O ${VOLUME_PATH}/models/vae/flux2-vae.safetensors \\"
    echo "    \"https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors\""
    echo ""
    echo "  wget -O ${VOLUME_PATH}/models/diffusion_models/flux-2-klein-4b.safetensors \\"
    echo "    \"https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors\""
    echo ""
    echo "  wget -O ${VOLUME_PATH}/models/text_encoders/qwen_3_4b.safetensors \\"
    echo "    \"https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors\""
    echo ""
    exit 1
else
    echo ""
    echo "  All checks passed. Ready to run FLUX.2 test workflow."
    exit 0
fi
