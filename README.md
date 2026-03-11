# AI OFM Production Factory

Production pipeline for AI-generated content: stable characters, high-quality stills,
controllable short-form video, and long-form assembly.

One technical core, two output lanes (SFW + lawful adult), full reproducibility.

## Stack

| Layer | Tool |
|-------|------|
| Compute | Runpod RTX 4090 24GB (cloud) |
| Runtime | Dockerized ComfyUI (headless API) |
| Image | FLUX.2 [klein] 4B + LoRA + refs |
| Video | Wan 2.2 TI2V-5B + interpolation + upscale |
| Storage | Backblaze B2 (S3-compatible) |
| Metadata | Supabase Postgres + JSON manifests |
| Orchestration | FastAPI (planned) |

## Repository Structure

```
/infra          Docker, compose, env templates, deploy configs
/services       orchestrator, internal panel, workers (Phase 3)
/models         base model refs, LoRA registry
/refs           character/style reference packs
/creative       briefs, character bibles, style bibles, shot library
/workflows      5 versioned ComfyUI JSON graphs (Phase 2)
/manifests      job manifests, review logs, sequence manifests
/scripts        setup and verification scripts
/docs           SOPs, review rules, system docs, roadmap
/exports        contact sheets, deliverables
/tests          unit and integration tests
```

## Quick Start

### 1. Environment

Copy `.env.example` to `infra/env/staging.env` and fill in credentials:
- Backblaze B2 (S3) keys
- Supabase Postgres connection
- ComfyUI URL (set per pod session, not hardcoded)

### 2. Infrastructure Setup

```bash
# S3 bucket structure (both SFW + adult buckets)
python3 scripts/setup_s3_structure.py

# Postgres schema (5 tables)
# Run scripts/setup_postgres_schema.sql in Supabase SQL Editor
```

### 3. Verification

```bash
python3 scripts/verify_s3.py
python3 scripts/verify_postgres.py

# ComfyUI (requires running pod):
export COMFYUI_URL=https://<pod-id>-8188.proxy.runpod.net
python3 scripts/verify_comfyui.py
```

### 4. Docker (Runpod)

```bash
cd infra/compose
docker-compose -f docker-compose.staging.yml up -d
```

## Build Phases

See [docs/roadmap/build_plan.md](docs/roadmap/build_plan.md) for full status.

| Phase | Name | Status |
|-------|------|--------|
| 1 | Skeleton | COMPLETE |
| 2 | Creative OS | Next |
| 3 | Production Loop | Planned |
| 4 | Money Layer | Planned |
| 5 | Voice + Automation | Planned |

## Key Documents

- [AI_OFM_Production_Pipeline_v1.md](AI_OFM_Production_Pipeline_v1.md) — master technical spec
- [AI_Content_System_Build.md](AI_Content_System_Build.md) — build checklist
- [Video_Splicing.md](Video_Splicing.md) — long-form video assembly
- [docs/system/naming_convention.md](docs/system/naming_convention.md) — naming standard
- [docs/system/architecture.md](docs/system/architecture.md) — system architecture

## Naming Convention

All files follow `docs/system/naming_convention.md`. Key rules:
- lowercase snake_case everywhere
- versions: `v001`, `v002` (never `v1`, `v2`)
- dates: `YYYY_MM_DD`
- characters: `chara`, `charb`, `charc` (immutable once published)
