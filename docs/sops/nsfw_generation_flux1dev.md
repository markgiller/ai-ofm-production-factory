# NSFW Generation — FLUX.1 Dev + LoRA Stack

Standard operating procedure for adult lane content generation on **FLUX.1 Dev 12B + character LoRA**,
based on testing conducted 2026-03-16 during lily_v001 checkpoint evaluation.

---

## Key Finding: FLUX.1 Dev Has Soft Alignment, Not Hard Filter

FLUX.1 Dev self-hosted has **no content filter** — but it was trained with alignment that makes it
resist explicit poses. It will generate:

| Content | Result |
|---------|--------|
| Topless, bare chest | ✅ Works without NSFW LoRA |
| Full nudity, bare back/ass | ✅ Works without NSFW LoRA |
| Explicit poses (spread legs, doggy) | ❌ Fails without NSFW LoRA — model "softens" composition |
| Detailed genital anatomy | ❌ Requires uncensored base model |

The model doesn't throw an error — it just quietly generates a tamer version of the prompt.

---

## Two-Lane Architecture

### Lane 1: SFW / Implied Nude (Instagram, Threads)
- Character LoRA only, strength 1.0
- No NSFW LoRA needed
- Identity lock: FaceSim 0.77 (excellent)
- Results: portrait, fashion, boudoir, artistic nude

### Lane 2: Explicit Adult (Fanvue)
- Character LoRA (strength 1.0) + NSFW LoRA (strength 0.3-0.5) stacked
- Identity: slightly degraded (~0.70-0.74 estimated) due to LoRA interference
- Results: explicit poses work, anatomy realistic but genitalia "smoothed"

---

## NSFW LoRA Stack — ComfyUI Implementation

Workflow uses two chained `LoraLoaderModelOnly` nodes:

```
UNETLoader(1) → LoraLoaderModelOnly[lily, 1.0](14) → LoraLoaderModelOnly[nsfw, 0.45](15) → BasicGuider(6)
                                                                                            → BasicScheduler(8)
```

Node 6 (BasicGuider) and Node 8 (BasicScheduler) must reference Node 15 output, not Node 14.

### Tested LoRA: NSFW FLUX LoRA V1 (CivitAI - Ai_Art_Vision)
- **Source:** civitai.com/models/655753
- **File:** `nsfw_flux_lora_v1.safetensors` (656MB)
- **Base:** FLUX.1 Dev
- **Training:** 18,000 steps, 600 images, A6000
- **Trigger word:** `AiArtV` (include at start of prompt)
- **Reviews:** 1,805 overwhelmingly positive — confirmed stacking with character LoRAs on fp8
- **Install path:** `/app/comfyui/models/loras/nsfw_flux_lora_v1.safetensors`

### Strength Tuning Results

| lily strength | NSFW strength | Identity | Pose explicitness | Notes |
|---------------|---------------|----------|-------------------|-------|
| 1.0 | 0.5 | ~70% | High | Pose works great, face drifts |
| 1.0 | 0.3 | ~80% | Medium | Face closer, poses softer |
| 1.0 | 0.45 | ~75% | High | Best compromise |

**Rule:** suммарный strength обеих LoRA не превышать ~1.5 во избежание артефактов.

---

## Prompt Structure for Adult Lane

```
AiArtV [explicit action/pose], lily, young woman with hazel eyes and freckles on nose and cheeks,
[body description], [scene/setting], [lighting], [camera/lens], photorealistic
```

- `AiArtV` trigger word **обязательно** в начале
- Упоминать freckles явно — иначе NSFW LoRA "перебивает" характерные черты
- `hazel eyes` держит цвет глаз
- Детали освещения и камеры (35mm f/1.4) улучшают фотореализм

---

## Known Limitations of Current Stack

### 1. Genital anatomy unrealistic
FLUX.1 Dev + NSFW LoRA генерирует "сглаженную" анатомию — не детализированную.
Причина: модель не видела explicit контент при тренировке.

**Решение (v002):** заменить base model на uncensored checkpoint:
- **Fluxed Up v7.1** (CivitAI 847101) — fp8 вариант, drop-in замена, 500+ отзывов
- **Vision Realistic** (CivitAI — Ai_Art_Vision) — тот же автор что NSFW LoRA

### 2. Identity drift at explicit poses
При higher NSFW strength лицо отклоняется от lily референса.
Причина: NSFW LoRA натренирована на 600 изображениях с конкретным лицом — интерференция.

**Решение (v002):** тренировать character LoRA на uncensored base model. Тогда одна LoRA
держит identity И не конфликтует с explicit контентом.

### 3. Face-heavy dataset = weak body shots
Датасет lily_v001 (36 фото) в основном портреты/face. LoRA плохо держит identity
при full body / explicit позах где лицо маленькое.

**Решение (v002):** добавить в датасет full body shots разных поз (не upscale, а разнообразие).

---

## Workflow File

Eval workflow с поддержкой LoRA стека:
`workflows/eval/IMG_eval_lora_v001.json`

Для production нужен отдельный `IMG_hero_nsfw_v001.json` с двумя LoRA нодами.

---

## Checkpoint Evaluation Results (lily_v001, 2026-03-16)

ArcFace scoring: 9 checkpoints × 3 prompts × 3 seeds = 80 images

| Rank | Step | Mean FaceSim | Max | Notes |
|------|------|-------------|-----|-------|
| #1 | **1750** | **0.7727** | 0.8037 | **WINNER — deployed to ComfyUI** |
| #2 | 2000 | 0.7712 | 0.8156 | почти идентичен |
| #3 | 2250 | 0.7668 | 0.8043 | лёгкий спад |
| #4 | 2500 | 0.7653 | 0.8088 | финальный — чуть хуже |
| #9 | 0 | 0.5160 | 0.5883 | baseline без LoRA |

Sweet spot: **step 1750** — после него лёгкий overfitting, identity начинает падать.
Baseline jump: 0.516 → 0.773 = +49% — LoRA работает.

### Deploy command
```bash
cp /workspace/lora_training/lily_v001/output/lora_lily_v001/lora_lily_v001_000001750.safetensors \
   /app/comfyui/models/loras/lora_lily_v001.safetensors
```

---

## Next Steps (v002 Roadmap)

1. **Uncensored base model** — скачать Fluxed Up v7.1 fp8, протестировать с lily LoRA
2. **v002 dataset** — добавить full body poses (не upscale существующих, а разнообразие ракурсов)
3. **v002 training** — тренировать на uncensored base, rank 16 как и v001
4. **IMG_hero_nsfw workflow** — production workflow с двумя LoRA + upscale + color grade
