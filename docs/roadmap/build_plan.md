# Build Plan

## Phase 1 — Skeleton (COMPLETE)

Infrastructure foundation. "Правильный пустой каркас."

| Component | Deliverable | Status |
|-----------|-------------|--------|
| Compute | Runpod RTX 4090 24GB cloud pod | DONE |
| Runtime | Dockerized ComfyUI headless API (staging + production) | DONE |
| Storage | Backblaze B2: ofm-staging + ofm-staging-adult (13 folders) | DONE |
| Metadata | Supabase Postgres: 5 tables in ofm_staging schema | DONE |
| Repo | Git repository with full directory structure (35 dirs) | DONE |
| Naming | naming_convention.md sections 1-17 | DONE |
| Staging/prod | Separate Dockerfile, start.sh, env, docker-compose | DONE |
| Verify scripts | verify_s3.py, verify_postgres.py, verify_comfyui.py | DONE |

### Known Issues Deferred to Phase 2
- FLUX.2-klein-4B text encoder: model expects 7680-dim input, T5-XXL gives 4096-dim
- FLUX VAE file: 128 scale factors instead of expected 16 (investigate symlinks on pod)
- Phase 1 Runtime gate passed with EmptyImage workflow (model-free API proof)

---

## Phase 2 — Creative OS (NEXT)

Character system, house aesthetic, shot grammar, workflow library.

| Component | Deliverable | Status |
|-----------|-------------|--------|
| Character system | LoRA training pipeline, ref packs, character bible template | TODO |
| House aesthetic | Style LoRA, skin finish rules, lens/light logic | TODO |
| Shot grammar | 8 shot types with prompt blocks + repair rules | TODO |
| Workflow library | 5 versioned ComfyUI JSON graphs (explore/hero/repair/video/finish) | TODO |
| FLUX integration | Resolve text encoder mismatch, validate VAE, test full T2I pipeline | TODO |

### Ready When
- "есть repeatable output для explore, hero, repair, video, finish"
- Face, hands, light, clothing, background pass basic QC
- Character identity stable across 50+ frames

---

## Phase 3 — Production Loop

Orchestrator, operator panel, end-to-end job execution.

| Component | Deliverable | Status |
|-----------|-------------|--------|
| Orchestrator | FastAPI service: job intake, param injection, ComfyUI integration | TODO |
| Internal panel | Web UI for operator: launch jobs, review, accept/reject | TODO |
| Manifest system | Auto-generate JSON manifest per job, store in S3 + Postgres | TODO |
| Review gates | Identity gate, polish gate, shot gate, motion gate | TODO |

### Ready When
- "оператор может запустить production job через panel/API, а не собирать pipeline руками"
- Every winner reproducible from manifest

---

## Phase 4 — Money Layer

Policy lanes, publishing, growth assets, KPI.

| Component | Deliverable | Status |
|-----------|-------------|--------|
| Lane separation | SFW/adult policy configs, compliance logs, age-gating | TODO |
| Publishing | Platform variants (IG/Threads/Fanvue), caption system | TODO |
| Promo/growth assets | Promo stills, teasers, story content pipeline | TODO |
| KPI/analytics | Performance tracking, winner analysis, cost tracking | TODO |

---

## Phase 5 — Voice + Partial Automation

| Component | Deliverable | Status |
|-----------|-------------|--------|
| Voice module v2 | TTS integration, voice-over for video | TODO |
| Partial automation | Auto-scoring, auto-routing, batch processing | TODO |
