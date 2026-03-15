# LoRA Training Workflow — FLUX.2 Klein 4B

Standard operating procedure for training character LoRA on FLUX.2 Klein Base 4B
using **musubi-tuner** on RunPod (RTX 4090 24GB).

> **ai-toolkit does NOT work with FLUX.2.** Use musubi-tuner only.

---

## Critical Gotchas (Read First)

These are recurring mistakes from v001-v004 training sessions. Read before every run:

### Pod Environment
1. **`export COMFYUI_URL=http://localhost:8188`** must be set in EVERY new SSH session — does not persist.
2. **Pod DNS may be broken** — fix with `echo "nameserver 8.8.8.8" > /etc/resolv.conf` before any `pip install`.
3. **SCP does not work with RunPod** — `subsystem request failed on channel 0`. Use `runpodctl send/receive` or `git push/pull`.
4. **Terminal input limits** — long scripts (>50 lines) cannot be pasted into SSH. Push via git or send via runpodctl instead.
5. **tmux may not be installed** — `apt-get update && apt-get install -y tmux`.
6. **g++ may not be installed** — needed for insightface build: `apt-get install -y g++`.

### ComfyUI Paths & Restart
7. **ComfyUI reads LoRAs from `/app/comfyui/models/loras/`** — NOT `/workspace/ComfyUI/models/loras/`. Always copy finished LoRA to `/app/comfyui/models/loras/`.
8. **ComfyUI models dir is `/app/comfyui/models/`** — verify with: `python3 -c "import sys; sys.path.insert(0,'/app/comfyui'); import folder_paths; print(folder_paths.models_dir)"`.
9. **ComfyUI must be KILLED and RESTARTED** after adding new LoRA files — it caches the file list at startup. PID 13 is the Docker entrypoint; the supervisor auto-restarts it after kill.
```bash
kill -9 $(pgrep -f "python main.py")
sleep 10
# Supervisor auto-restarts. Verify:
curl -s http://localhost:8188/object_info/LoraLoader | python3 -m json.tool | grep "lora_chara"
```

### Training
10. **Kill ComfyUI BEFORE training** to free VRAM: `pkill -9 -f "python main.py"`. Training will OOM if ComfyUI holds GPU memory.
11. **musubi-tuner requires `pip install -e .`** on first use per pod — otherwise `ModuleNotFoundError: No module named 'musubi_tuner'`.
12. **Uninstall xformers** if you get `undefined symbol` errors: `pip uninstall xformers -y`.
13. **Checkpoint filenames use dashes and 8 digits** — format is `lora_chara_v00X-step00000480.safetensors` (NOT underscores or fewer digits).

### Checkpoint Selection
14. **Early checkpoints often beat late ones** — with small datasets (8-15 images), ~40-60 steps/image is the sweet spot. Late checkpoints overfit and produce WORSE face similarity.
    - v003 results: step 480 (FaceSim 0.71) >>> step 800 (0.40) >>> step 1200 (0.49) >>> final (0.47)
    - Always test at least 3 checkpoints before choosing production LoRA.

### runpodctl
15. **runpodctl extracts to CURRENT working directory** — files end up where you ran `runpodctl receive`, NOT in `/workspace/`. Always `cd /workspace` first, then check with `find /workspace -name "lora_chara_v00X" -type d`.
16. **runpodctl on Mac** — install via: `brew install runpod/runpodctl/runpodctl`. If brew not installed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`.

---

## Prerequisites

| Component | Path on Pod |
|-----------|-------------|
| musubi-tuner | `/workspace/musubi-tuner` |
| DiT model | `/workspace/models/flux2_klein_base_4b/flux-2-klein-base-4b.safetensors` |
| VAE (BFL format) | `/workspace/models/vae/flux2-vae-bfl.safetensors` |
| VAE (Diffusers, raw) | `/workspace/models/vae/flux2-vae.safetensors` |
| Text encoder | `/workspace/models/flux2_klein_base_4b/text_encoder/model-00001-of-00002.safetensors` |
| Training root | `/workspace/lora_training/` |
| ComfyUI LoRA dir | `/app/comfyui/models/loras/` |
| ComfyUI models dir | `/app/comfyui/models/` |

### VAE Format Note

musubi-tuner expects **BFL format** VAE (keys like `encoder.down.0.block.0`).
ComfyUI / HuggingFace ships **Diffusers format** (keys like `encoder.down_blocks.0.resnets.0`).

Conversion script: `scripts/convert_vae_diffusers_to_bfl.py`
- Input: `/workspace/models/vae/flux2-vae.safetensors`
- Output: `/workspace/models/vae/flux2-vae-bfl.safetensors`

If `flux2-vae-bfl.safetensors` does not exist on the pod, send the script and run:
```bash
python3 convert_vae_diffusers_to_bfl.py
```

---

## Directory Structure Per Version

```
/workspace/lora_training/chara_v00X/
├── dataset.toml
├── img/
│   ├── image_001.png
│   ├── image_001.txt      # caption
│   ├── image_002.png
│   ├── image_002.txt
│   └── ...
└── output/
    ├── lora_chara_v00X.safetensors              # final
    ├── lora_chara_v00X-step00000110.safetensors  # checkpoint (note: dashes, 8 digits)
    └── ...
```

---

## Step-by-Step

### Step 0 — Prepare Training Images + Captions (Local Mac)

1. Place 10-20 curated PNG images in `~/Desktop/lora_chara_v00X/`
2. Create a `.txt` caption file for **each** image (same filename, different extension)

#### Caption Format (v003+ style)

Use trigger word `chara` at the start. Describe ONLY: clothing, pose, scene, lighting.
**Do NOT describe face or hair features** — let the model learn facial geometry from pixels.

```
chara, a young woman, [clothing], [pose/action], [location], [lighting]
```

Good example:
```
chara, a young woman, wearing a grey crewneck sweatshirt, sitting on a couch, bookshelf in background, warm indoor lighting, smiling at camera
```

Bad example (over-describes face — causes inconsistency with small datasets):
```
chara, young woman with shoulder length wavy brown hair, brown eyes, heart-shaped face, small hoop earrings, wearing a grey sweatshirt...
```

**Exception:** When generating with a DETAILED prompt (for explore/batch), include face features.
For training captions, keep them simple.

### Step 1 — Upload to Pod

**On Mac:**
```bash
cd ~/Desktop && runpodctl send lora_chara_v00X/
```

**On Pod** (replace CODE with the received code):
```bash
cd /workspace                          # IMPORTANT: receive here so files land in /workspace/
runpodctl receive CODE
mkdir -p /workspace/lora_training/chara_v00X/img
mkdir -p /workspace/lora_training/chara_v00X/output

# Files may land in different locations — find them first:
find /workspace -name "lora_chara_v00X" -type d

# Then move (adjust source path based on find result):
mv /workspace/lora_chara_v00X/*.png /workspace/lora_training/chara_v00X/img/
mv /workspace/lora_chara_v00X/*.txt /workspace/lora_training/chara_v00X/img/
```

Verify:
```bash
ls /workspace/lora_training/chara_v00X/img/*.txt | wc -l
ls /workspace/lora_training/chara_v00X/img/*.png | wc -l
```
Both counts must match.

### Step 2 — Create dataset.toml

```bash
cat > /workspace/lora_training/chara_v00X/dataset.toml << 'EOF'
[general]
resolution = [576, 720]
caption_extension = ".txt"
enable_bucket = true

[[datasets]]
batch_size = 1
image_directory = "/workspace/lora_training/chara_v00X/img"
EOF
```

> **Key name is `image_directory`** (not `image_dir`).

### Step 3 — Cache Latents

```bash
cd /workspace/musubi-tuner

python src/musubi_tuner/flux_2_cache_latents.py \
    --dataset_config /workspace/lora_training/chara_v00X/dataset.toml \
    --vae /workspace/models/vae/flux2-vae-bfl.safetensors \
    --model_version klein-base-4b \
    --vae_dtype bfloat16
```

Expected output: one `.safetensors` cache file per image in the `img/` directory.
Log should say `Loaded AE: <All keys matched successfully>`.

### Step 4 — Cache Text Encoder Outputs

```bash
python src/musubi_tuner/flux_2_cache_text_encoder_outputs.py \
    --dataset_config /workspace/lora_training/chara_v00X/dataset.toml \
    --text_encoder /workspace/models/flux2_klein_base_4b/text_encoder/model-00001-of-00002.safetensors \
    --model_version klein-base-4b \
    --batch_size 1
```

### Step 5 — Train

> **IMPORTANT:** Kill ComfyUI first to free VRAM:
> ```bash
> pkill -9 -f "python main.py"
> sleep 5
> ```

```bash
cd /workspace/musubi-tuner

accelerate launch --mixed_precision bf16 --num_cpu_threads_per_process 1 \
    src/musubi_tuner/flux_2_train_network.py \
    --dataset_config /workspace/lora_training/chara_v00X/dataset.toml \
    --dit /workspace/models/flux2_klein_base_4b/flux-2-klein-base-4b.safetensors \
    --model_version klein-base-4b \
    --optimizer_type adamw8bit \
    --learning_rate 1e-4 \
    --network_module networks.lora_flux_2 \
    --network_dim 16 \
    --network_alpha 8 \
    --max_train_steps TOTAL_STEPS \
    --save_every_n_steps SAVE_INTERVAL \
    --output_dir /workspace/lora_training/chara_v00X/output \
    --output_name lora_chara_v00X \
    --fp8_base \
    --fp8_scaled \
    --gradient_checkpointing \
    --mixed_precision bf16 \
    --timestep_sampling flux2_shift \
    --discrete_flow_shift 1.0 \
    --seed 42 \
    --sdpa
```

> **Note:** Do NOT add `--cache_latents` or `--cache_text_encoder_outputs` flags —
> musubi-tuner auto-detects cached files from steps 3-4.

### Step 6 — Deploy to ComfyUI + Test

```bash
# Restart ComfyUI (kill old, supervisor auto-restarts)
kill -9 $(pgrep -f "python main.py")
sleep 15

# Copy best checkpoint to ComfyUI (see Checkpoint Selection below)
cp /workspace/lora_training/chara_v00X/output/lora_chara_v00X.safetensors /app/comfyui/models/loras/

# If testing multiple checkpoints, copy those too:
cp /workspace/lora_training/chara_v00X/output/lora_chara_v00X-step00000NNN.safetensors /app/comfyui/models/loras/

# Restart ComfyUI again so it picks up new files
kill -9 $(pgrep -f "python main.py")
sleep 15

# Verify ComfyUI sees new LoRA
curl -s http://localhost:8188/object_info/LoraLoader | python3 -m json.tool | grep "lora_chara"

# Test
export COMFYUI_URL=http://localhost:8188
cd /workspace/ai-ofm-production-factory
python scripts/run_explore.py \
  --prompt "a photo of chara, young woman wearing grey sweatshirt, sitting on couch, warm indoor lighting, smiling at camera" \
  --lora lora_chara_v00X.safetensors --lora-strength 0.8 --count 10 --format 4:5
```

### Step 7 — Checkpoint Comparison (Important!)

Test at least 3 checkpoints with ArcFace:
```bash
# Install ArcFace deps if needed (pod DNS fix first)
echo "nameserver 8.8.8.8" > /etc/resolv.conf
apt-get update && apt-get install -y g++
pip install insightface onnxruntime-gpu opencv-python-headless

# Run ArcFace on each test session
python scripts/select_training_candidates.py \
  --reference /workspace/lora_training/chara_v00X/img/1.png \
  --input explore_output/SESSION_ID \
  --top 5
```

Pick the checkpoint with highest average FaceSim. With small datasets, early checkpoints usually win.

### Step 8 — Download Best LoRA to Mac

**On Pod:**
```bash
runpodctl send /workspace/lora_training/chara_v00X/output/lora_chara_v00X.safetensors
```

**On Mac:**
```bash
cd ~/Desktop && runpodctl receive CODE
```

Place final LoRA in: `models/lora/lora_chara_v00X.safetensors`

---

## Training Parameters Reference

| Parameter | Value | Notes |
|-----------|-------|-------|
| resolution | 576x720 | 4:5 portrait ratio |
| network_dim | 16 | LoRA rank |
| network_alpha | 8 | alpha = dim/2 |
| learning_rate | 1e-4 | OFM community uses 2e-4 — worth testing |
| optimizer | adamw8bit | memory efficient |
| seed | 42 | reproducibility |
| precision | bf16 + fp8_base + fp8_scaled | fits 24GB VRAM |
| gradient_checkpointing | yes | required for 24GB |

### Scaling Steps to Dataset Size

Rule of thumb: ~100-150 steps per image total, but sweet spot for small datasets is ~40-60 steps/image.

| Images | Total Steps | save_every_n_steps | Checkpoints |
|--------|------------|--------------------|----|
| 8 | 1200 | 80 | 15 |
| 11 | 1650 | 110 | 15 |
| 15 | 2250 | 150 | 15 |
| 20 | 3000 | 200 | 15 |
| 30 | 4500 | 300 | 15 |

---

## Iterative Training Cycle

The character lock process is iterative — each cycle improves hit rate:

```
v001 (16 imgs, text-only) → v002 (10 curated) → v003 (8 best + new captions)
  → v004 (11 = 8 original + 3 generated) → v005 (25-30) → ...
```

### Cycle Steps:
1. Train LoRA on current dataset
2. Find best checkpoint via ArcFace
3. Batch generate 288+ images with best checkpoint
4. ArcFace select top candidates
5. Human review — keep ONLY photos where face = chara
6. Add approved photos to dataset + write captions
7. Train next version → repeat

### Expected Hit Rates:
- 8-10 images: ~20-30% (v003)
- 15 images: ~40-50%
- 25-30 images: ~60-70%
- 40-50 images: ~80-90% (production quality)

### Prompt Strategy for Higher Hit Rate

Simple prompts ("a photo of chara, young woman, casual outfit") produce lower similarity.
**Detailed face-description prompts** + LoRA produce much higher similarity:

```
candid portrait of chara, a 20 year old female university student,
heart-shaped face with soft oval shape, warm brown eyes slightly larger
and rounded, natural soft arch eyebrows, small nose with straight bridge,
natural pink lips with fuller bottom lip, slight dimple, faint freckles,
light brown brunette hair just below shoulder length in loose waves,
small hoop earrings, [clothing], [scene], [lighting],
shot on 85mm f/1.8, authentic candid
```

v003 results: simple prompt FaceSim 0.64 → detailed prompt FaceSim **0.79**.

---

## Troubleshooting

### VAE loading error: "Missing key(s) in state_dict"
VAE is in Diffusers format. Run `convert_vae_diffusers_to_bfl.py` first.

### "image_dir" not found in TOML
Use `image_directory` (not `image_dir`). See musubi-tuner `config_utils.py` line 47.

### Text encoder 401 / gated repo error
FLUX.1-dev and FLUX.1-schnell are gated on HuggingFace. Use the text encoder
bundled with FLUX.2-klein-base-4B (already downloaded).

### ModuleNotFoundError: No module named 'musubi_tuner'
Run `cd /workspace/musubi-tuner && pip install -e .`

### xformers ImportError: undefined symbol
`pip uninstall xformers -y` — pre-installed xformers conflicts with PyTorch version.

### ComfyUI "value_not_in_list" for LoRA
LoRA file exists but ComfyUI hasn't scanned it. Kill and restart ComfyUI (see gotcha #9).

### ComfyUI URL not resolving from inside pod
Use `http://localhost:8188` not the external RunPod proxy URL.

### pip install fails: "Temporary failure in name resolution"
`echo "nameserver 8.8.8.8" > /etc/resolv.conf`

### Terminal cannot accept long commands
Push scripts via git (`git push` on Mac → `git pull` on pod) or send via `runpodctl send`.

### runpodctl files not found after receive
Files extract to current directory. Use `find /workspace -name "lora_chara_v00X" -type d` to locate.

### ComfyUI port already in use
ComfyUI is already running from Docker entrypoint. Just use it: `curl http://localhost:8188/system_stats`.

---

## NSFW Notes (FLUX.2 Klein 4B)

- FLUX.2 Klein generates nudity, breasts, erotic content — NO safety checker in self-hosted ComfyUI
- Does NOT generate explicit genitalia — training data was filtered by Black Forest Labs
- Sufficient for soft/implied NSFW (Fanvue lingerie, topless, artistic nude)
- For explicit NSFW: need FLUX.1 Dev (12B) + Fluxed Up checkpoint or Flux-Uncensored-V2 LoRA
- FLUX.1 Dev LoRAs are NOT compatible with FLUX.2 Klein — separate character LoRA training required

---

## Version History

| Version | Images | Steps | Best Checkpoint | Notes |
|---------|--------|-------|-----------------|-------|
| v001 | 16 | 1450 | final | First training run, VAE conversion discovered |
| v002 | 10 | 1450 | final | Improved curated dataset post-explore workflow |
| v003 | 8 | 1200 | step 480 (FaceSim 0.71) | New caption strategy (no face description). Step 480 >>> 1200 |
| v004 | 11 | 1650 | TBD | 8 original + 3 generated. Testing in progress |
