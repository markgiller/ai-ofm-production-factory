# System Architecture

## Overview

Production system where any asset passes through a formalized path:
brief -> explore -> select -> hero -> repair -> video -> finish -> review -> publish.

One factory, two output lanes (SFW + lawful adult) on the same technical core
with different policy packs, review gates, and distribution rules.

---

## 7-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Creative Inputs                               │
│    briefs, character bibles, style bibles, reference    │
│    packs, shot library, wardrobe/location/background    │
│    packs, platform specs                                │
│    Without this the system has no managed creative      │
│    memory.                                              │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Workflow Library                              │
│    5 versioned ComfyUI JSON graphs:                     │
│    IMG_explore, IMG_hero, IMG_repair,                   │
│    VID_i2v, VID_finish                                  │
│    Repeatability and fast rollback.                     │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Inference                                     │
│    Runpod RTX 4090 24GB, headless ComfyUI in Docker     │
│    Executes jobs, not a playground.                     │
│    Staging pod (R&D) and production pod (live) separate.│
├─────────────────────────────────────────────────────────┤
│  Layer 4: Orchestrator                                  │
│    FastAPI service: accepts job, injects parameters     │
│    into versioned workflow JSON, sends to /prompt,      │
│    reads /queue and /history, saves outputs.            │
│    Removes manual chaos, creates traceability.          │
├─────────────────────────────────────────────────────────┤
│  Layer 5: Storage                                       │
│    Backblaze B2 (S3-compatible)                         │
│    refs, raw outputs, final outputs, workflow snapshots,│
│    review assets, sequences, thumbs, audio, voice,      │
│    captions. Asset lineage and reproducibility.         │
├─────────────────────────────────────────────────────────┤
│  Layer 6: Metadata                                      │
│    Supabase Postgres + JSON manifests per job           │
│    jobs, assets, characters, workflows, review_scores   │
│    Machine memory for analysis and scaling.             │
├─────────────────────────────────────────────────────────┤
│  Layer 7: Review & Analytics                            │
│    Human selection, accept/reject, routing to repair,   │
│    KPI tracking. Later: automated scoring gates.        │
│    This is where winners separate from "okay."          │
└─────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Image Pipeline

```
Brief (character + lane + shot type + style)
  │
  ▼
IMG_explore ─── batch 10-50 variations ──► contact sheet + shortlist + seeds
  │
  ▼
Human select ── pick best candidates
  │
  ▼
IMG_hero ────── full-quality still ──────► hero master + crop variants + thumb
  │
  ├──► QC pass? ──► yes ──► continue to video
  │                  │
  │                  ▼ no
  │            IMG_repair ── fix face/hands/clothing/background
  │                  │
  │                  └──► loop back to QC
  ▼
VID_i2v ────── hero still → source clip ──► 720p/24fps clip
  │
  ▼
VID_finish ─── interpolation + upscale + encode ──► 1080p master
  │                                                 + platform variants
  │                                                 + preview thumb
  ▼
Review gate ── accept / reject / route to repair
  │
  ▼
Publish ────── platform variants + captions
```

### Long-form Video (2-3 min)

Not one long generation — assembled from 12-25 short clips (3-8 sec each).

```
SEQ_plan ─── shot list from brief
  ▼
SEQ_source_batch ─── generate clips per shot list
  ▼
SEQ_select ─── pick best take per slot
  ▼
SEQ_gapcheck ─── identify missing transitions
  ▼
SEQ_assemble ─── timeline assembly (ffmpeg concat)
  ▼
SEQ_audio ─── music bed + room tone + texture layers
  ▼
SEQ_package ─── final render + platform variants
```

Clip taxonomy: anchor, bridge, detail, reaction, entry, exit, cover, alt_take.
See Video_Splicing.md for full sequence manifest schema.

---

## Storage Architecture

### Lane Separation (mandatory)

SFW and adult assets **never** share a bucket.

| Environment | SFW Bucket | Adult Bucket |
|-------------|------------|--------------|
| Staging | `ofm-staging` | `ofm-staging-adult` |
| Production | `ofm-prod` | `ofm-prod-adult` |

The `lane` field in every manifest must match the bucket where the asset is stored.
Cross-lane storage paths are a critical error.

### Bucket Structure (identical in both SFW and adult buckets)

```
refs/
  characters/<character_id>/          per-character face/body/pose refs
    chara_face_v001.png               version in filename, flat structure
    chara_body_v001.png
  styles/<style_name>/                house aesthetic style refs
  locations/                          location references
  backgrounds/                        background references

outputs/
  raw/YYYY/MM/DD/                     ComfyUI outputs before review
    chara_sfw_hero_mirror_9x16_v001_seed483829.png    (image, naming §7)
    job_2026_03_11_chara_sfw_hero_00421.json           (manifest, naming §4)
  final/YYYY/MM/DD/                   accepted winners post-review gate

workflow_snapshots/YYYY/MM/DD/        exact graph JSON at job execution time
  job_..._workflow.json               lookup by job_id, not workflow name

review_assets/YYYY/MM/DD/            contact sheets and gate review assets
  review_job_..._contactsheet.png     naming §12
  review_job_..._thumb.png

sequences/                            long-form assembled videos
  seq_YYYY_MM_DD_<char>_####/         per-sequence folder
    seq_..._master.mp4                naming §9
    seq_..._preview.mp4
    seq_..._manifest.json

thumbs/                               preview thumbnails per asset
audio/                                audio beds, room tone, texture layers
voice/                                TTS outputs (Phase 5)
captions/                             platform caption files (Phase 4)
```

### Storage Provider

Backblaze B2, S3-compatible API. Requires AWS Signature V4.
Endpoint format: `https://s3.<region>.backblazeb2.com`

---

## Database Schema

Single Supabase database (`postgres`), isolation via schemas:
- Staging: schema `ofm_staging`
- Production: schema `ofm_production`

### Tables

**jobs** — lifecycle of each ComfyUI run
```
id                 TEXT PRIMARY KEY     job_2026_03_11_chara_sfw_hero_00421
lane               TEXT NOT NULL        'sfw' or 'adult'
character_id       TEXT                 chara, charb, charc
brief_id           TEXT
workflow_id        TEXT
status             TEXT NOT NULL        queued → running → done → accepted/rejected/failed
created_at         TIMESTAMPTZ
finished_at        TIMESTAMPTZ
operator           TEXT                 who launched the job
cost_estimate      NUMERIC(10,4)       GPU cost tracking
notes              TEXT
```

**assets** — what was produced
```
asset_id           TEXT PRIMARY KEY
job_id             TEXT REFERENCES jobs(id)
type               TEXT NOT NULL        'image', 'video', 'manifest', 'contact_sheet'
path               TEXT NOT NULL        s3:// path to asset
width              INT
height             INT
fps                NUMERIC(5,2)
score_human        NUMERIC(3,1)
accepted           BOOLEAN
```

**characters** — character state as production entities
```
character_id       TEXT PRIMARY KEY     chara, charb, charc
name               TEXT NOT NULL
lane               TEXT NOT NULL
lora_version       TEXT                 v001, v002, etc.
ref_pack_version   TEXT
style_bible_version TEXT
active             BOOLEAN DEFAULT true
```

**workflows** — version control of ComfyUI graphs
```
workflow_id        TEXT PRIMARY KEY
name               TEXT NOT NULL
version            TEXT NOT NULL        v001 format (CHECK constraint)
file_hash          TEXT
changelog          TEXT
active             BOOLEAN DEFAULT true
```

**review_scores** — gate scores for quality control
```
job_id             TEXT PRIMARY KEY REFERENCES jobs(id)
hook_score         SMALLINT             0 or 1
identity_score     SMALLINT             0 or 1
composition_score  SMALLINT             0 or 1
lighting_score     SMALLINT             0 or 1
detail_score       SMALLINT             0 or 1
motion_score       SMALLINT             0 or 1
publish_readiness  NUMERIC(3,1)
notes              TEXT
```

### Key Indexes

- `idx_jobs_status` — filter by job status
- `idx_jobs_lane` — filter by SFW/adult
- `idx_jobs_character` — filter by character
- `idx_jobs_created` — sort by date
- `idx_assets_job` — find all assets for a job
- `idx_assets_type` — filter by asset type
- `idx_assets_accepted` — find accepted assets

---

## Job Manifest Schema (JSON)

Every job produces a manifest stored in S3 and referenced in Postgres:

```json
{
  "job_id": "job_2026_03_11_chara_sfw_hero_00421",
  "date": "2026-03-11",
  "operator": "mark",
  "lane": "sfw",
  "character_id": "chara",
  "workflow_id": "IMG_hero_v001",
  "workflow_version": "v001",
  "workflow_hash": "sha256:abc123...",
  "model_version": "flux2_klein_4b",
  "model_hash": "sha256:def456...",
  "lora_versions": {
    "character": "lora_chara_v003",
    "style": "lora_house_editorial_v001"
  },
  "references_used": [
    "refs/characters/chara/chara_face_v004.png",
    "refs/characters/chara/chara_body_v003.png"
  ],
  "seed": 483829,
  "parameters": {
    "steps": 30,
    "cfg": 3.5,
    "width": 1024,
    "height": 1820
  },
  "outputs": [
    "outputs/raw/2026/03/11/chara_sfw_hero_mirror_9x16_v001_seed483829.png"
  ],
  "accepted": true,
  "final_asset_paths": [
    "outputs/final/2026/03/11/chara_sfw_hero_mirror_9x16_v001_seed483829.png"
  ],
  "notes": ""
}
```

Any winner is reproducible by reading its manifest + pulling files from S3.

---

## Staging vs Production

| | Staging | Production |
|---|---------|-----------|
| **Purpose** | R&D, workflow tuning, test new nodes | Live job execution, review-ready outputs |
| **Dependencies** | Tier 1 (pinned) + Tier 2 (sweep custom nodes) | Tier 1 only (hard fail if requirements_pinned.txt missing) |
| **Custom nodes** | Open for testing | Allowlist + pinned git commit hashes |
| **Docker restart** | `unless-stopped` | `always` |
| **What's forbidden** | Opening externally, mixing with live prod | Manual installs, unconfirmed nodes, config drift |

### Two-Tier Dependency System

**Tier 1 (pinned):** `requirements_pinned.txt` on the network volume.
Explicit `package==version` pins. Source of truth for stable nodes.
Installed first so it takes precedence.

**Tier 2 (sweep, staging only):** Each `custom_nodes/<node>/requirements.txt`
gets installed for nodes not yet pinned. pip skips packages already satisfied by tier 1.

**Upgrade path:** Once a node's deps are stable → pin in requirements_pinned.txt.
Production: tier 1 only, no sweep.

---

## Compute

Cloud GPU rental (Runpod/Vast), not owned hardware.
RTX 4090 24GB as starting production GPU.

VRAM modes (set via `VRAM_MODE` env var):
- `highvram` — keep models in VRAM (24GB default, RTX 4090)
- `normalvram` — balanced offloading (no flag)
- `lowvram` — aggressive offloading (<12GB)
- `cpu` — CPU-only, debugging without GPU

### Network Volume

All models, custom nodes, and outputs live on a persistent Runpod network volume
mounted at `/workspace`. The Docker container is ephemeral — symlinks wire
the volume into ComfyUI's expected directories:

```
/workspace/models/       → /app/comfyui/models
/workspace/custom_nodes/ → /app/comfyui/custom_nodes
/workspace/outputs/      → /app/comfyui/output
/workspace/input/        → /app/comfyui/input
```

This ensures data survives pod restarts and container rebuilds.

---

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `ENV` | Environment identifier | `staging` or `production` |
| `COMFYUI_PORT` | ComfyUI listen port | `8188` |
| `VRAM_MODE` | GPU memory strategy | `highvram` |
| `NETWORK_VOLUME_PATH` | Persistent volume mount | `/workspace` |
| `COMFYUI_VERSION` | Pinned ComfyUI git tag | `v0.16.4` |
| `HF_HOME` | HuggingFace cache on volume | `/workspace/.cache/huggingface` |
| `PIP_CACHE_DIR` | pip cache on volume | `/workspace/.pip_cache` |
| `S3_ENDPOINT_URL` | B2 S3-compatible endpoint | `https://s3.eu-central-003.backblazeb2.com` |
| `S3_BUCKET_NAME` | SFW bucket | `ofm-staging` |
| `S3_BUCKET_NAME_ADULT` | Adult bucket | `ofm-staging-adult` |
| `S3_ACCESS_KEY` | B2 application key ID | (secret) |
| `S3_SECRET_KEY` | B2 application key | (secret) |
| `S3_REGION` | B2 region | `eu-central-003` |
| `POSTGRES_HOST` | Supabase host | `db.xxx.supabase.co` |
| `POSTGRES_PORT` | Postgres port | `5432` |
| `POSTGRES_DB` | Database name (always `postgres` on Supabase) | `postgres` |
| `POSTGRES_SCHEMA` | Schema for isolation | `ofm_staging` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | (secret) |
| `COMFYUI_URL` | Running pod URL (set per session) | `https://<pod-id>-8188.proxy.runpod.net` |
