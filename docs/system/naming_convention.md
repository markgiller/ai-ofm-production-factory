# Naming Convention

This document defines the **canonical naming rules for the entire system**.

This file is the **single source of truth** for naming across:

- assets
- workflows
- jobs
- manifests
- LoRA models
- references
- sequences
- storage paths

Every service, agent, script, and operator **must follow these rules**.

If a new entity type appears in the system, the naming rule must be added here first.

---

# 1. Global Rules

All system identifiers follow the same base principles.

## Character case

All names use:

```
lowercase snake_case
```

Allowed characters:

```
a-z
0-9
_
```

Not allowed:

```
spaces
camelCase
kebab-case
special symbols
```

---

## Version format

All versioned entities use:

```
v001
v002
v003
```

NOT:

```
v1
v2
v10
```

Reason: proper lexical sorting.

---

## Date format

All timestamps use:

```
YYYY_MM_DD
```

Example:

```
2026_03_09
```

---

## File naming philosophy

Names must be:

- descriptive
- deterministic
- machine readable

File names must allow understanding the asset **without opening the manifest**.

---

# 2. Workflow Naming

Workflows must follow this pattern:

```
<purpose>_<model>_<character|generic>_<style>_v###.json
```

Examples:

```
explore_flux2k4b_generic_editorial_v001.json
hero_flux2k4b_chara_editorial_v003.json
repair_flux2k4b_chara_editorial_v002.json
video_wan22_chara_editorial_v001.json
finish_video_master_v001.json
```

Purpose examples:

```
explore
hero
repair
video
finish
sequence
```

---

# 3. Job ID Naming

Jobs follow this format:

```
job_<date>_<character>_<lane>_<workflow>_<number>
```

Example:

```
job_2026_03_09_chara_sfw_hero_00421
```

Fields:

| Field | Description |
|------|-------------|
| date | job creation date |
| character | character id |
| lane | sfw / adult |
| workflow | workflow type |
| number | sequential job counter |

---

# 4. Manifest Naming

Manifest files mirror the job ID.

Format:

```
job_<job_id>.json
```

Example:

```
job_2026_03_09_chara_sfw_hero_00421.json
```

Manifest keys must use:

```
snake_case
```

Example keys:

```
job_id
workflow_version
model_hash
references_used
final_asset_paths
```

---

# 5. Character Naming

Character identifiers must be short and stable.

Format:

```
char<letter>
```

Examples:

```
chara
charb
charc
```

These IDs are used across:

- jobs
- assets
- LoRA
- sequences
- storage

Character IDs must **never change once published**.

---

# 6. LoRA Naming

LoRA models follow this pattern:

```
lora_<subject>_v###
```

Examples:

```
lora_chara_v006.safetensors
lora_house_editorial_v003.safetensors
lora_skinfinish_v002.safetensors
```

Subject types:

```
character
house_style
skin_finish
lighting
wardrobe
```

---

# 7. Image Asset Naming

Hero images follow this format:

```
<character>_<lane>_<shot_type>_<composition>_<ratio>_v###_seed####.png
```

Example:

```
chara_sfw_hero_mirror_9x16_v012_seed483829.png
```

Fields:

| Field | Description |
|------|-------------|
| character | character id |
| lane | sfw / adult |
| shot_type | hero / medium / mirror / seated |
| composition | scene type |
| ratio | 9x16 / 1x1 / 4x5 |
| version | image iteration |
| seed | generation seed |

---

# 8. Video Asset Naming

Video master format:

```
<character>_<scene>_<ratio>_master_v###.mp4
```

Example:

```
chara_walkin_9x16_master_v004.mp4
```

Source clips:

```
<character>_<scene>_src_v###.mp4
```

Example:

```
chara_walkin_src_v002.mp4
```

---

# 9. Sequence Naming

Sequences represent long-form assembled videos.

Format:

```
seq_<date>_<character>_<number>
```

Example:

```
seq_2026_03_09_chara_0007
```

Sequence outputs:

```
seq_2026_03_09_chara_0007_master.mp4
seq_2026_03_09_chara_0007_preview.mp4
```

---

# 10. Reference Asset Naming

Reference assets must follow:

```
<character>_<ref_type>_v###
```

Examples:

```
chara_face_v004.png
chara_body_v003.png
chara_hair_makeup_v002.png
chara_signature_pose_v001.png
```

---

# 11. Storage Path Naming

Storage keys must follow the system storage architecture.

Base bucket:

```
s3://ofm-prod/
```

Paths:

```
refs/
outputs/raw/YYYY/MM/DD/
outputs/final/YYYY/MM/DD/
workflow_snapshots/
review_assets/
thumbs/
audio/
voice/
captions/
```

Example:

```
s3://ofm-prod/outputs/raw/2026/03/09/job_2026_03_09_chara_sfw_hero_00421.png
```

---

# 12. Review Asset Naming

Review files follow:

```
review_<job_id>_<type>.png
```

Examples:

```
review_job_2026_03_09_chara_sfw_hero_00421_thumb.png
review_job_2026_03_09_chara_sfw_hero_00421_contactsheet.png
```

---

# 13. Forbidden Naming

The following naming patterns are **strictly forbidden**:

```
final_new_real_v2_last.json
test_new_final_fixed.png
video_last_v3_final2.mp4
image_final_final.png
```

Reasons:

- breaks automation
- breaks manifest linking
- impossible to parse programmatically

---

# 14. Naming Change Policy

Naming rules may only be changed through:

```
docs/system/naming_convention.md
```

All changes must be:

- reviewed
- version controlled
- applied globally

---

# 15. Core Principle

Naming is not cosmetic.

Naming is **production discipline**.

A clean naming system enables:

- reproducibility
- automation
- orchestration
- debugging
- scaling

Without strict naming, the factory collapses into chaos.