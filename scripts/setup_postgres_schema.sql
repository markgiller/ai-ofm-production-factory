-- scripts/setup_postgres_schema.sql
--
-- One-time schema setup for the OFM production factory metadata layer.
-- Idempotent — safe to re-run (uses IF NOT EXISTS throughout).
--
-- Creates schema: ofm_staging
-- Tables: jobs, assets, characters, workflows, review_scores
--
-- Schema design: AI_OFM_Production_Pipeline_v1.md §11
-- Naming: docs/system/naming_convention.md
--
-- Usage (Supabase SQL Editor or psql):
--   \i scripts/setup_postgres_schema.sql
--
-- psql direct:
--   psql "postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres" \
--        -f scripts/setup_postgres_schema.sql

-- ── Schema ────────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS ofm_staging;

SET search_path TO ofm_staging;

-- ── jobs ──────────────────────────────────────────────────────────────────────
-- Lifecycle record for every orchestrator run.
-- One row per ComfyUI job submission.

CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT        PRIMARY KEY,          -- job_YYYY_MM_DD_charX_lane_workflow_#####
    lane            TEXT        NOT NULL,             -- sfw | adult
    character_id    TEXT        NOT NULL,             -- chara | charb | charc
    brief_id        TEXT,                             -- brief_YYYY_MM_DD_#### (nullable for explore batches)
    workflow_id     TEXT        NOT NULL,             -- FK → workflows.workflow_id
    status          TEXT        NOT NULL DEFAULT 'pending',
                                                      -- pending | running | done | failed | rejected
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    operator        TEXT,                             -- who triggered the job
    cost_estimate   NUMERIC(10, 4),                  -- estimated GPU cost in USD
    notes           TEXT,                             -- operator notes / review flags

    CONSTRAINT jobs_lane_check        CHECK (lane IN ('sfw', 'adult')),
    CONSTRAINT jobs_status_check      CHECK (status IN ('pending', 'running', 'done', 'failed', 'rejected'))
);

-- ── assets ────────────────────────────────────────────────────────────────────
-- One row per output file produced by a job.
-- path stores the full s3:// key (see naming_convention.md §11).

CREATE TABLE IF NOT EXISTS assets (
    asset_id        TEXT        PRIMARY KEY,          -- derived from filename per naming §7 / §8
    job_id          TEXT        NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    type            TEXT        NOT NULL,             -- image | video | manifest | review | thumb | audio | caption
    path            TEXT        NOT NULL UNIQUE,      -- s3://ofm-staging/outputs/raw/YYYY/MM/DD/<file>
    width           INTEGER,                          -- px (null for non-visual assets)
    height          INTEGER,                          -- px
    fps             NUMERIC(5, 3),                   -- frames per second (video only)
    score_human     INTEGER,                          -- 1-5 operator quality rating (null = not rated)
    accepted        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT assets_type_check      CHECK (type IN ('image', 'video', 'manifest', 'review', 'thumb', 'audio', 'caption')),
    CONSTRAINT assets_score_check     CHECK (score_human IS NULL OR (score_human >= 1 AND score_human <= 5))
);

-- ── characters ────────────────────────────────────────────────────────────────
-- Current production state of each character entity.
-- character_id must never change once published (naming_convention §5).

CREATE TABLE IF NOT EXISTS characters (
    character_id        TEXT    PRIMARY KEY,          -- chara | charb | charc
    name                TEXT    NOT NULL,             -- human display name
    lane                TEXT    NOT NULL,             -- sfw | adult | both
    lora_version        TEXT,                         -- lora_chara_v###.safetensors (active version)
    ref_pack_version    TEXT,                         -- ref pack version in use
    style_bible_version TEXT,                         -- style bible version
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT characters_lane_check  CHECK (lane IN ('sfw', 'adult', 'both'))
);

-- ── workflows ─────────────────────────────────────────────────────────────────
-- Version registry for ComfyUI JSON graphs.
-- file_hash ensures reproducibility — same hash = same graph.

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id     TEXT        PRIMARY KEY,          -- e.g. img_explore_v001
    name            TEXT        NOT NULL,             -- IMG_explore, IMG_hero, IMG_repair, VID_i2v, VID_finish
    version         TEXT        NOT NULL,             -- v001 | v002 | v003
    file_hash       TEXT        NOT NULL,             -- SHA-256 of the workflow JSON at time of registration
    changelog       TEXT,                             -- what changed vs previous version
    active          BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT workflows_version_format CHECK (version ~ '^v[0-9]{3}$')
);

-- ── review_scores ─────────────────────────────────────────────────────────────
-- Optional per-job review gate scores. One row per reviewed job.
-- All scores: 0 = fail, 1 = pass.

CREATE TABLE IF NOT EXISTS review_scores (
    job_id              TEXT    PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    identity_score      INTEGER,    -- 0 | 1 — identity gate
    polish_score        INTEGER,    -- 0 | 1 — polish gate (skin, hands, cloth, bg, light)
    shot_score          INTEGER,    -- 0 | 1 — shot gate (composition, hook)
    motion_score        INTEGER,    -- 0 | 1 — motion gate (video only)
    thumbnail_score     INTEGER,    -- 0 | 1 — thumbnail gate
    channel_score       INTEGER,    -- 0 | 1 — channel/format gate
    publish_readiness   TEXT,       -- draft | ready | published
    notes               TEXT,
    reviewed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT rs_identity_check    CHECK (identity_score  IS NULL OR identity_score  IN (0, 1)),
    CONSTRAINT rs_polish_check      CHECK (polish_score     IS NULL OR polish_score     IN (0, 1)),
    CONSTRAINT rs_shot_check        CHECK (shot_score       IS NULL OR shot_score       IN (0, 1)),
    CONSTRAINT rs_motion_check      CHECK (motion_score     IS NULL OR motion_score     IN (0, 1)),
    CONSTRAINT rs_thumb_check       CHECK (thumbnail_score  IS NULL OR thumbnail_score  IN (0, 1)),
    CONSTRAINT rs_channel_check     CHECK (channel_score    IS NULL OR channel_score    IN (0, 1)),
    CONSTRAINT rs_readiness_check   CHECK (publish_readiness IS NULL OR publish_readiness IN ('draft', 'ready', 'published'))
);

-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_jobs_character    ON jobs(character_id);
CREATE INDEX IF NOT EXISTS idx_jobs_lane         ON jobs(lane);
CREATE INDEX IF NOT EXISTS idx_jobs_status       ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at   ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_assets_job_id     ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_assets_accepted   ON assets(accepted);
CREATE INDEX IF NOT EXISTS idx_assets_type       ON assets(type);
