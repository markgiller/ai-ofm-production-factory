#!/usr/bin/env python3
# scripts/verify_postgres.py
#
# Smoke test for Postgres connectivity and schema.
# Checks:
#   1. Connection succeeds
#   2. Schema ofm_staging exists
#   3. All 5 tables present: jobs, assets, characters, workflows, review_scores
#   4. Round-trip: INSERT test row → SELECT → DELETE
#
# Exit 0 = all checks pass. Exit 1 = one or more failures.
#
# Usage:
#   export POSTGRES_HOST=db.<ref>.supabase.co
#   export POSTGRES_USER=postgres
#   export POSTGRES_PASSWORD=<password>
#   export POSTGRES_DB=postgres
#   export POSTGRES_SCHEMA=ofm_staging
#   python3 scripts/verify_postgres.py

import os
import sys

REQUIRED_VARS = [
    "POSTGRES_HOST",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
]

EXPECTED_TABLES = ["jobs", "assets", "characters", "workflows", "review_scores"]
TEST_JOB_ID = "verify_test_job_do_not_use"


def get_conn():
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    schema = os.environ.get("POSTGRES_SCHEMA", "ofm_staging")
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        options=f"-c search_path={schema}",
        connect_timeout=10,
        sslmode="require",
    )


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "✓" if ok else "✗"
    msg = f"  {status} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return ok


def main():
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print("Error: missing required environment variables:")
        for v in missing:
            print(f"  {v}")
        print()
        print("Export them before running:")
        print("  export POSTGRES_HOST=db.<ref>.supabase.co")
        print("  export POSTGRES_USER=postgres")
        print("  export POSTGRES_PASSWORD=<password>")
        print("  export POSTGRES_DB=postgres")
        print("  export POSTGRES_SCHEMA=ofm_staging")
        sys.exit(1)

    schema = os.environ.get("POSTGRES_SCHEMA", "ofm_staging")
    results = []

    # ── 1. Connection ──────────────────────────────────────────────────────────
    print("\n[postgres] connecting...")
    try:
        conn = get_conn()
        cur = conn.cursor()
        results.append(check("connection", True))
    except Exception as e:
        results.append(check("connection", False, str(e)))
        print("\n✗ Cannot connect. Fix error above and re-run.")
        sys.exit(1)

    # ── 2. Schema exists ───────────────────────────────────────────────────────
    cur.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
        (schema,),
    )
    results.append(check(f"schema '{schema}' exists", cur.fetchone() is not None))

    # ── 3. Tables present ─────────────────────────────────────────────────────
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        """,
        (schema,),
    )
    found_tables = {row[0] for row in cur.fetchall()}
    for table in EXPECTED_TABLES:
        results.append(check(f"table '{table}'", table in found_tables))

    # ── 4. Round-trip write/read/delete ───────────────────────────────────────
    try:
        cur.execute(
            f"""
            INSERT INTO {schema}.jobs (id, lane, character_id, workflow_id, status)
            VALUES (%s, 'sfw', 'chara', 'verify_workflow', 'pending')
            ON CONFLICT (id) DO NOTHING
            """,
            (TEST_JOB_ID,),
        )
        conn.commit()

        cur.execute(
            f"SELECT id FROM {schema}.jobs WHERE id = %s", (TEST_JOB_ID,)
        )
        row = cur.fetchone()
        results.append(check("round-trip INSERT → SELECT", row is not None))

        cur.execute(f"DELETE FROM {schema}.jobs WHERE id = %s", (TEST_JOB_ID,))
        conn.commit()
        results.append(check("round-trip DELETE confirmed", True))
    except Exception as e:
        results.append(check("round-trip write/read/delete", False, str(e)))
        conn.rollback()

    cur.close()
    conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 40}")
    print(f"  {passed}/{total} checks passed")

    if all(results):
        print("\nPostgres layer OK.")
        sys.exit(0)
    else:
        print("\nSome checks failed. Fix errors above and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
