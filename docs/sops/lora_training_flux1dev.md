# LoRA Training Workflow — FLUX.1 Dev 12B (ai-toolkit)

Standard operating procedure for training character LoRA on **FLUX.1 Dev 12B**
using **ostris/ai-toolkit** on RunPod RTX 4090 24GB.

> This SOP captures two days of trial-and-error from the lily_v001 training session (2026-03-15 to 2026-03-16),
> plus deep research across CivitAI, HuggingFace, GitHub, and 50+ A/B test studies.

---

## Why FLUX.1 Dev (Not FLUX.2 Klein)

We migrated from FLUX.2 Klein 4B to FLUX.1 Dev 12B after hitting a hard ceiling:

| Issue | FLUX.2 Klein 4B | FLUX.1 Dev 12B |
|-------|-----------------|----------------|
| FaceSim ceiling | 0.67-0.69 max (v001-v004 LoRAs) | Higher capacity, TBD |
| Synthetic drift | Training on own outputs averaged identity | Better base quality = less drift |
| IP-Adapter support | None (no adapter exists for Klein) | Yes (FaceID adapters available) |
| Model quality | Decent but 4B is limited for identity | 12B captures fine facial detail |
| Photorealism | Drifts to illustration without filename trick | Native photorealism |
| NSFW | Filtered by BFL (no explicit content) | Full capability self-hosted |
| Community | Small, limited tooling | Largest FLUX community, most LoRA guides |

**Previous Klein LoRA results (archived, NOT compatible with FLUX.1 Dev):**
- v001 (16 imgs): baseline, learned VAE conversion
- v002 (10 imgs): improved curation
- v003 (8 imgs): step 480 FaceSim 0.71 — discovered 60 steps/img sweet spot
- v004 (11 imgs): step 660 FaceSim 0.704 — confirmed sweet spot, synthetic bootstrapping

**Key learning from Klein era:** identity quality is bottlenecked by base model capacity,
not training technique. Moving to 12B was necessary.

---

## Why ai-toolkit (Not musubi-tuner)

We originally planned to use musubi-tuner (used for v001-v004 on Klein). Investigation found:

- **musubi-tuner only has `flux_2_*` and `flux_kontext_*` training scripts** — no vanilla FLUX.1 Dev support
- **ai-toolkit (ostris) has native FLUX.1 Dev support** with `is_flux: true` flag
- ai-toolkit auto-downloads model from HuggingFace in diffusers format
- ai-toolkit handles fp8 quantization, latent caching, EMA, sampling all in one config
- Official example configs exist for 24GB GPUs: `config/examples/train_lora_flux_24gb.yaml`

**Note:** musubi-tuner was excellent for FLUX.2 Klein. If we ever train on Klein again, use musubi-tuner.
See `docs/sops/lora_training_workflow.md` for the Klein SOP.

---

## Why NOT Other Identity Methods

Before training a LoRA, we tried three faster approaches on FLUX.1 Dev. All failed:

| Method | How | Result | Verdict |
|--------|-----|--------|---------|
| IP-Adapter FaceID | Reference image → adapter conditions generation | Copies general style/vibe, NOT face identity | FAILED |
| PuLID | Identity embedding injected into generation | Plastic, artificial faces — uncanny valley | FAILED |
| FLUX.1 Kontext Dev | Image-to-image with identity preservation | Face gets lost in new contexts | FAILED |

**Conclusion:** For FLUX.1 Dev character identity, LoRA training is the only reliable method.
IP-Adapter may still work as a *supplement* at inference time (LoRA + IP-Adapter stacking),
but cannot replace LoRA for primary identity.

---

## Dataset Creation

### Source: Nano Banana Pro (external service)

Since all on-device identity methods failed, we used an external service:
1. Created one high-quality FLUX.1 Dev reference portrait
2. Uploaded to Nano Banana Pro
3. Generated 36 diverse images using multi-prompt generation
4. ArcFace validated: 7 very good, all 36 recommended for training

### Dataset Preparation Script

`scripts/prepare_lily_v001.py` handles:
1. Writing individual captions (.txt) for each image
2. Converting JPG → PNG and resizing (longest side = 1024)
3. Creating dataset.toml (for musubi-tuner, not needed for ai-toolkit)
4. Validating PNG/TXT count match

Output: `~/Desktop/lily_v001_training/` → ready for upload to pod.

### Caption Strategy

**Training captions — SIMPLE (trigger + scene, NO face features):**
```
lily, a young woman wearing a grey crewneck sweatshirt, sitting at a wooden table
in a cafe, holding a coffee cup, window light from the left, smiling at camera
```

**Why no face features in training?** Face descriptions in captions teach the model to associate
identity with *text* rather than *pixels*. Without face descriptions, the LoRA must learn facial
geometry directly from image data → stronger identity lock.

**Generation prompts — DETAILED (include face features):**
```
candid portrait of lily, a 20 year old female, heart-shaped face, warm brown eyes,
natural soft arch eyebrows, small nose, natural pink lips, light brown hair in loose waves,
wearing a denim jacket, city sidewalk, golden hour, shot on 85mm f/1.8
```

This asymmetry (simple training captions + detailed generation prompts) was discovered in v003
and produced a FaceSim jump from 0.64 → 0.79.

### Dataset Composition

Optimal mix for character LoRA:
- **Close-up/headshot: ~40%** — teaches facial detail
- **Lifestyle/scene: ~60%** — teaches identity across contexts

lily_v001 actual: 11 headshots (31%) + 25 lifestyle (69%) — within range.

---

## Critical Gotchas (Read Before Every Run)

These are hard-won from the lily_v001 training session. Every single one caused a crash or multi-hour delay.

### Pod Setup

1. **Use RunPod PyTorch template — NOT ComfyUI template.**
   - ComfyUI is the container entrypoint (PID 1). Killing it kills the entire container and SSH.
   - We discovered this when trying to free RAM: `pkill -f comfyui` → terminal dies → pod crashes.
   - ComfyUI also loads models into RAM on startup, eating 10-20GB.
   - With FLUX.1 Dev needing ~35GB RAM during model load, the 43GB ComfyUI pod OOMed at 100% RAM.
   - **PyTorch template: clean, no background processes, RAM fully available.**
   - Required RAM: **100GB+**. The old 43GB pod was insufficient.
   - Our working pod: RunPod PyTorch 2.4.0 template → 124GB RAM.

2. **tmux not pre-installed** on PyTorch template — install every new pod:
   ```bash
   apt-get update && apt-get install -y tmux
   tmux new -s train
   ```
   ALWAYS train inside tmux. SSH disconnects will not kill training.
   - Detach: `Ctrl+B`, then `D`
   - Reattach: `tmux attach -t train`

3. **PyTorch 2.5.1 required** — RunPod PyTorch template ships 2.4.0, but the latest diffusers
   uses `enable_gqa` in `scaled_dot_product_attention()` which requires PyTorch 2.5+.
   Without upgrade, training crashes with:
   ```
   TypeError: scaled_dot_product_attention() got an unexpected keyword argument 'enable_gqa'
   ```
   Fix:
   ```bash
   pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
   ```
   Warnings about torchaudio/torchvision incompatibility are safe to ignore —
   LoRA training doesn't use them.

4. **Install ai-toolkit requirements** (first time per pod):
   ```bash
   cd /workspace/ai-toolkit
   pip install -r requirements.txt
   ```
   Without this: `ModuleNotFoundError: No module named 'dotenv'`

5. **HF_HOME must point to /workspace** — default `/root/.cache` is on the small Docker overlay
   filesystem (often only 20GB). FLUX.1 Dev download is ~35GB → "Disk quota exceeded".
   ```bash
   export HF_HOME=/workspace/.cache/huggingface
   ```
   **Set this in EVERY SSH session / tmux window before running anything.**
   If you forget and the download starts to `/root/.cache`, it will hit the quota and crash.

6. **HuggingFace login required** — FLUX.1 Dev is a gated model on HuggingFace:
   ```bash
   python -c "from huggingface_hub import login; login(token='YOUR_TOKEN')"
   ```
   - Get token: huggingface.co → Settings → Access Tokens
   - Must also accept FLUX.1 Dev license on the model page
   - Without login: `401 Unauthorized` during download
   - Note: `huggingface-cli login` may not work on PyTorch template (`command not found`).
     Use the Python one-liner above instead.
   - Model auto-downloads on first training run (~35GB → /workspace/.cache/huggingface).
     On subsequent runs, the cache is reused. **Do NOT delete the cache between runs.**

7. **ai-toolkit uses diffusers format** — the local `flux1-dev-fp8.safetensors` (BFL single-file format)
   is NOT compatible. ai-toolkit must download from HuggingFace in diffusers format
   (3 transformer shards + text encoders + VAE, ~35GB total).

### Config Mistakes That Kill Training

8. **Missing `is_flux: true`** in model section → ai-toolkit loads `StableDiffusionPipeline`:
   ```
   ValueError: Pipeline StableDiffusionPipeline expected ['feature_extractor', 'image_encoder',
   'safety_checker', ...] but only {...} were passed.
   ```

9. **Missing `low_vram: true`** → CUDA OOM during model load.
   FLUX.1 Dev in bf16 is ~24GB. RTX 4090 has 23.53GiB usable VRAM.
   Without `low_vram`, ai-toolkit calls `transformer.to(cuda, dtype=bf16)` — moves the FULL
   unquantized model to GPU BEFORE fp8 quantization runs → OOM.
   With `low_vram: true`: quantization happens on CPU first (~5-10 min slower),
   then the quantized ~12GB model moves to GPU. Fits easily with headroom.

10. **Missing `gradient_checkpointing: true`** → CUDA OOM during training,
    even if model loads successfully. Without it, activations fill remaining VRAM.

11. **Missing `noise_scheduler: "flowmatch"`** → incorrect training for FLUX architecture.
    FLUX uses flow matching, not DDPM. Without this setting, the noise schedule is wrong
    and the LoRA learns garbage.

12. **Missing `neg: ""`** in sample section → `ValueError: text input must be of type str`.
    FLUX doesn't use negative prompts, but ai-toolkit passes the neg prompt through the
    tokenizer which expects a string. `None` crashes it. Empty string `""` is fine.

13. **`cache_latents_to_disk: true` + `caption_dropout_rate > 0`** → tokenizer crash.
    These two settings conflict. During latent caching, ai-toolkit also processes captions.
    Caption dropout returns None for some samples, and the tokenizer crashes on None.
    **Don't combine these.** Either use latent caching with dropout=0, or use dropout without caching.

14. **`alpha = rank/2` is wrong for LoRA** — alpha/rank ratio directly scales the effective
    learning rate. The LoRA output is scaled by `alpha/rank`:
    - rank 32 / alpha 16 → scaling factor 0.5 → effective LR = 8e-5 × 0.5 = 4e-5 (too low)
    - rank 16 / alpha 16 → scaling factor 1.0 → effective LR = 1e-4 × 1.0 = 1e-4 (correct)
    **Always use alpha = rank (1:1 ratio)** unless you explicitly want to scale down the LR.

15. **`content_or_style`** — use `"balanced"` for character LoRAs. "style" biases training toward
    late denoising steps (texture/detail), "content" toward early steps (composition).
    Character identity needs BOTH facial detail AND compositional consistency.

---

## Training Parameters — Why Each Value

Every parameter was chosen based on research across 50+ A/B test studies, CivitAI guides,
official ai-toolkit examples, and our own v001-v004 training history.

### Rank: 16 (not 32)

Community consensus for FLUX.1 Dev character LoRA:
- Rank 16 is sufficient for character identity on a 12B model
- Higher ranks show diminishing returns and INCREASE overfitting risk with small datasets (36 imgs)
- CivitAI researcher with 16 published LoRAs: "going higher than 16 gives diminishing returns and may harm outputs"
- Rank 16 = smaller file size, faster training, better generalization
- **If rank 16 underperforms:** retrain with rank 32. But try 16 first.

### Alpha: 16 (1:1 with rank)

This is the most critical and least understood parameter:
- alpha/rank ratio directly scales the effective learning rate
- **rank 32 / alpha 16 = 0.5x effective LR** — this was our original config and was WRONG
- **rank 16 / alpha 16 = 1.0x effective LR** — LR works as intended
- CivitAI research: "When you reduce Rank, keep original Alpha unless you redo LR research"
- Rule: **always set alpha = rank** for predictable LR behavior

### Learning Rate: 1e-4

- Most convergent finding across ALL sources for FLUX character LoRAs
- FLUX is more resilient to LR than SD/SDXL — it tolerates up to 4e-4
- 1e-4 is conservative enough for 36 images while still learning efficiently
- Our previous 8e-5 × 0.5 alpha ratio = effective 4e-5, which was too low

### LR Scheduler: cosine (not constant)

- Cosine naturally reduces LR toward the end of training
- Prevents overfitting in later steps — critical for 36-image dataset
- Constant scheduler keeps LR high throughout → higher overfitting risk
- One CivitAI study used "sine schedule with 2000 step period" with excellent results by step 1300

### Steps: 2500

- Rule of thumb: 40-70 steps per image
- 36 images × 70 = 2520 → rounded to 2500
- Previous Klein findings: ~60 steps/image was optimal (v003: 8 imgs × 60 = 480 sweet spot)
- Sweet spot expected around steps 1250-2000 (50-55 steps/image)
- We save checkpoints every 250 steps to find the exact sweet spot

### EMA: enabled (decay 0.99)

- Exponential Moving Average smooths out learning
- Reduces impact of noisy gradients — important on small (36 img) datasets
- Official ai-toolkit config recommends it: `use_ema: true, ema_decay: 0.99`
- Slight VRAM cost but fits within 24GB with rank 16
- May make model feel "undertrained" → might need slightly more steps

### Optimizer: adamw8bit

- AdamW with 8-bit quantization — standard for memory-constrained training
- Saves 2-3GB VRAM vs full-precision AdamW
- Well-understood, predictable behavior
- Alternative: Prodigy (auto-adjusts LR, set lr=1.0). One user reported Prodigy
  succeeded where adamw8bit failed, but results can be more chaotic. Try if adamw8bit fails.

### Resolution: [768, 1024]

- 512 is too low for facial detail in character LoRAs — excluded
- 1024 captures maximum detail for face geometry
- 768 provides aspect ratio flexibility (our dataset is 4:5 ratio → 928x1152)
- ai-toolkit auto-buckets: our 36 images fell into 672x864 and 800x1024 buckets

### Gradient Checkpointing: true

- Trades compute time for VRAM — stores fewer intermediate activations during forward pass
- **Non-negotiable for 24GB.** Without it, training OOMs after model loads.
- Slight speed reduction (~10-15% slower per step) but enables training at all.

### Caption Dropout: 0.05 (5%)

- 5% of training steps, the caption is dropped (empty string used instead)
- Forces LoRA to learn identity from image features, not from text conditioning alone
- Prevents "trigger word overfitting" — where model only recognizes the character
  when the exact trigger word is present
- Standard value across FLUX LoRA community

### Sampling: every 250 steps, 3 prompts

- Generate 3 test images at steps 250, 500, 750, ..., 2500
- Matches save_every (250 steps) so each checkpoint has corresponding samples
- ~30 seconds overhead per sample point — negligible vs training time
- Prompts cover: studio portrait, outdoor scene, close-up — tests identity across contexts
- `neg: ""` required (FLUX ignores negative prompts but tokenizer needs a string)
- `guidance_scale: 4` — standard for FLUX sampling
- `sample_steps: 20` — enough for quality preview

### Quantization: fp8 + low_vram

- `quantize: true` → fp8 mixed precision, reduces model from ~24GB to ~12GB on GPU
- `low_vram: true` → quantize on CPU first, then move quantized model to GPU
- Without `low_vram`: tries to move full bf16 (~24GB) to 23.53GiB GPU → OOM
- CPU quantization adds ~5-10 min to startup but is necessary for 24GB cards
- `dtype: bf16` for training precision — most stable for FLUX

---

## Prerequisites

| Component | Path on Pod | Notes |
|-----------|-------------|-------|
| ai-toolkit | `/workspace/ai-toolkit` | `git clone https://github.com/ostris/ai-toolkit.git` |
| FLUX.1 Dev | `/workspace/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-dev/` | Auto-downloads ~35GB |
| Training root | `/workspace/lora_training/` | One subdir per training version |
| Config | `/workspace/lora_training/lily_v001/config.yaml` | Written via cat heredoc |
| Dataset | `/workspace/lora_training/lily_v001/img/` | .png + .txt pairs |
| Output | `/workspace/lora_training/lily_v001/output/` | Checkpoints + samples |
| Training log | `/workspace/training.log` | Written by tee during training |

---

## Step-by-Step

### Step 0 — Prepare Dataset (Local Mac)

Use `scripts/prepare_lily_v001.py` as template for new characters.

1. Place curated images in `~/Desktop/lily_dataset/`
2. Run: `python scripts/prepare_lily_v001.py`
3. Output: `~/Desktop/lily_v001_training/` with:
   - `img/` — 36 PNG files (01.png-36.png) + 36 TXT captions (01.txt-36.txt)
   - All resized to max 1024px longest side

Caption rules:
- Trigger word first: `lily, a young woman...`
- Describe ONLY: clothing, pose, scene, lighting, action
- **Do NOT describe face or hair** — let LoRA learn from pixels

Upload to pod:
```bash
# Mac
cd ~/Desktop && runpodctl send lily_v001_training/

# Pod
cd /workspace && runpodctl receive CODE
mkdir -p /workspace/lora_training/lily_v001/{img,output}
mv lily_v001_training/img/* /workspace/lora_training/lily_v001/img/

# Verify
ls /workspace/lora_training/lily_v001/img/*.png | wc -l  # should match image count
ls /workspace/lora_training/lily_v001/img/*.txt | wc -l  # must equal PNG count
```

### Step 1 — New Pod Setup (first time per pod)

```bash
# 1. Install tmux
apt-get update && apt-get install -y tmux
tmux new -s train

# 2. Set HF cache location (CRITICAL — do this FIRST)
export HF_HOME=/workspace/.cache/huggingface

# 3. Upgrade PyTorch 2.4 → 2.5.1 (CRITICAL — diffusers needs enable_gqa)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124

# 4. Install ai-toolkit dependencies
cd /workspace/ai-toolkit
pip install -r requirements.txt

# 5. HuggingFace login (FLUX.1 Dev is gated)
python -c "from huggingface_hub import login; login(token='YOUR_HF_TOKEN')"

# 6. Verify
python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.cuda.is_available()}')"
free -h  # should show 100GB+ total RAM
```

### Step 2 — Write Config

```bash
cat > /workspace/lora_training/lily_v001/config.yaml << 'EOF'
job: extension
config:
  name: "lora_lily_v001"
  process:
    - type: "sd_trainer"
      training_folder: "/workspace/lora_training/lily_v001/output"
      device: "cuda:0"
      trigger_word: "lily"

      model:
        name_or_path: "black-forest-labs/FLUX.1-dev"
        is_flux: true            # MUST have — without it loads StableDiffusionPipeline
        quantize: true           # fp8 quantization — fits 24GB VRAM
        low_vram: true           # quantize on CPU — prevents OOM on 23.53GiB GPU

      network:
        type: "lora"
        linear: 16               # rank 16 — sufficient for character identity
        linear_alpha: 16         # alpha = rank (1:1 — effective LR not scaled)

      save:
        dtype: float16
        save_every: 250          # 10 checkpoints over 2500 steps
        max_step_saves_to_keep: 10

      datasets:
        - folder_path: "/workspace/lora_training/lily_v001/img"
          caption_ext: "txt"
          caption_dropout_rate: 0.05    # 5% — prevents trigger overfitting
          resolution: [768, 1024]       # multi-res (no 512 — too low for face detail)
          default_caption: "lily"
          # NOTE: do NOT add cache_latents_to_disk with caption_dropout > 0

      train:
        batch_size: 1
        steps: 2500              # ~70 steps/image for 36 images
        gradient_accumulation_steps: 1
        train_unet: true
        train_text_encoder: false
        gradient_checkpointing: true    # MUST have for 24GB
        noise_scheduler: "flowmatch"    # MUST have for FLUX architecture
        optimizer: "adamw8bit"
        lr: 1e-4                 # standard for FLUX character LoRA
        lr_scheduler: "cosine"   # prevents overfitting in later steps
        content_or_style: "balanced"
        dtype: bf16
        ema_config:
          use_ema: true
          ema_decay: 0.99

      sample:
        sampler: "flowmatch"     # must match noise_scheduler
        sample_every: 250
        width: 1024
        height: 1024
        prompts:
          - "lily, a young woman wearing a grey crewneck t-shirt, head and shoulders portrait, neutral expression, white background, studio lighting"
          - "lily, a young woman wearing a denim jacket, standing on a city sidewalk, golden hour sunlight, slight smile"
          - "lily, a young woman, close-up headshot, bare shoulders, white background, soft natural lighting"
        neg: ""                  # MUST have — FLUX ignores it but tokenizer needs a string
        seed: 42
        walk_seed: true
        guidance_scale: 4
        sample_steps: 20
EOF
```

### Step 3 — Run Training

```bash
export HF_HOME=/workspace/.cache/huggingface
cd /workspace/ai-toolkit
python run.py /workspace/lora_training/lily_v001/config.yaml 2>&1 | tee /workspace/training.log
```

First run: downloads FLUX.1 Dev (~35GB) + CPU quantization = ~15-20 min startup.
Subsequent runs: ~5-10 min startup (HF cache reused, still needs CPU quantization).

**Expected output sequence:**
```
Loading Flux model
Loading transformer
Loading checkpoint shards: 100% | 3/3       ← 3 transformer shards (~24GB total)
Quantizing transformer                       ← CPU quantization (low_vram mode, ~5 min)
Loading VAE
Loading T5
Loading checkpoint shards: 100% | 2/2        ← T5-XXL text encoder
Quantizing T5
Loading CLIP
Making pipe
Preparing Model
create LoRA network. base dim (rank): 16, alpha: 16
create LoRA for Text Encoder: 0 modules.     ← correct, we don't train text encoder
create LoRA for U-Net: 494 modules.          ← 494 LoRA modules on transformer
enable LoRA for U-Net
Dataset: /workspace/lora_training/lily_v001/img
  - Found 36 images
Bucket sizes:
672x864: 36 files                            ← bucket 1
800x1024: 36 files                           ← bucket 2
Generating baseline samples before training  ← 3 initial images (seed 42)
lora_lily_v001: 0% | 2/2500 [lr: 1.0e-04 loss: 3.594e-01]  ← TRAINING STARTED
```

Training speed: ~2.5 sec/step → **~1.7 hours** for 2500 steps.
VRAM usage: ~15-18GB during training (~6-8GB headroom).

### Step 4 — Monitor Progress

Detach from tmux (training continues in background):
```
Ctrl+B, then D
```

Reattach:
```bash
tmux attach -t train
```

Check training log from another terminal:
```bash
tail -f /workspace/training.log
```

Sample images appear in:
```
/workspace/lora_training/lily_v001/output/lora_lily_v001/samples/
```

**What to look for in samples:**
- Step 250: blurry, identity barely visible — normal
- Step 500: face shape emerging, still generic
- Step 1000: clear identity forming, should look like lily
- Step 1500: strong identity, good detail — likely near sweet spot
- Step 2000: if still improving, great; if degrading, 1500 was better
- Step 2500: check for overfitting (same face in every pose, loss of variety)

### Step 5 — Checkpoint Selection

Checkpoints saved to:
```
/workspace/lora_training/lily_v001/output/lora_lily_v001/
  lora_lily_v001_step00000250.safetensors
  lora_lily_v001_step00000500.safetensors
  ...
  lora_lily_v001_step00002500.safetensors
```

**Sweet spot expected: steps 1250-2000** (~50-55 steps/image).
Previous Klein findings: step = images × 60 consistently won across v003 and v004.

Evaluate with ArcFace (install on pod):
```bash
apt-get update && apt-get install -y build-essential
pip install insightface onnxruntime-gpu opencv-python-headless
```

Visual evaluation: compare sample images at each step.
Quantitative: generate 10 images per checkpoint with ComfyUI, run ArcFace scoring.

### Step 6 — Download Best LoRA

**On Pod:**
```bash
runpodctl send /workspace/lora_training/lily_v001/output/lora_lily_v001/lora_lily_v001_step00001500.safetensors
```

**On Mac:**
```bash
cd ~/Desktop && runpodctl receive CODE
```

Place in repo: `models/lora/lora_lily_v001.safetensors`

---

## File Transfer Notes (runpodctl)

- **SCP does not work with RunPod** — `subsystem request failed on channel 0`. Use runpodctl.
- **runpodctl v2.1.6 binary was 404** — we used v1.14.3 instead
- **send and receive must run simultaneously** — keep Mac terminal open during transfer
- **"file already exists" error** — delete the old file first, then retry
- **Files extract to CWD** — always `cd /workspace` before `runpodctl receive`
- **Install on Mac:** `brew install runpod/runpodctl/runpodctl`

---

## Training Parameters Reference

| Parameter | Value | Why |
|-----------|-------|-----|
| Model | FLUX.1 Dev 12B | Best open-source, 12B capacity for identity, full NSFW |
| quantize | fp8 | 24GB → ~12GB model on GPU |
| low_vram | true | CPU quantization prevents OOM (bf16 model > GPU VRAM) |
| rank | 16 | Sufficient for character, less overfitting than 32 |
| alpha | 16 | 1:1 with rank — effective LR = lr × 1.0 |
| lr | 1e-4 | Standard for FLUX character LoRA |
| lr_scheduler | cosine | Natural LR decay prevents late overfitting |
| optimizer | adamw8bit | Memory efficient, predictable |
| gradient_checkpointing | true | Required for 24GB VRAM |
| noise_scheduler | flowmatch | Required for FLUX architecture |
| EMA | decay 0.99 | Smooths small-dataset training |
| dtype | bf16 | Training precision |
| save dtype | float16 | Checkpoint format (compatible with ComfyUI) |
| caption_dropout | 0.05 | Prevents trigger overfitting |
| content_or_style | balanced | Character needs both face detail + composition |
| steps | 2500 | ~70/image for 36 images |
| save_every | 250 | 10 checkpoints for sweet spot search |
| resolution | [768, 1024] | No 512 (too low for faces) |
| batch_size | 1 | Minimum for 24GB |
| neg | "" | Required by tokenizer even though FLUX ignores it |

### Steps Formula

```
total_steps = num_images × 70           # conservative
total_steps = num_images × 50           # aggressive
save_every  = total_steps / 10          # 10 checkpoints
sweet_spot  ≈ num_images × 50-60       # historically optimal
```

### Scaling by Dataset Size

| Images | Total Steps | save_every | Expected Sweet Spot |
|--------|------------|------------|---------------------|
| 10 | 700 | 70 | ~500-600 |
| 20 | 1400 | 140 | ~1000-1200 |
| 36 | 2500 | 250 | ~1500-2000 |
| 50 | 3500 | 350 | ~2500-3000 |

---

## Pod Specifications (Tested Working)

| Setting | Value |
|---------|-------|
| Template | RunPod PyTorch 2.4.0 (then upgrade to 2.5.1) |
| GPU | RTX 4090 24GB |
| System RAM | 124GB (100GB+ required) |
| Container disk | 50GB |
| Volume | /workspace (persistent across restarts) |
| Docker image | runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04 |

**Do NOT use:**
- Custom ComfyUI template (PID1 issue, RAM contention)
- Pods with < 100GB system RAM (OOM during model load)
- Pods with < 50GB container disk (HF cache + checkpoints)

---

## Troubleshooting

### CUDA OOM during model load
`low_vram: true` missing in model section. Add it.

### StableDiffusionPipeline error
`is_flux: true` missing in model section. Add it.

### `scaled_dot_product_attention() got unexpected keyword 'enable_gqa'`
PyTorch 2.4 installed. Upgrade:
```bash
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
```

### `text input must be of type str` (tokenizer crash)
`neg: ""` missing from sample section. Add it.
Can also be caused by `cache_latents_to_disk: true` + `caption_dropout_rate > 0` — remove caching.

### `ModuleNotFoundError: No module named 'dotenv'`
```bash
cd /workspace/ai-toolkit && pip install -r requirements.txt
```

### `Disk quota exceeded` during HF download
HF_HOME points to Docker overlay. Fix:
```bash
export HF_HOME=/workspace/.cache/huggingface
```
If cache already partially downloaded to /root, delete it:
```bash
rm -rf /root/.cache/huggingface
```

### `401 Unauthorized` downloading FLUX.1 Dev
HF login missing or FLUX.1 Dev license not accepted. Fix:
```bash
python -c "from huggingface_hub import login; login(token='TOKEN')"
```
Also accept license at: huggingface.co/black-forest-labs/FLUX.1-dev

### Training OOM (after model loads)
`gradient_checkpointing: true` missing in train section. Add it.

### `huggingface-cli: command not found`
Use Python one-liner instead:
```bash
python -c "from huggingface_hub import login; login(token='TOKEN')"
```

### `error creating container: image pull pending` (RunPod)
Docker Hub rate limit or RunPod infrastructure issue. Wait and retry, try different region,
or use a different template.

### Pod RAM at 100% → pod crashes
ComfyUI or other processes consuming RAM. Use PyTorch template (no background processes).
If already on PyTorch template: check `free -h` before training. If less than 50GB free,
investigate with `ps aux --sort=-%mem | head`.

---

## Iterative Training Cycle

Same approach that worked for Klein v001→v004, now on FLUX.1 Dev:

```
v001 (36 imgs, Nano Banana generated) → evaluate → v002 (add best generated) → ...
```

1. Train LoRA on current dataset
2. Find best checkpoint via sample images + ArcFace
3. Batch generate 200+ images with best checkpoint (ComfyUI explore workflow)
4. ArcFace select top candidates (highest face similarity to reference)
5. Human review — keep ONLY photos where face = character
6. Add approved photos to dataset + write captions
7. Train next version → repeat

**Expected progression:**
- 10 images: ~20-30% hit rate
- 30 images: ~50-60% hit rate
- 50+ images: ~80-90% hit rate (production quality)

---

## Inference Identity Lock (Beyond LoRA)

LoRA alone is necessary but often not sufficient for top-tier consistency.
Best results stack multiple methods:

1. **Base model** — FLUX.1 Dev 12B (good skin micro-texture)
2. **LoRA** — character identity (this SOP)
3. **IP-Adapter FaceID** — inference-time conditioning (failed alone but may help WITH LoRA)
4. **Detailed face-description prompts** — explicitly describe facial features at generation time
5. **Post-processing** — Real-ESRGAN upscale + subtle film grain

The prompt asymmetry trick (simple training captions + detailed generation prompts) boosted
FaceSim from 0.64 → 0.79 in Klein v003. Apply same strategy with FLUX.1 Dev.

---

## Version History

| Version | Model | Images | Steps | Rank | Best Checkpoint | FaceSim | Notes |
|---------|-------|--------|-------|------|-----------------|---------|-------|
| Klein v001 | FLUX.2 Klein 4B | 16 | 1450 | 16 | final | — | First run, VAE conversion |
| Klein v002 | FLUX.2 Klein 4B | 10 | 1450 | 16 | final | — | Improved curation |
| Klein v003 | FLUX.2 Klein 4B | 8 | 1200 | 16 | step 480 | 0.71 | New caption strategy, 60 steps/img |
| Klein v004 | FLUX.2 Klein 4B | 11 | 1650 | 16 | step 660 | 0.704 | +3 generated, sweet spot confirmed |
| **Dev v001** | **FLUX.1 Dev 12B** | **36** | **2500** | **16** | **TBD** | **TBD** | **ai-toolkit, rank 16/alpha 16, cosine** |

---

## Appendix A: lily_v001 Training Log (FLUX.1 Dev)

Complete chronological record of the first FLUX.1 Dev LoRA training session.
Reference for future training runs — shows every problem encountered and how it was solved.

### Timeline

**Day 1 — 2026-03-15 (Saturday)**

| Time | Action | Result |
|------|--------|--------|
| Morning | Created dataset preparation script `scripts/prepare_lily_v001.py` | 36 PNG + 36 TXT captions generated from lily_dataset JPGs |
| Morning | Ran prepare script on Mac | Output: `~/Desktop/lily_v001_training/` — 36 images resized to max 1024px |
| Afternoon | Investigated musubi-tuner for FLUX.1 Dev | FAILED — only has `flux_2_*` and `flux_kontext_*` scripts, no vanilla FLUX.1 Dev |
| Afternoon | Switched to ai-toolkit (ostris) | Has native FLUX.1 Dev support with `is_flux: true` |
| Afternoon | Uploaded dataset to pod via runpodctl | runpodctl v2.1.6 was 404, used v1.14.3. DNS fix needed: `echo "nameserver 8.8.8.8" > /etc/resolv.conf` |
| Afternoon | Installed ai-toolkit on pod | `git clone` + `pip install -r requirements.txt` |
| Afternoon | First training attempt — `is_flux: true` missing | CRASHED: `StableDiffusionPipeline expected [...]` |
| Afternoon | Second attempt — no `low_vram: true` | CRASHED: CUDA OOM. Full bf16 model (24GB) → 23.53GiB GPU |
| Afternoon | HF download to /root/.cache | CRASHED: `Disk quota exceeded`. Fixed: `export HF_HOME=/workspace/.cache/huggingface` |
| Afternoon | HF download without auth | CRASHED: `401 Unauthorized`. Fixed: `huggingface-cli login` |
| Evening | Download with auth | "receiver dropped" — network error on second transformer shard |
| Evening | Aggressive disk cleanup | Removed ~60GB: video_models, kontext, clip_vision, ipadapter-flux, pulid, facexlib, old HF cache |
| Evening | Third training attempt | CRASHED: RAM 100% (42.84/42.84 GiB). ComfyUI + FLUX.1 Dev load competing for RAM |
| Evening | Tried to kill ComfyUI | Terminal died — ComfyUI is PID 1 on the ComfyUI template |
| Evening | Pod crashed (OOM) | Could not SSH back in |
| Late night | Tried new pod with PyTorch template | Docker image pull errors — RunPod infra issue |
| Late night | Session ended | Decided to retry next day |

**Day 2 — 2026-03-16 (Sunday)**

| Time | Action | Result |
|------|--------|--------|
| Morning | New pod: RunPod PyTorch 2.4.0, RTX 4090, 50GB container | Pod started successfully. 124GB RAM! |
| Morning | Verified /workspace persistence | ai-toolkit, dataset, HF cache all intact from previous pod |
| Morning | `tmux new -s train` | `bash: tmux: command not found`. Fixed: `apt-get update && apt-get install -y tmux` |
| Morning | `huggingface-cli login` | `command not found`. Fixed: `python -c "from huggingface_hub import login; login(token='...')"` |
| Morning | `pip install -r requirements.txt` → run training | CRASHED: `ModuleNotFoundError: No module named 'dotenv'` — forgot to install requirements |
| Morning | Installed requirements, ran training | Model loaded, quantized on CPU... |
| Morning | Training attempt — no `low_vram: true` initially | CRASHED: CUDA OOM. Added `low_vram: true` |
| ~12:15 | Training with `low_vram: true` | SUCCESS: "Quantizing transformer" on CPU. Model loaded! |
| ~12:15 | But then tokenizer error | CRASHED: `ValueError: text input must be of type str` during "Generating baseline samples" |
| ~12:20 | Investigated error — missing `neg: ""` | The sample section passes None to tokenizer for negative prompt |
| ~12:25 | Fixed config, retried | CRASHED: `TypeError: scaled_dot_product_attention() got unexpected keyword 'enable_gqa'` |
| ~12:30 | Diagnosed: PyTorch 2.4 vs diffusers needing 2.5+ | `pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124` |
| ~12:35 | PyTorch upgraded, retried training | SUCCESS! |
| ~12:39 | **TRAINING STARTED** | `lora_lily_v001: 0% | 2/2500 [lr: 1.0e-04 loss: 3.594e-01]` at ~2.45s/step |
| ~12:40 | Documented everything in SOP | Created `docs/sops/lora_training_flux1dev.md` |

### Errors Encountered (in order)

1. **musubi-tuner has no FLUX.1 Dev scripts** → switched to ai-toolkit
2. **runpodctl v2.1.6 binary 404** → used v1.14.3
3. **Pod DNS broken** → `echo "nameserver 8.8.8.8" > /etc/resolv.conf`
4. **runpodctl "file already exists"** → `rm ~/Desktop/lily_v001_training.zip`
5. **`StableDiffusionPipeline` error** → added `is_flux: true`
6. **CUDA OOM during load** → added `low_vram: true`
7. **Disk quota exceeded** → `export HF_HOME=/workspace/.cache/huggingface`
8. **401 Unauthorized** → `huggingface-cli login` (gated model)
9. **"receiver dropped"** → network error, retried download
10. **RAM 100% (43GB pod)** → ComfyUI competing with FLUX.1 Dev load
11. **Killing ComfyUI kills container** → ComfyUI is PID 1 on that template
12. **Docker image pull errors** → RunPod infrastructure issue, waited
13. **tmux not installed** → `apt-get update && apt-get install -y tmux`
14. **`huggingface-cli: command not found`** → use Python one-liner instead
15. **`ModuleNotFoundError: No module named 'dotenv'`** → `pip install -r requirements.txt`
16. **CUDA OOM (second pod, no `low_vram`)** → confirmed `low_vram: true` is mandatory
17. **`ValueError: text input must be of type str`** → added `neg: ""` to sample section
18. **`TypeError: enable_gqa`** → upgraded PyTorch 2.4 → 2.5.1

### Final Working Config (what actually ran)

```yaml
job: extension
config:
  name: "lora_lily_v001"
  process:
    - type: "sd_trainer"
      training_folder: "/workspace/lora_training/lily_v001/output"
      device: "cuda:0"
      trigger_word: "lily"
      model:
        name_or_path: "black-forest-labs/FLUX.1-dev"
        is_flux: true
        quantize: true
        low_vram: true
      network:
        type: "lora"
        linear: 16
        linear_alpha: 16
      save:
        dtype: float16
        save_every: 250
        max_step_saves_to_keep: 10
      datasets:
        - folder_path: "/workspace/lora_training/lily_v001/img"
          caption_ext: "txt"
          caption_dropout_rate: 0.05
          resolution: [768, 1024]
          default_caption: "lily"
      train:
        batch_size: 1
        steps: 2500
        gradient_accumulation_steps: 1
        train_unet: true
        train_text_encoder: false
        gradient_checkpointing: true
        noise_scheduler: "flowmatch"
        optimizer: "adamw8bit"
        lr: 1e-4
        lr_scheduler: "cosine"
        content_or_style: "balanced"
        dtype: bf16
        ema_config:
          use_ema: true
          ema_decay: 0.99
      sample:
        sampler: "flowmatch"
        sample_every: 250
        width: 1024
        height: 1024
        prompts:
          - "lily, a young woman wearing a grey crewneck t-shirt, head and shoulders portrait, neutral expression, white background, studio lighting"
          - "lily, a young woman wearing a denim jacket, standing on a city sidewalk, golden hour sunlight, slight smile"
          - "lily, a young woman, close-up headshot, bare shoulders, white background, soft natural lighting"
        neg: ""
        seed: 42
        walk_seed: true
        guidance_scale: 4
        sample_steps: 20
```

### Final Working Pod Setup Commands (copy-paste ready)

```bash
# 1. SSH into pod
ssh PODID@ssh.runpod.io -i ~/.ssh/id_ed25519

# 2. Install tmux + create session
apt-get update && apt-get install -y tmux
tmux new -s train

# 3. Set HF cache (MUST be first)
export HF_HOME=/workspace/.cache/huggingface

# 4. Upgrade PyTorch (MUST do before training)
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124

# 5. Install ai-toolkit deps (if new pod)
cd /workspace/ai-toolkit && pip install -r requirements.txt

# 6. HF login (if new pod)
python -c "from huggingface_hub import login; login(token='YOUR_TOKEN')"

# 7. Write config (cat heredoc) — see Final Working Config above

# 8. Run training
cd /workspace/ai-toolkit
python run.py /workspace/lora_training/lily_v001/config.yaml 2>&1 | tee /workspace/training.log

# 9. Detach tmux
# Ctrl+B, then D

# 10. Reattach later
tmux attach -t train
```

### Dataset Details (36 images)

Source: Nano Banana Pro from single FLUX.1 Dev reference photo.
All images 4:5 ratio (928x1152), resized to max 1024px by prepare script.

**Composition:**
- 11 close-up/headshot/portrait (31%): lily_2, 3, 5, 7, 8, 9, 10, 35, 36, 4, 6
- 25 lifestyle/scene (69%): lily_1, 12-34

**Caption examples:**
```
01.txt: lily, a young woman wearing a grey university crewneck sweatshirt, sitting at a wooden table in a cafe, holding a coffee cup, window light from the left, smiling at camera
02.txt: lily, a young woman, bare shoulders, extreme close-up headshot, facing camera directly, neutral expression, white background, flat even lighting
13.txt: lily, a young woman wearing an olive green field jacket over a brown t-shirt and jeans, walking on a city sidewalk, carrying a brown leather bag, golden hour sunlight, pedestrians in background
```

**Caption rules applied:**
- Trigger word "lily" always first
- Describe clothing, pose, scene, lighting, action
- NO face features (no "brown eyes", "wavy hair", etc.)
- Let LoRA learn facial identity from pixels only

### Training Metrics (initial)

- Start: step 2/2500, loss 0.359, lr 1e-4
- Speed: ~2.45 sec/step
- Estimated total: ~1.7 hours
- VRAM: ~15-18GB (6-8GB headroom on 24GB)
- RAM: 124GB total, ~35GB used during model load, stabilized after

### Config Evolution (what changed and why)

| Version | Change | Reason |
|---------|--------|--------|
| Draft 1 | rank 32, alpha 16, lr 8e-5, constant | Initial research-based config |
| Draft 2 | Added `is_flux: true` | Without it: StableDiffusionPipeline error |
| Draft 3 | Added `low_vram: true` | Without it: CUDA OOM during model load |
| Draft 4 | Added `gradient_checkpointing`, `noise_scheduler: flowmatch`, `train_unet/text_encoder` | Official config comparison — 4 missing critical settings |
| Draft 5 | rank 16, alpha 16, lr 1e-4, cosine, EMA | Deep research: 50+ A/B tests, CivitAI community consensus |
| Draft 6 | Added `neg: ""` | Tokenizer crash on None negative prompt |
| Draft 7 | Removed `cache_latents_to_disk` | Conflicts with `caption_dropout_rate > 0` |
| **Final** | PyTorch 2.5.1 upgrade | diffusers `enable_gqa` requires PyTorch 2.5+ |

### What We Learned (Key Takeaways)

1. **Infrastructure is half the battle.** 10 of 18 errors were environment/pod issues, not training config.
2. **Official example configs exist** — `config/examples/train_lora_flux_24gb.yaml` would have prevented 4 errors.
3. **alpha = rank is critical** — alpha/rank scaling of effective LR is poorly documented but hugely impactful.
4. **ComfyUI template is wrong for training** — use PyTorch template, no background processes.
5. **100GB+ RAM is mandatory** — 43GB is not enough for FLUX.1 Dev model loading.
6. **PyTorch version matters** — latest diffusers needs features from PyTorch 2.5+.
7. **`2>&1 | tee /workspace/training.log`** — always capture logs, scroll history is unreliable.
8. **tmux is mandatory** — SSH disconnects are common, losing a 2-hour training run is unacceptable.
9. **HF_HOME on /workspace** — default path runs out of disk quota on Docker overlay.
10. **Test sampling config early** — `neg: ""` bug only surfaces when sampling runs.
