#!/usr/bin/env python3
# scripts/setup_s3_structure.py
#
# One-time script to create the folder structure in both S3 buckets.
# Creates .keep marker files to establish the folder hierarchy.
# Idempotent — safe to re-run (existing .keep files are silently overwritten).
#
# Initialises BOTH buckets: SFW (S3_BUCKET_NAME) and Adult (S3_BUCKET_NAME_ADULT).
# Lane separation is a hard constraint from day one — see naming_convention.md §17.
#
# Usage:
#   pip install boto3
#   export S3_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
#   export S3_ACCESS_KEY=<keyID>
#   export S3_SECRET_KEY=<applicationKey>
#   export S3_REGION=<region>
#   export S3_BUCKET_NAME=ofm-staging
#   export S3_BUCKET_NAME_ADULT=ofm-staging-adult
#   python3 scripts/setup_s3_structure.py

import os
import sys
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Required environment variables
REQUIRED_VARS = [
    "S3_ENDPOINT_URL",
    "S3_ACCESS_KEY",
    "S3_SECRET_KEY",
    "S3_BUCKET_NAME",
    "S3_BUCKET_NAME_ADULT",
]

# Canonical folder structure.
# Derived from AI_OFM_Production_Pipeline_v1.md §5 and naming_convention.md §11.
#
# refs/characters/    ← character ref assets, versioned in filename (§10)
# refs/styles/        ← house aesthetic style refs
# refs/locations/     ← location reference images
# refs/backgrounds/   ← background reference images
# outputs/raw/        ← raw ComfyUI outputs before review gate
# outputs/final/      ← accepted winners after review gate
# workflow_snapshots/ ← exact workflow JSON snapshot at job time (reproducibility)
# review_assets/      ← contact sheets and gate review assets (§12)
# sequences/          ← long-form assembled videos (Video_Splicing.md, §9)
# thumbs/             ← preview thumbnails per asset
# audio/              ← audio beds, room tone, texture layers
# voice/              ← TTS / voice cloning outputs (Phase 5)
# captions/           ← platform caption files (Phase 4)
STRUCTURE = [
    "refs/characters/",
    "refs/styles/",
    "refs/locations/",
    "refs/backgrounds/",
    "outputs/raw/",
    "outputs/final/",
    "workflow_snapshots/",
    "review_assets/",
    "sequences/",
    "thumbs/",
    "audio/",
    "voice/",
    "captions/",
]


def get_client() -> boto3.client:
    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def setup_bucket(client, bucket: str) -> bool:
    print(f"\n[{bucket}] connecting...")

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            print(f"[{bucket}] ✗ bucket not found — create it in Backblaze B2 first")
        elif code in ("403", "AccessDenied"):
            print(f"[{bucket}] ✗ access denied — check your API token permissions")
        else:
            print(f"[{bucket}] ✗ unexpected error ({code}): {e}")
        return False

    print(f"[{bucket}] ✓ bucket accessible")
    print(f"[{bucket}] creating structure...")

    for folder in STRUCTURE:
        key = f"{folder}.keep"
        client.put_object(Bucket=bucket, Key=key, Body=b"")
        print(f"  ✓ {key}")

    return True


def main():
    # Validate required env vars — fail fast with clear message
    missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
    if missing:
        print("Error: missing required environment variables:")
        for v in missing:
            print(f"  {v}")
        print()
        print("Export them before running:")
        print("  export S3_ENDPOINT_URL=https://s3.<region>.backblazeb2.com")
        print("  export S3_ACCESS_KEY=<keyID>")
        print("  export S3_SECRET_KEY=<applicationKey>")
        print("  export S3_REGION=<region>")
        print("  export S3_BUCKET_NAME=ofm-staging")
        print("  export S3_BUCKET_NAME_ADULT=ofm-staging-adult")
        sys.exit(1)

    client = get_client()

    buckets = [
        os.environ["S3_BUCKET_NAME"],
        os.environ["S3_BUCKET_NAME_ADULT"],
    ]

    results = {bucket: setup_bucket(client, bucket) for bucket in buckets}

    print("\n" + "=" * 50)
    for bucket, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {bucket}")

    if all(results.values()):
        print("\nDone. Both buckets initialized.")
        sys.exit(0)
    else:
        print("\nSome buckets failed. Fix errors above and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
