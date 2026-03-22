# Chroma 1 HD — Knowledge Base

Base model for AI OFM Production Factory. Selected 2026-03-20 after FLUX.2 Klein and FLUX.1 Dev
failed to produce publishable NSFW content (anatomy "flux static", LoRA stacking identity drift).

Chroma 1 HD is truly uncensored — natively trained on explicit content, no alignment filtering.

---

## Forum Knowledge

Community intelligence collected from CivitAI, Reddit, Discord, and GitHub.
Sources verified against multiple independent users where possible.

### Training — Recommended Toolchain

**⚠️ CRITICAL UPDATE:** ai-toolkit is **NOT recommended** for Chroma.
Source (levzzz Chroma guide): "AI-toolkit is not recommended due to having potential issues and lacking optimization."

**Recommended trainers (in order):**

| Trainer | Notes |
|---------|-------|
| **OneTrainer** | **Recommended** — powerful GUI, lots of settings |
| **diffusion-pipe** | Longest Chroma support, battle-tested |
| **kohya-ss/sd-scripts** | Use `sd3` branch for Chroma support |
| ~~ai-toolkit~~ | ~~Not recommended~~ — potential issues, lacks optimization |

**Our plan:** Use **OneTrainer** (GUI) or **diffusion-pipe** for `lora_lily_chroma_v001`.

---

### Training — Critical Differences from FLUX

**Chroma is MORE SENSITIVE to training than FLUX.**
You cannot reuse FLUX training parameters and expect the same results.

| Parameter | FLUX.1 Dev (our v001) | Chroma 1 HD (community consensus) |
|-----------|----------------------|-----------------------------------|
| Learning Rate | 1e-4 | **5e-5 to 7e-5** (significantly lower) |
| LR Schedule | cosine | **decaying LR across time** |
| Steps (batch 1) | 2500 (36 imgs) | **5000–7000** (same dataset size range) |
| Sensitivity | Tolerant up to 4e-4 | Breaks down at FLUX-level LR |

Source (CivitAI):
> "You can't train a Chroma1-HD LoRA on the exact same parameters than flux and expect
> the same results. LoRA training parameters must be tailored to each model. Chroma1-HD
> is much more sensitive to LR. If you use the same LR than flux it's going to break down."

> "I had great Chroma LoRA results starting at LR 0.00005 with a decaying LR across time,
> and total steps around 5000 to 7000 steps at batch 1."

**Takeaway:** LR range: **5e-5 to 7e-5**. Steps: **5000–7000**. Decaying LR schedule. Use OneTrainer or diffusion-pipe.

### Identity Drift — Known Issue, Solvable

> "Chroma vs flux 1 dev Lora I have trained my Lora with both flux1-d and chroma HD.
> Same exact data set and captions. My flux Lora is amazing and I love the results but
> my chroma HD Lora drifts in likeness very easily."

**Root cause: captions.** Chroma was trained using Gemini-generated captions.
It expects more descriptive prompts than FLUX.

> "It's most likely your captions. Chroma was trained using captions from Gemini,
> and likes a bit more descriptive prompts than Flux."

**Solution — Gemini-style descriptive captions:**
- Use Gemini to optimize prompts in its own captioning language
- Alternative: JoyCaption via TagGUI (confirmed working)
- Prompt for TagGUI: `Write a descriptive prompt for this image in 150 words or less.
  ONLY describe the most important elements of the image.`
- Use "Start caption with" field for trigger word: `An image of [trigger_word]`
- Edit down generated captions — remove fluff, reorder sentences

**Caption format (confirmed working):**
```
An image of [trigger_word] [single sentence: what character is doing].
[Anything different than typical about the character].
[Scene description, lighting, background — 2-3 sentences].
```

**Example:**
```
An image of bob_the_gunfighter sitting at a table in a wild west saloon playing poker
at night staring directly ahead with a determined look. He is sitting at the table his
cards laying face down in front of him and his right hand reaching for the holster at
his hip. Three other players are sitting nervously around the table. In the background
are several people sitting at a bar to the left and a man dressed similarly to him is
standing at the top of the stairs his gun out. The lighting is dim, illuminated by the
soft glow of oil lamps.
```

**Impact on our pipeline:** Our FLUX captions were SHORT by design (trigger + scene, no face features).
For Chroma we likely need to re-caption the entire dataset with Gemini-style descriptive captions.
This is a significant change from our FLUX approach.

### Dataset Composition for Character LoRA

Recommended mix (from experienced Chroma LoRA creator):

| Shot Type | Percentage | Notes |
|-----------|-----------|-------|
| Face / neck / shoulders (close-up) | 10–15% | Identity anchor |
| Full body standing | 10–15% | Body proportions |
| Upper body + face | 30–40% | Primary training target |
| Various poses / activities | 30–50% | Running, throwing, sitting, etc. |

> "Variety of distances, angles and positions helps."
> "If the face doesn't come out good I'll add a few more face images, same with full body."

**Comparison to our lily_v001 dataset:**
- Our dataset: 31% close-up, 69% lifestyle — close-up percentage is HIGH for Chroma
- Chroma recommendation: much more upper body + face (30-40%), less pure close-up
- Our dataset has 0% full body standing — this is a gap
- Action: for Chroma v001, consider rebalancing or expanding dataset

### Prompting

→ See [chroma_prompting.md](chroma_prompting.md) for full prompting guide, negative prompts, samplers, schedulers, CFG, and dataset captioning.

**Key facts:**
- Chroma was trained with negatives — always provide a negative prompt (unlike FLUX)
- Natural language sentences only — no comma-separated tags
- Gemini 1.5 Flash for dataset captioning — mandatory (same tool used in Chroma training)

### ControlNet Compatibility

FLUX ControlNets work with Chroma.

> "Controlnets для Flux работают с Chroma! В примере используется tile controlnet от Jasper AI."

This means our future inpainting/detailer workflow can use existing FLUX ControlNet ecosystem.

### Performance Optimization

**MagCache** — now works with Chroma. 2x+ speedup but at cost of detail.
- Simple images: effect barely noticeable
- Detailed scenes: very noticeable quality loss
- Composition stays similar — only details affected
- Use case: **fast prompt testing / exploration batch**, NOT hero generation
- Settings: check recommended settings on the GitHub page. Selecting "chroma" in the node
  does NOT auto-change values.

**Other acceleration methods:**
- Torch compile (Triton) — known, established
- SageAttention — known, established

### Samplers & Schedulers

→ See [chroma_prompting.md](chroma_prompting.md) for full sampler ranking and scheduler parameters.

**Summary:** `res_multistep` > `euler` at same speed. Beta scheduler at 0.4/0.4 (shift=1). 26 steps default.

---

## Architecture Notes

Source: official HuggingFace README — `lodestones/Chroma1-HD`

### Overview

- **Parameters:** 8.9B (trimmed from FLUX.1-schnell's 12B)
- **Base architecture:** FLUX.1-schnell
- **License:** Apache 2.0 — fully open, commercial use allowed, no restrictions
- **Purpose:** designed as a **base model for finetuning** — neutral foundation, not production-tuned
- **Training data:** 5M sample curated dataset from a 20M pool — artistic, photographic, niche styles
- **Alignment:** released in **uncensored state**, no safety filter applied
- **Version note:** Chroma1-HD = Chroma-v.50

### Architectural Modifications vs FLUX.1-schnell

Three significant changes from the base FLUX architecture:

**1. Parameter reduction: 12B → 8.9B**
- Replaced a 3.3B parameter timestep-encoding layer with a 250M parameter FFN
- Original layer was vastly oversized for its task — this is more efficient, not a downgrade

**2. MMDiT Masking**
- T5 padding tokens are masked during training
- Prevents model from attending to irrelevant `<pad>` tokens
- Result: higher fidelity output, increased training stability

**3. Custom Timestep Distributions**
- Custom sampling distribution (`-x^2`) instead of standard
- Prevents loss spikes during training
- Ensures effective training on both high-noise and low-noise regions

### Why These Modifications Matter for Us

- The timestep-encoding replacement means Chroma behaves differently from FLUX at the scheduler level — this explains why BetaSamplingScheduler and ModelSamplingAuraFlow (flow shift) are used instead of FLUX's flowmatch
- MMDiT masking = cleaner prompt adherence — model focuses on actual prompt tokens, not padding
- Custom timestep distribution = more stable training for our LoRA (less likely to have runaway loss spikes)

---

## Files Required

### Diffusion Model (pick one)

| File | Source | Size | LoRA compat | Use |
|------|--------|------|------------|-----|
| `Chroma1-HD.safetensors` | `lodestones/Chroma1-HD` | ~18GB bf16 | Any | **Training LoRA** |
| `Chroma1-HD-fp8_scaled_rev2.safetensors` | `silveroxides/Chroma1-HD-fp8-scaled` | ~9GB | **Regular LoRAs ✅** | **ComfyUI inference — use this with OneTrainer LoRAs** |
| `Chroma1-HD-fp8matmulmixed_large_rev2.safetensors` | silveroxides | ~9GB | Unknown | New variant (matmul mixed precision) |
| `Chroma1-HD-fp8mixed-final.safetensors` | silveroxides | ~9GB | Unknown | New variant (mixed final) |
| `Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` | silveroxides | ~9GB | **Pruned flash-heun LoRAs ONLY ❌** | Hybrid precision, no custom loader needed but incompatible with regular LoRAs |
| `Chroma1-HD-fp8_scaled_original_hybrid_small_rev2.safetensors` | silveroxides | — | Regular LoRAs ✅ | Hybrid precision, needs custom loader |
| `Chroma1-HD-fp8_scaled_original_hybrid_large_rev2.safetensors` | silveroxides | — | Pruned flash-heun LoRAs ONLY ❌ | Hybrid precision, needs custom loader |

**⚠️ EMPIRICAL RESULT (tested 2026-03-21) — overrides documentation:**
- `hybrid_large` + OneTrainer LoRA = **LoRA applies well, better identity** ✅
- `fp8_scaled_rev2` + OneTrainer LoRA = weak LoRA effect, wrong identity ❌

Documentation says hybrid_large needs "pruned flash-heun LoRAs" — empirically wrong for our use case. **Use hybrid_large for inference with our LoRAs.**

**For our pipeline:** full `Chroma1-HD.safetensors` for training, `Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` for ComfyUI inference.

**Files on network volume:**
- `/workspace/models/diffusion_models/Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` ✅ — **use this**
- `/workspace/models/unet/Chroma1-HD-fp8_scaled_rev2.safetensors` — worse LoRA adherence in practice

### Text Encoder (T5 XXL — pick one)

| File | Source | Quality | Notes |
|------|--------|---------|-------|
| `t5xxl_fp16.safetensors` | `comfyanonymous/flux_text_encoders` | Best | ~8GB |
| `t5xxl_fp8_e4m3fn_scaled.safetensors` | `comfyanonymous/flux_text_encoders` | Good | ~4GB |
| `flan-t5-xxl-fp16.safetensors` | `silveroxides/flan-t5-xxl-encoder-only` | Better | Chroma-specific T5 variant |
| `flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors` | silveroxides | Good | Chroma-specific fp8 |
| `flan-t5-xxl-Q8_0.gguf` | `silveroxides/flan-t5-xxl-encoder-only-GGUF` | **Recommended for precision** | Needs ComfyUI-GGUF node |

**Note:** `flan-t5-xxl` is a Chroma-specific T5 variant from silveroxides (Chroma contributor).
Preferred over standard t5xxl for Chroma.

### VAE

| File | Source |
|------|--------|
| `ae.safetensors` | `Comfy-Org/Lumina_Image_2.0_Repackaged` |

Same VAE as FLUX — if already downloaded, reuse it.

---

## LoRA Inference — Confirmed Working Config (tested 2026-03-21)

### lora_lily_chroma_v001 on full bf16 model

| Parameter | Value | Notes |
|-----------|-------|-------|
| Model | `Chroma1-HD.safetensors` | Full bf16, 17.8GB on disk |
| UNETLoader weight_dtype | `fp8_e4m3fn` | Quantizes on load: ~17GB → ~8.5GB VRAM. Required on 32GB GPU |
| CLIP | `flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors` | chroma type |
| LoRA | `lora_lily_chroma_v001.safetensors` | Final checkpoint (step 2700) |
| LoRA strength_model | **1.5** | 1.0 = weak identity. 1.5 = best identity without artifact |
| LoRA strength_clip | 1.0 | |
| Resolution | 1152×1152 | |
| Sampler | euler | |
| Steps | 26 | |
| CFG | 3.8 | |
| Scheduler | BetaSamplingScheduler 0.45/0.45 | |

**Checkpoint ranking (lora_lily_chroma_v001):** Final step 2700 > earlier checkpoints.

→ For prompt formulas and working examples see [chroma_prompting.md](chroma_prompting.md).

**VRAM:** fp8_e4m3fn (~8.5GB) + flan-t5 fp8 (~5GB) + VAE (~0.5GB) + activations ≈ safe on both RTX 5090 (32GB) and RTX 4090 (24GB).
`weight_dtype=default` (bf16) → OOM on second generation due to memory fragmentation.

---

## ComfyUI Setup

### RunPod Inference Pod — Our Setup

**Template:** `markgiller/ofm_comfyui_staging:latest` (custom Docker image)

| Parameter | Value |
|-----------|-------|
| GPU | RTX 4090 (24 GB VRAM) |
| Container Disk | 20 GB (ephemeral) |
| Network Volume | `ofm_staging_volume` — 100 GB, permanent, `/workspace` |
| HTTP Port | 8188 |
| TCP Ports | 22, 443 |
| VRAM_MODE | `highvram` — models stay in VRAM (fp8 uses ~13.5 GB of 24 GB) |

**Model files on network volume:**

| File | Path | Size |
|------|------|------|
| `Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` | `/workspace/models/diffusion_models/` | ~9 GB |
| `flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors` | `/workspace/models/text_encoders/` | ~4 GB |
| `ae.safetensors` | `/workspace/models/vae/` | ~0.5 GB |

**Why `defaultloader_hybrid_large_rev2`** (not the original `fp8_scaled_rev2`):
- `fp8_scaled_rev2` moved to `do_not_use/` in the silveroxides repo — deprecated
- `defaultloader` variant works with standard ComfyUI UNETLoader, no custom loader needed

**Download commands (Python API — `huggingface-cli` not in PATH on current image):**
```bash
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id='silveroxides/Chroma1-HD-fp8-scaled',
    filename='Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors',
    local_dir='/workspace/models/diffusion_models')
"
python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id='silveroxides/flan-t5-xxl-encoder-only',
    filename='flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors',
    local_dir='/workspace/models/text_encoders')
"
```
**Fix:** `huggingface_hub[cli]` added to staging Dockerfile — CLI will work after next image rebuild.

**Symlink structure (handled by `start.sh` on every pod start):**
- `/workspace/models` → `/app/comfyui/models`
- `/workspace/custom_nodes` → `/app/comfyui/custom_nodes`
- `/workspace/outputs` → `/app/comfyui/output`
- `/workspace/input` → `/app/comfyui/input`
- `/workspace/user` → `/app/comfyui/user` (workflows persistent in ComfyUI browser)

**Workflows on network volume:** `/workspace/user/default/workflows/`
- `Chroma1_HD_T2I.json` — official baseline workflow
- `Chroma1-HD_Full_with_res2s.json` — advanced workflow (RES4LYF required)

---

### File Placement

```
/workspace/models/          ← network volume (persistent)
├── diffusion_models/
│   └── Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors
├── text_encoders/
│   └── flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors
└── vae/
    └── ae.safetensors      ← reused from FLUX, same file
```

### Official Workflow Parameters (from Chroma1_HD_T2I workflow)

| Parameter | Value | Node |
|-----------|-------|------|
| Model | `Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` | UNETLoader |
| CLIP file | `flan-t5-xxl_float8_e4m3fn_scaled_stochastic.safetensors` | CLIPLoader |
| CLIP type | `chroma` | CLIPLoader |
| VAE | `ae.safetensors` | VAELoader |
| Latent | EmptySD3LatentImage | — |
| Default resolution | 1152×1152 | EmptySD3LatentImage |
| Flow shift | 1.0 | ModelSamplingAuraFlow |
| Sampler | `euler` | KSamplerSelect |
| Scheduler | BetaSamplingScheduler | — |
| Steps | 26 | BetaSamplingScheduler |
| Alpha / Beta | 0.45 / 0.45 | BetaSamplingScheduler |
| CFG | 3.8 | CFGGuider |
| Negative prompt | Required (descriptive, see below) | CLIPTextEncode |
| T5 padding | **min_padding=1** (how model was trained — always use 1) | T5TokenizerOptions |

### Official Negative Prompt (from workflow)

```
This greyscale unfinished sketch has bad proportions, is featureless and disfigured.
It is a blurry ugly mess and with excessive gaussian blur. It is riddled with watermarks
and signatures. Everything is smudged with leaking colors and nonsensical orientation of
objects. Messy and abstract image filled with artifacts disrupt the coherency of the
overall composition. The image has extreme chromatic abberations and inconsistent lighting.
Dull, monochrome colors and countless artistic errors.
```

Descriptive negative (full sentences) works better than tag-style for Chroma.

### diffusers Python API (for scripting)

```bash
pip install transformers diffusers sentencepiece accelerate
```

```python
import torch
from diffusers import ChromaPipeline

pipe = ChromaPipeline.from_pretrained("lodestones/Chroma1-HD", torch_dtype=torch.bfloat16)
pipe.enable_model_cpu_offload()

image = pipe(
    prompt=["..."],
    negative_prompt=["low quality, ugly, unfinished, out of focus, deformed, disfigure, blurry, smudged, restricted palette, flat colors"],
    generator=torch.Generator("cpu").manual_seed(433),
    num_inference_steps=40,
    guidance_scale=3.0,
    num_images_per_prompt=1,
).images[0]
```

**Diffusers parameters:** 40 steps, guidance_scale 3.0 — higher steps than ComfyUI workflow (26).
Both are valid, different schedulers.

### Custom Nodes Required

| Node Pack | Purpose | Install |
|-----------|---------|---------|
| `silveroxides/ComfyUI_SigmoidOffsetScheduler` | Chroma-specific scheduler | GitHub |
| `silveroxides/ComfyUI_Hybrid-Scaled_fp8-Loader` | Hybrid precision model loading | GitHub (optional) |
| `city96/ComfyUI-GGUF` | GGUF text encoder support | GitHub (optional) |
| `RES4LYF` | res_2s sampler (ClownsharKSampler_Beta) | GitHub |

For our baseline workflow (Chroma1_HD_T2I) — no custom nodes needed. All standard ComfyUI.
For advanced workflow (res_2s) — RES4LYF required.

### Optional: Styling LoRAs (from res_2s community workflow)

Используются поверх character LoRA для улучшения качества финального изображения. Не обязательны, но интересны для post-processing слоя:

| LoRA | Strength | Effect |
|------|----------|--------|
| `Flux/Skintastic_Flux_v1.safetensors` | 0.7 | Качество кожи, текстура |
| `Flux/Background-Flux-V01_epoch_15.safetensors` | 0.4 | Улучшение фона |
| `Flux/GrainScape_UltraReal_v2.safetensors` | 0.15 | Плёночное зерно, фотореализм |
| `Flux/42lux-Schwarzwald-Klinik-v15-bf16.safetensors` | 0.3 | Кинематографическое освещение |

Все из FLUX-экосистемы — совместимы с Chroma. Исследовать на этапе построения hero/finish workflow.

---

## Training SOP

### Dataset Captioning for Chroma

→ See [chroma_prompting.md](chroma_prompting.md) — Dataset Captioning section for full Gemini system instruction and caption format.

**Key fact:** Gemini 1.5 Flash is mandatory — Chroma's training data was captioned with it. Same tool = native language match = less identity drift.

---

## Quantization

Chroma is **sensitive to quantization**. Two recommended methods:

| Method | Quality | Size | Speed | LoRA impact |
|--------|---------|------|-------|-------------|
| **GGUF Q8** | Nearly indistinguishable from bf16 | Larger | Slower | Inference speed affected by LoRAs |
| **fp8 scaled learned** (Clybius) | Slightly worse than Q8 | Smaller | **Fastest** | Less affected by LoRAs |

**Our choice:** `Chroma1-HD-fp8_scaled_defaultloader_hybrid_large_rev2.safetensors` = Clybius fp8 scaled. Correct tradeoff for production inference.

---

## Model Variants

| Model | Version | Notes |
|-------|---------|-------|
| Chroma1-Base | v.48 (chroma-unlocked-v48) | 512x raw pretrained — use for long full fine-tune |
| Chroma1-HD | finetune of v48, mixed res | **Our base model** — primary for inference |
| chroma-unlocked-v49/v50 | — | **BORKED** — overfit on 1024x, not recommended |
| Chroma1-Flash | finetune of v48 at 512x | Fast: 8 steps (heun/dpmpp_sde) or 16 steps — NOT for LoRA training |
| DC-2k | merge of v48-detail-calibrated + 2k-test | Best for >1024x generation |
| Chroma1-Radiance | experimental | VAE-less PixelNerd architecture, alpha — ignore for now |

**Note on v49/v50:** Our knowledge base previously said "Chroma1-HD = v.50" — this was incorrect. Chroma1-HD is a separate finetune of v48, not the same as v49/v50 which are borked intermediate checkpoints.

Chroma1-Flash: 8 steps with heun/dpmpp_sde_ancestral, or 16 steps with multistep samplers. NOT for LoRA training. Potentially useful for explore batches.

---

## Version History

| Date | Event |
|------|-------|
| 2026-03-20 | Chroma 1 HD selected as base model. Knowledge base created. |
| 2026-03-21 | Inference pod configured. Models downloaded to network volume. RunPod setup documented. |
| 2026-03-21 | Step 2 complete: Chroma1_HD_T2I workflow loaded in ComfyUI, settings verified. Step 3 complete: base model confirmed — photorealistic SFW and NSFW anatomy working, no "flux static". |
| 2026-03-21 | Major KB update from levzzz Chroma guide: ai-toolkit NOT recommended → switching to OneTrainer/diffusion-pipe. Samplers, schedulers, quantization, model variants, prompting all updated. |
| 2026-03-21 | LoRA compatibility clarified: hybrid_large variants require pruned flash-heun LoRAs ONLY — NOT compatible with OneTrainer LoRAs. Use fp8_scaled_rev2 for regular LoRA inference. New model variants added: fp8matmulmixed_large_rev2, fp8mixed-final. |
| 2026-03-21 | lora_lily_chroma_v001 tested on full bf16 Chroma1-HD.safetensors (RTX 5090). Final checkpoint (step 2700) works best. Working config: UNETLoader weight_dtype=fp8_e4m3fn (halves VRAM: 17GB→8.5GB), LoRA strength=1.5, resolution 1152×1152. Realistic anatomy confirmed. Identity ~60-70% Lily — limited by single-source dataset. Full bf16 + fp8_e4m3fn quantization = reliable 32GB VRAM fit. |
| 2026-03-22 | RTX 4090 (24GB) confirmed working: Chroma1-HD.safetensors + UNETLoader weight_dtype=fp8_e4m3fn. No quality loss vs bf16 for production content. VRAM fits comfortably. |
| 2026-03-22 | FLUX inpainting as identity fix — ABANDONED. FLUX/Chroma style mismatch + v001 identity weakness = result not publishable. Real solution: v002 dataset generated natively on Chroma → Gemini captions → retrain. |
