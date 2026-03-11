# System Architecture

## 7-Layer Architecture

```
Layer 1: Creative Inputs
    briefs, character bibles, style bibles, reference packs,
    shot library, wardrobe/location/background packs, platform specs

Layer 2: Workflow Library
    5 versioned ComfyUI JSON graphs:
    IMG_explore, IMG_hero, IMG_repair, VID_i2v, VID_finish

Layer 3: Inference
    Runpod RTX 4090 24GB pod, headless ComfyUI in Docker
    Separate staging and production pods

Layer 4: Orchestrator
    FastAPI service: job intake, parameter injection,
    POST /prompt, poll /queue + /history, save outputs

Layer 5: Storage
    Backblaze B2 (S3-compatible)
    refs, raw outputs, final outputs, workflow snapshots,
    review assets, sequences, thumbs, audio, voice, captions

Layer 6: Metadata
    Supabase Postgres: jobs, assets, characters, workflows, review_scores
    JSON manifests per job (seed, model version, LoRA, refs, lineage)

Layer 7: Review & Analytics
    Human selection, accept/reject, routing to repair,
    KPI tracking, scoring (later: automated gates)
```

## Data Flow

```
Brief
  -> IMG_explore (batch 10-50 variations)
  -> Human select (contact sheet + shortlist)
  -> IMG_hero (high-quality still with LoRA + refs)
  -> IMG_repair (if needed: face/hands/clothing/background)
  -> VID_i2v (hero still -> 720p/24fps source clip)
  -> VID_finish (interpolation + upscale + encode -> 1080p master)
  -> Review gate (accept / reject / route to repair)
  -> Publish (platform variants + captions)
```

## Storage Architecture

Two buckets per environment (lane separation):

| Environment | SFW | Adult |
|-------------|-----|-------|
| Staging | `ofm-staging` | `ofm-staging-adult` |
| Production | `ofm-prod` | `ofm-prod-adult` |

Bucket structure (identical in both lanes):
```
refs/characters/<char>/
refs/styles/<style>/
refs/locations/
refs/backgrounds/
outputs/raw/YYYY/MM/DD/
outputs/final/YYYY/MM/DD/
workflow_snapshots/YYYY/MM/DD/
review_assets/YYYY/MM/DD/
sequences/seq_YYYY_MM_DD_<char>_####/
thumbs/
audio/
voice/
captions/
```

## Database Schema

```
jobs            lifecycle of each ComfyUI run
assets          what was produced (images, video, manifests)
characters      character state as production entities
workflows       version control of ComfyUI graphs
review_scores   gate scores for quality control
```

Schema: `ofm_staging` (staging) / `ofm_production` (production).
Single Supabase database (`postgres`), isolation via schemas.

## Staging vs Production

| | Staging | Production |
|---|---------|-----------|
| Purpose | R&D, workflow tuning, new nodes | Live job execution |
| Dependencies | Tier 1 (pinned) + Tier 2 (sweep) | Tier 1 only (hard fail if missing) |
| Custom nodes | Open for testing | Allowlist + pinned versions |
| Restart | unless-stopped | always |

## Compute

Cloud rental (Runpod/Vast), not owned hardware.
RTX 4090 24GB as starting production GPU.
VRAM modes: highvram (default), normalvram, lowvram, cpu.
