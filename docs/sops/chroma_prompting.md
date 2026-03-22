# Chroma 1 HD — Prompting Guide

All prompting, sampling, and scheduling knowledge for Chroma 1 HD inference.

---

## Prompt Structure

**Optimal length:** 75–150 T5 tokens. Max: 512 tokens (check at [sd-tokenizer](https://sd-tokenizer.rocker.boo/), set to Pixart). 1–2 paragraphs. 2 sentences character+action, 1 sentence background/atmosphere.

**Formula:**
```
[style] [subject] [action] [more subject description] [atmosphere/mood] [more on style]
```

**Natural language only** — no tag lists, no comma-separated keywords. Full sentences. This is how Chroma was trained.

---

## Photorealism Tricks

**Repetition:** Mention "photo" or "photograph" at beginning AND end. Special phrase: `The photograph is a .` repeated x10 at the end significantly improves photorealism.

**Lighting is critical** — more important than "this is a photo" modifiers. Always specify:
- `studio lighting`
- `natural lighting`
- `soft ambient lighting`
- `golden hour light`
- `warm bedside lamp`

**Filename anchor** — prepend `IMG_XXXX.HEIC` for amateur/phone photo realism. Strongest photorealism trigger for camera-trained models.

**Amateur/self-filmed aesthetic:**
- `A casual snapshot of ...`
- `phone propped on [surface]`
- `screenshot quality — like a frame captured from a vertical video`
- `slightly overexposed highlights from [light source]`

**Tag formatting:**
- Tags separated by **commas** → cartoon/anime style drift
- Tags separated by **periods** → realistic style preserved
- For fully realistic: natural language only, no tags

**Avoid:**
- Fluff words and motion words — overly generic descriptors hurt generation
- SD-era keywords: `ultrarealistic`, `masterpiece`, `best quality`, `extremely detailed` — noise for Chroma
- Anything implying movement in a static scene

---

## Negative Prompts

Unlike FLUX (which ignores negatives), **Chroma was trained with negatives** — always provide one.

**Official negative prompt (from Chroma1_HD_T2I workflow):**
```
This greyscale unfinished sketch has bad proportions, is featureless and disfigured.
It is a blurry ugly mess and with excessive gaussian blur. It is riddled with watermarks
and signatures. Everything is smudged with leaking colors and nonsensical orientation of
objects. Messy and abstract image filled with artifacts disrupt the coherency of the
overall composition. The image has extreme chromatic abberations and inconsistent lighting.
Dull, monochrome colors and countless artistic errors.
```

**Alternative — anatomy-focused negative (community-sourced):**
```
This is a simple anime like artwork with discontinued bodies and doubles. This is a low
resolution digital painting with boring composition and weak lighting. The background is
a simple flat color and extremely blurry. Ultimately this is a bad photo with characters
having perfect doll skin. The characters have distorted proportions and broken anatomy.
```

**Rule:** Short negative prompt (<70 tokens) not recommended. Use full descriptive sentences.

---

## Special Tags

| Tag | Effect |
|-----|--------|
| `aesthetic 0-10` | General aesthetic score |
| `aesthetic 11` | Aesthetically curated AI images (may cause prompt bleeding) |
| `A casual snapshot of ...` | Amateur/phone photo style |
| `...cosplayer dressed as XYZ character...` | Realistic fictional characters |

---

## LoRA Prompting

**Trigger word:** `lily` — T5 is not great at out-of-context trigger words. Always describe everything visible in the image, not just the character.

**Working NSFW formula (confirmed with lora_lily_chroma_v001):**
```
IMG_XXXX.HEIC

An image of lily [action/pose in one sentence]. [Body visibility, expression, hair state in one sentence]. [Scene: location, lighting, background in 1-2 sentences]. [Camera/shot description].
```

**Example (confirmed working):**
```
IMG_4821.HEIC

An image of lily lying on her back on a white bedsheet, completely naked, legs spread
wide apart, squirting intensely. Her back is arched, face tilted back with mouth open,
eyes half-closed. Medium brown wavy hair spread across the pillow, natural freckles
across her nose. Small silver necklace. Warm bedside lamp in the background, slightly
blown out. Shot from slightly above at an angle, full body visible. Raw, candid, unedited.
```

**Self-filmed example:**
```
IMG_7743.HEIC

An image of lily completely naked, filming herself with her phone propped up on a pillow
at the foot of the bed — the shot is slightly wide angle, the way a phone camera captures
a selfie video. [action]. Screenshot quality — like a frame captured from a vertical video.
Slightly overexposed highlights from the lamp.
```

---

## Samplers

| Sampler | Notes |
|---------|-------|
| `euler` | Most basic, fastest per step — works but not optimal |
| `res_multistep` | **Nearly always better than euler at similar speed — use as default** |
| `dpmpp_2m` | Decent alternative to res_multistep |
| `gradient_estimation` | Trades aesthetics for better coherency |
| `heun` / `deis` | Recommended for Flash models only |
| `res_2s` (RES4LYF) | Potentially better than heun — "secret weapon" |
| `res_2m` (RES4LYF) | Potentially better than res_multistep |

Ancestral samplers may sometimes improve results.

---

## Schedulers

**Default (official):** 26 steps, shift=1, beta scheduler **0.6 / 0.6**
**Our workflow:** sigmoid_offset scheduler, square_k=1.0, base_c=0.5 — confirmed best results.

> At shift=1 → beta settings **0.4 / 0.4** can improve over default 0.6/0.6

| Scheduler | Notes |
|-----------|-------|
| `beta` | Recommended. At shift=1 use 0.4/0.4 |
| `sigmoid_offset` | **Our default.** square_k=1.0, base_c=0.5. Made for Chroma with shift=1 |
| `bong_tangent` (RES4LYF) | Great results but ignores shifting, not customisable |

**Timestep shifting:** Chroma trained WITHOUT timestep shifting. Use shift=1 or flux_shift. shift<1 not recommended.

**Sigmoid Offset Scheduler** — custom scheduler by silveroxides (Chroma contributor):
- GitHub: https://github.com/silveroxides/ComfyUI_SigmoidOffsetScheduler
- Install as ComfyUI custom node
- **Our settings:** square_k=1.0, base_c=0.5 (tested, best photorealism)

---

## CFG

- Official default: **3.8** (CFGGuider node)
- Advanced workflow (Skimmed CFG): **3.5**
- Lower CFG = more photorealistic. Higher CFG = more prompt adherence but illustration drift.

---

## Dataset Captioning (for LoRA training)

**Tool:** Gemini 1.5 Flash — mandatory. Chroma's training dataset was captioned with Gemini 1.5 Flash specifically. Same model = native language match = less identity drift.

**Caption format:**
```
An image of lily [what she is doing in one sentence]. [Notable clothing, expression, or pose in one sentence]. [Scene: location, lighting, background in 1-2 sentences].
```

**Key rules:**
- Natural language, full sentences — no tags, no commas as separators
- 60–130 words total
- Always describe lighting explicitly
- Describe everything visible
- Never use "illustrated", "rendered", "drawn" — she is a real person in a photograph
- Trigger word: **`lily`**

**Gemini System Instruction:**
```
You are a training data captioner for an image generation model.
Caption each image in natural language following this exact format:

An image of lily [what she is doing in one sentence]. [Any notable clothing, expression,
or pose details in one sentence]. [Scene description: location, lighting, background in
1-2 sentences].

Rules:
- Natural language only, full sentences, no tags or commas as separators
- 60-130 words total
- Always describe lighting explicitly
- Describe everything visible
- Never use words like "illustrated", "rendered", "drawn" — she is a real person in a photograph
```

**Captioning principles:**
- Style deconstruction: describe Medium+Texture, Technique, Lighting, Level of Finish
- For photographic style: use `analog film capture`, `photograph`, `shallow depth of field`
- Subject count lock: if one person → describe only one person
- Output only the caption string — no titles, no introduction
- Word count: casual photo → ~60 words; professional portrait → ~130 words
