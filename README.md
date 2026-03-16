# AI OFM Production Factory

Production pipeline for AI-generated content. Not a "drawing tool" — a disciplined factory
where every asset follows a formalized path from brief to publish.

**Core principle:** character lock + house aesthetic + production discipline + ruthless curation.
Quality and consistency over volume. Revenue comes through curation, not mass AI spam.

## What This System Does

One technical core, two output lanes:
- **SFW lane** — fashion, editorial, lifestyle content
- **Lawful adult lane** — separate character packs, storage buckets, compliance logs, age-gating

Every asset passes through:
```
brief → explore → select → hero → repair → video → finish → review → publish
```

The system solves four problems simultaneously:
1. Stable character identity from post to post
2. Fast, high-quality photorealistic stills and controllable short clips
3. Full lineage preservation (inputs, versions, seeds, workflows) without manual chaos
4. Readiness for gradual automation without rewriting the core

## Stack

| Layer | Tool | Role |
|-------|------|------|
| Compute | Runpod RTX 4090 24GB (cloud rental) | Starting production GPU |
| Runtime | Dockerized ComfyUI (headless API) | Inference engine, staging + prod separate |
| Image backbone | FLUX.1 Dev 12B (fp8) | T2I/I2I via LoRA + refs |
| Video backbone | Wan 2.2 TI2V-5B | Image-to-video, 720p/24fps source clips |
| Finishing | Upscale + interpolation + encode | Every clip goes through finish stage |
| Storage | Backblaze B2 (S3-compatible) | Raw/final separated, full lineage |
| Metadata | Supabase Postgres + JSON manifests | Machine memory for reproducibility |
| Orchestration | FastAPI + internal panel (Phase 3) | Job runner, not "magic agent" |

## 5 Core Workflows

| Workflow | Purpose | Key Output |
|----------|---------|------------|
| **IMG_explore** | Fast batch of 10-50 variations | Contact sheet, shortlist, seeds for best frames |
| **IMG_hero** | Production-quality still from selected candidate | Hero master, crop variants, thumbnail |
| **IMG_repair** | Fix defects without full regeneration | Repaired asset (face/hands/clothing/background) |
| **VID_i2v** | Controllable short clip from hero still | 720p/24fps source clip |
| **VID_finish** | Publish-ready packaging | 1080p master + platform variants + preview thumb |

Long-form video (2-3 min): assembled from 12-25 short clips, not one generation.
See [Video_Splicing.md](Video_Splicing.md) for the sequence assembly layer.

## Repository Structure

```
/infra                              Infrastructure
  /docker/staging/                  Dockerfile + start.sh (two-tier deps)
  /docker/production/               Dockerfile + start.sh (pinned deps only, hard fail)
  /compose/                         docker-compose.staging.yml, docker-compose.prod.yml
  /env/                             staging.env, production.env (gitignored, never committed)
  /deploy/                          Deploy configs (staging + production)

/services                           Application services (Phase 3)
  /orchestrator/                    FastAPI job runner
  /internal_panel/                  Operator web UI
  /workers/                         Background workers

/models                             Model registry (not weights — those live on volume/S3)
  /image/base/                      Image model references
  /video/base/                      Video model references
  /loras/characters/                Character LoRA registry
  /loras/styles/                    Style LoRA registry

/refs                               Reference packs
  /characters/                      Per-character face/body/pose refs
  /styles/                          House aesthetic style refs
  /locations/                       Location references
  /backgrounds/                     Background references

/creative                           Creative inputs
  /briefs/                          Production briefs
  /character_bibles/                Character identity docs
  /style_bibles/                    House aesthetic rules
  /shot_library/                    8 shot types with prompt blocks
  /platform_specs/                  Platform-specific requirements

/workflows                          Versioned ComfyUI JSON graphs (Phase 2)
  /explore/                         IMG_explore_v###.json
  /hero/                            IMG_hero_v###.json
  /repair/                          IMG_repair_v###.json
  /video/                           VID_i2v_v###.json
  /finish/                          VID_finish_v###.json

/manifests                          Job tracking
  /jobs/                            Per-job JSON manifests
  /reviews/                         Review gate logs
  /sequences/                       Long-form video sequence manifests

/scripts                            Setup and verification
/docs                               Documentation
  /system/                          naming_convention.md, architecture.md
  /roadmap/                         build_plan.md
  /sops/                            Standard operating procedures
  /review_rules/                    Review gate criteria

/exports                            Contact sheets, deliverables
/tests                              Unit and integration tests
```

## Quick Start

### 1. Environment Setup

```bash
# Copy template and fill in real credentials
cp .env.example infra/env/staging.env
# Edit staging.env with:
#   - Backblaze B2 keys (S3_ACCESS_KEY, S3_SECRET_KEY, S3_ENDPOINT_URL)
#   - Supabase Postgres connection (POSTGRES_HOST, POSTGRES_PASSWORD)
#   - COMFYUI_URL is set per pod session, never hardcoded
```

**Security:** `infra/env/*.env` files are gitignored. Never commit credentials.

### 2. Infrastructure Init

```bash
# Initialize S3 bucket structure (both SFW + adult buckets)
pip install boto3
python3 scripts/setup_s3_structure.py

# Initialize Postgres schema (5 tables)
# Copy scripts/setup_postgres_schema.sql → run in Supabase SQL Editor

# Initialize Runpod volume (model directories, requirements template)
# SSH into pod, then:
bash scripts/setup_volume.sh
```

### 3. Verification

```bash
# S3 connectivity + round-trip + folder structure
python3 scripts/verify_s3.py

# Postgres connectivity + 5 tables + round-trip INSERT/SELECT/DELETE
python3 scripts/verify_postgres.py

# ComfyUI API pipeline (requires running pod)
export COMFYUI_URL=https://<pod-id>-8188.proxy.runpod.net
python3 scripts/verify_comfyui.py
```

All scripts exit 0 on success, exit 1 on failure.

### 4. Docker (Runpod)

```bash
cd infra/compose
docker-compose -f docker-compose.staging.yml up -d
```

## Build Phases

| Phase | Name | Status | Details |
|-------|------|--------|---------|
| 1 | Skeleton | COMPLETE | Runpod, Docker, ComfyUI, B2, Postgres, repo, naming |
| 2 | Creative OS | Next | Character system, house aesthetic, workflows |
| 3 | Production Loop | Planned | Orchestrator, panel, manifest system, review gates |
| 4 | Money Layer | Planned | Lane policies, publishing, growth assets, KPI |
| 5 | Voice + Automation | Planned | TTS, auto-scoring, batch processing |

See [docs/roadmap/build_plan.md](docs/roadmap/build_plan.md) for full breakdown with "Ready when" criteria.

## Key Documents

| Document | Purpose |
|----------|---------|
| [AI_OFM_Production_Pipeline_v1.md](AI_OFM_Production_Pipeline_v1.md) | Master technical spec (stack, architecture, workflows, schema, SOPs) |
| [AI_Content_System_Build.md](AI_Content_System_Build.md) | Build checklist with "Ready when" gate criteria |
| [Video_Splicing.md](Video_Splicing.md) | Long-form video assembly (sequence layer, clip taxonomy) |
| [docs/system/naming_convention.md](docs/system/naming_convention.md) | Single source of truth for all naming rules |
| [docs/system/architecture.md](docs/system/architecture.md) | 7-layer system architecture |
| [docs/roadmap/build_plan.md](docs/roadmap/build_plan.md) | Phase-by-phase build plan with status tracking |

## Naming Convention

All files follow [docs/system/naming_convention.md](docs/system/naming_convention.md):

| Rule | Example |
|------|---------|
| All names: lowercase snake_case | `chara_sfw_hero_mirror.png` |
| Versions: v001, v002, v003 | `lora_chara_v003.safetensors` |
| Dates: YYYY_MM_DD | `job_2026_03_11_chara_sfw_hero_00421` |
| Characters: immutable IDs | `chara`, `charb`, `charc` |
| Buckets: hyphens (S3 exception) | `ofm-staging`, `ofm-staging-adult` |
| Lane separation: never mix | SFW and adult assets in separate buckets always |

## Operational Principle

**Manual-first, system-first:** build a disciplined manual pipeline first.
Automation comes on top as routing/scoring/job-running layer, not instead of production discipline.

**Raw output is never published.** Every clip passes through a finish stage.
