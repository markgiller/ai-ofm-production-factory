# Build Plan

Порядок сборки — не по красоте, а по уму. Каждый этап опирается на предыдущий.

Система состоит из 5 больших машин:
1. **Production core** — GPU, runtime, storage, DB, orchestrator
2. **Creative OS** — character lock, style, shot grammar, briefs, refs
3. **Content engine** — explore -> hero -> repair -> video -> finish
4. **Money filter** — review gates, scoring, ruthless curation
5. **Growth engine** — promo variants, thumbnails, reels/carousels, publish presets, KPI feedback

---

## Phase 1 — Skeleton (COMPLETE)

Infrastructure foundation. "Правильный пустой каркас."

| Component | Deliverable | Готово, когда | Status |
|-----------|-------------|---------------|--------|
| Compute | Runpod RTX 4090 24GB cloud pod | можно стабильно гонять image/video jobs без ручного UI-бардака | DONE |
| Runtime | Dockerized ComfyUI headless API | workflow запускается JSON'ом, а не руками | DONE |
| Storage | Backblaze B2: ofm-staging + ofm-staging-adult (13 folders) | raw/final разнесены, каждый output можно найти по job/manifest | DONE |
| Metadata | Supabase Postgres: 5 tables in ofm_staging schema | любой winner можно воспроизвести | DONE |
| Repo structure | Git repo with full directory structure (35 dirs) | любой новый оператор понимает, где лежит что | DONE |
| Naming | naming_convention.md sections 1-17 | нет файлов вида final_new_real_v2_last.json | DONE |
| Staging/prod | Separate Dockerfile, start.sh, env, docker-compose | прод не трогают для R&D | DONE |
| Verify scripts | verify_s3.py, verify_postgres.py, verify_comfyui.py | все скрипты exit 0 | DONE |

### Verification Evidence
- verify_s3.py: bucket connect + round-trip PUT/GET/DELETE + folder structure
- verify_postgres.py: 9/9 checks (connection, schema, 5 tables, round-trip INSERT/SELECT/DELETE)
- verify_comfyui.py: 5/5 checks (system_stats, POST /prompt, poll /queue, GET /history, output file)

### Notes
- Phase 1 Runtime gate passed with EmptyImage workflow (model-free API proof).
- Image backbone migrated from FLUX.2 Klein 4B → FLUX.1 Dev 12B (fp8) on 2026-03-15 due to FaceSim plateau and lack of IP-Adapter support. See `docs/sops/lora_training_flux1dev.md` for full rationale.

---

## Phase 2 — Creative OS (NEXT)

Character system, house aesthetic, shot grammar, workflow library.
This phase gives the factory its creative identity and repeatable production capability.

| Component | Deliverable | Готово, когда | Status |
|-----------|-------------|---------------|--------|
| Creative memory | Briefs, character bibles, style bibles, shot library, platform specs | каждый asset стартует не с пустого промпта, а из structured input | TODO |
| Character system | Character LoRA, ref packs, character bible, forbidden drift, approved shot families | персонаж стабилен из поста в пост и не "плавает" | TODO |
| House aesthetic | Style LoRA, skin finish, lens behavior, light logic, color mood, editorial polish | разные сцены ощущаются как один бренд | TODO |
| Shot grammar | 8 shot types: hero close-up, medium conversational, mirror, entrance/walking, seated idle, over-shoulder, reaction, CTA end frame | у каждого shot type есть prompt block, refs, preferred ratios, failure modes, repair rules и примеры winners | TODO |
| Workflow library | 5 versioned ComfyUI JSON graphs (explore/hero/repair/video/finish) | workflow versionируется, имеет changelog и snapshot при запуске job | TODO |
| FLUX integration | FLUX.1 Dev 12B (fp8) loaded, LoRA training via ai-toolkit | FLUX.1 Dev генерирует стабильный output через API | DONE |

### Model layer (prerequisite for workflows)
- Image backbone: FLUX.1 Dev 12B (fp8) — explore, hero, repair, editing
- Video backbone: Wan 2.2 TI2V-5B — source clip 720p/24fps
- Finishing: upscale + interpolation + encode — every clip passes through finish stage

**Готово, когда:** есть repeatable output для explore, hero, repair, video, finish.

---

## Phase 3 — Production Loop

Orchestrator, operator panel, end-to-end job execution with full traceability.

| Component | Deliverable | Готово, когда | Status |
|-----------|-------------|---------------|--------|
| Orchestrator | FastAPI: job intake, parameter injection, /prompt, /queue, /history, save outputs, manifests, DB write | оператор запускает job через panel/API, а не собирает пайплайн руками | TODO |
| Internal panel | Web UI: lane, character, workflow, refs, params, publish target, notes | оператор может без техдолга запускать production jobs | TODO |
| Brief intake | Structured brief: character, plot, emotional tone, shot type, channel, post goal | brief полный, однозначный и пригоден для explore | TODO |
| Explore line | 10-50 variations, contact sheet, shortlist JSON, seeds | из explore выходят 1-3 кандидата, которых реально стоит доводить | TODO |
| Select layer | Seed fixation, notes, shortlist decision | selected frame уже ощущается дорогим, а не generic | TODO |
| Hero line | Ref injection, LoRA, pose/control, two-pass, inpaint, upscale | лицо, руки, свет, одежда и фон проходят базовый QC | TODO |
| Repair line | repair_face, repair_hands, repair_clothing, repair_background, repair_identity_preserve | нет заметных артефактов и drift | TODO |
| Video line | Wan 2.2 short controllable clips, subtle motion, 720p/24fps source | движение естественное, без morphing/stutter | TODO |
| Finish line | Interpolation, upscale, encode, caption/audio flags, platform variants | есть 1080p master + channel variants + preview thumb + final manifest | TODO |
| Review gates | Identity gate, polish gate, shot gate, motion gate, thumbnail gate, channel gate | у каждого reject есть конкретная причина, "нормально" в прод не уходит | TODO |

### Manifest system
Every job auto-generates a JSON manifest with: job_id, date, operator, lane, workflow_version,
model_version, model_hash, LoRA versions, references_used, seed, parameters, outputs,
accepted/rejected, final_asset_paths, notes.

**Готово, когда:** любой winner воспроизводим по manifest + S3 files, оператор не собирает pipeline руками.

---

## Phase 4 — Money Layer

Policy lanes, publishing, growth assets, KPI. "То, что реально тянет людей и деньги."

| Component | Deliverable | Готово, когда | Status |
|-----------|-------------|---------------|--------|
| Policy / lane separation | SFW + lawful adult: разные packs, approval rules, storage flags, review flags, publishing rules | sensitive assets и brand-safe assets не смешиваются ни по storage, ни по review, ни по publish | TODO |
| Promo / growth asset line | Carousels, reels, thumbnail-first кадры, CTA end frames, hook-first variants, platform-native crops, post packages | на каждый hero asset фабрика выпускает growth-pack для соцсетей, а не только "основной файл" | TODO |
| Publishing system | Publish presets по каналам (IG/Threads/Fanvue), asset ID, связь с performance tracking | каждый опубликованный asset имеет канал, дату, вариант и результат | TODO |
| KPI / analytics | Keeper rate, rework count, time-to-final, character drift incidents, cost per accepted asset, accepted assets per GPU hour, video completion rate, channel metrics | видно, какой workflow реально делает winners, а какой просто жжет GPU | TODO |

### Long-form video assembly (sequences)
Assembles 12-25 short clips (3-8 sec each) into 2-3 minute videos.
Additional workflows: SEQ_plan, SEQ_gapcheck, SEQ_source_batch, SEQ_select, SEQ_assemble, SEQ_audio, SEQ_package.
Clip taxonomy: anchor, bridge, detail, reaction, entry, exit, cover, alt_take.
See Video_Splicing.md for full spec.

**Готово, когда:** контент замыкается на метрики, growth-pack идёт автоматически, long-form видео собирается из коротких клипов.

---

## Phase 5 — Voice + Partial Automation

"Только потом" — после доказанной manual repeatability.

| Component | Deliverable | Готово, когда | Status |
|-----------|-------------|---------------|--------|
| Voice module v2 | TTS/voice cloning, lip sync, breathing/ambience/pauses, final audio mix | можно менять текст, темп, эмоцию и язык без перегенерации клипа | TODO |
| Partial automation | Scoring, batch scheduling, top-N selection, auto-routing в repair | вы уже умеете руками стабильно выпускать winners, автоматизация ускоряет дисциплину | TODO |

**Готово, когда:** автоматизация ускоряет дисциплину, а не заменяет её.

---

## Anti-chaos Rules (v1)

Non-goals that maintain focus:
- Не строить multi-GPU cluster
- Не собирать тонну кастомных нод
- Не делать свою foundation model
- Не насиловать native 1080p/30 на одной 4090
- Не запускать fully autonomous agent до доказанной repeatability

**Готово, когда:** команда не расползается в "интересные эксперименты."
