#!/usr/bin/env python3
# scripts/verify_s3.py
#
# Smoke test for S3/B2 connectivity and folder structure.
# Tests both SFW and adult buckets.
#
# Checks:
#   1. Bucket accessible (head_bucket)
#   2. Round-trip write/read/delete
#   3. Expected top-level prefixes present
#
# Exit 0 = all checks pass. Exit 1 = one or more failures.
#
# Usage:
#   export S3_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
#   export S3_ACCESS_KEY=<keyID> S3_SECRET_KEY=<applicationKey> S3_REGION=<region>
#   export S3_BUCKET_NAME=ofm-staging S3_BUCKET_NAME_ADULT=ofm-staging-adult
#   python3 scripts/verify_s3.py

import os
import sys
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

TEST_KEY = "ofm_verify_test.tmp"
TEST_BODY = b"ofm_s3_verify"

# Top-level prefixes expected after setup_s3_structure.py has run
EXPECTED_PREFIXES = {
    "refs/",
    "outputs/",
    "workflow_snapshots/",
    "review_assets/",
    "sequences/",
    "thumbs/",
    "audio/",
    "voice/",
    "captions/",
}


def get_client() -> boto3.client:
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT_URL"),
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name=os.environ.get("S3_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def verify_bucket(client, bucket: str) -> list:
    failures = []

    # 1. Bucket accessible
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        failures.append(f"head_bucket failed ({code})")
        return failures  # No point continuing

    # 2. Round-trip: PUT → GET → DELETE
    try:
        client.put_object(Bucket=bucket, Key=TEST_KEY, Body=TEST_BODY)
        obj = client.get_object(Bucket=bucket, Key=TEST_KEY)
        content = obj["Body"].read()
        if content != TEST_BODY:
            failures.append("round-trip data mismatch")
        client.delete_object(Bucket=bucket, Key=TEST_KEY)
        # Confirm deletion
        try:
            client.head_object(Bucket=bucket, Key=TEST_KEY)
            failures.append("test object not deleted")
        except ClientError as e:
            if e.response["Error"]["Code"] != "404":
                failures.append(f"delete confirm failed: {e}")
    except ClientError as e:
        failures.append(f"round-trip failed: {e}")

    # 3. Expected folder structure
    try:
        resp = client.list_objects_v2(Bucket=bucket, Delimiter="/")
        found = {p["Prefix"] for p in resp.get("CommonPrefixes", [])}
        missing = EXPECTED_PREFIXES - found
        if missing:
            for prefix in sorted(missing):
                failures.append(f"missing prefix '{prefix}' — run setup_s3_structure.py")
    except ClientError as e:
        failures.append(f"list_objects failed: {e}")

    return failures


def main():
    required = ["S3_ACCESS_KEY", "S3_SECRET_KEY", "S3_BUCKET_NAME", "S3_BUCKET_NAME_ADULT"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Error: missing env vars: {', '.join(missing)}")
        sys.exit(1)

    client = get_client()

    buckets = [
        ("SFW   ", os.environ["S3_BUCKET_NAME"]),
        ("Adult ", os.environ["S3_BUCKET_NAME_ADULT"]),
    ]

    all_failures = []

    for label, bucket in buckets:
        print(f"\n[{label.strip()}] {bucket}")
        failures = verify_bucket(client, bucket)

        if failures:
            for f in failures:
                print(f"  ✗ {f}")
            all_failures.extend(failures)
        else:
            print("  ✓ bucket accessible")
            print("  ✓ round-trip (PUT / GET / DELETE)")
            print("  ✓ folder structure present")

    print()
    print("=" * 40)
    if not all_failures:
        print("S3 layer OK.")
        sys.exit(0)
    else:
        print(f"Failures: {len(all_failures)}")
        print("Fix above before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
