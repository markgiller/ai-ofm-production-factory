# ──────────────────────────────────────────────────────────────────────────────
# Base: pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime
#
# Why this base:
#   - PyTorch 2.8.0 + CUDA 12.8 + cuDNN 9 — supports both RTX 4090 (Ada,
#     SM_89) and RTX 5090 (Blackwell, SM_100). CUDA 12.1 does not support
#     Blackwell. CUDA 12.8 is fully backward-compatible with Ada.
#   - `runtime` (not `devel`): ComfyUI does not compile CUDA kernels at build
#     time → smaller image footprint
#   - Avoids manual Python/CUDA installation and version mismatch issues
# ──────────────────────────────────────────────────────────────────────────────
FROM pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime

# ── Pinned versions ───────────────────────────────────────────────────────────
# Any upgrade must go through staging changelog first.
# Official ComfyUI org (as of 2025-2026): Comfy-Org (not comfyanonymous)
# Check releases: https://github.com/Comfy-Org/ComfyUI/releases
ARG COMFYUI_VERSION=v0.16.4

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV COMFYUI_PATH=/app/comfyui

# ── System dependencies ───────────────────────────────────────────────────────
# libgl1 + libglib2.0-0: required by OpenCV (used by some ComfyUI nodes)
# libgomp1: OpenMP, required by some torch operations
# ffmpeg: required for video workflows (Wan 2.2 output processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Torch ecosystem ───────────────────────────────────────────────────────────
# torchvision, torchaudio, xformers MUST come from the PyTorch CUDA 12.8 index.
# Installing xformers from PyPI will silently use a CPU-only build on CUDA hosts,
# degrading performance and VRAM efficiency on the 4090/5090.
RUN pip install --no-cache-dir \
    torchvision \
    torchaudio \
    xformers \
    --index-url https://download.pytorch.org/whl/cu128

# ── ComfyUI Python dependencies ───────────────────────────────────────────────
# Installed separately from ComfyUI's own requirements.txt for layer cache
# efficiency. A change to ComfyUI version does not invalidate this layer.
RUN pip install --no-cache-dir \
    transformers \
    diffusers \
    accelerate \
    safetensors \
    aiohttp \
    einops \
    Pillow \
    numpy \
    scipy \
    scikit-image \
    kornia \
    sentencepiece \
    spandrel \
    av \
    imageio \
    imageio-ffmpeg

# ── ComfyUI ───────────────────────────────────────────────────────────────────
# Pinned to COMFYUI_VERSION. NO model weights baked into the image.
# All models, custom nodes, outputs and inputs come from the network volume
# at runtime via symlinks created by start.sh.
RUN git clone --depth 1 --branch "${COMFYUI_VERSION}" \
    https://github.com/Comfy-Org/ComfyUI /app/comfyui

RUN pip install --no-cache-dir -r /app/comfyui/requirements.txt

# ── Startup script ────────────────────────────────────────────────────────────
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8188

# /system_stats is available once ComfyUI is fully initialised.
# start-period gives start.sh time to complete before checks begin.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f "http://localhost:${COMFYUI_PORT:-8188}/system_stats" || exit 1

ENTRYPOINT ["/app/start.sh"]
