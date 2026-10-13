"""Copy existing MinIO objects to local storage without deleting MinIO data.

Run this inside the currently running API container BEFORE recreating the
Compose stack. The current API container bind-mounts ./services/api at /app,
so its output is initially written to services/api/storage/uploads. Copy that
folder to the project-level ./storage/uploads on the host before `docker compose
up --build -d --remove-orphans` so the new persistent bind mount can use it.
"""
import os
from pathlib import Path

import boto3
from botocore.config import Config

endpoint = os.environ.get("OLD_MINIO_ENDPOINT", "http://minio:9000")
access_key = os.environ.get("OLD_MINIO_ACCESS_KEY", os.environ.get("S3_ACCESS_KEY", "minioadmin"))
secret_key = os.environ.get("OLD_MINIO_SECRET_KEY", os.environ.get("S3_SECRET_KEY", "minioadmin"))
bucket = os.environ.get("OLD_MINIO_BUCKET", os.environ.get("S3_BUCKET", "mock-interview-dev"))
root = Path(os.environ.get("MIGRATION_DEST", "/app/storage/uploads")).resolve()
root.mkdir(parents=True, exist_ok=True)

client = boto3.client(
    "s3", endpoint_url=endpoint, aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    config=Config(s3={"addressing_style": "path"}),
)

copied = 0
skipped = 0
paginator = client.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket):
    for item in page.get("Contents", []):
        key = item["Key"]
        target = (root / key).resolve()
        if root != target and root not in target.parents:
            print(f"SKIP unsafe key: {key!r}")
            skipped += 1
            continue
        if target.exists():
            print(f"SKIP already exists: {key}")
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        response = client.get_object(Bucket=bucket, Key=key)
        target.write_bytes(response["Body"].read())
        target.with_name(target.name + ".content-type").write_text(
            response.get("ContentType") or "application/octet-stream", encoding="utf-8"
        )
        copied += 1
        print(f"COPIED {key}")

print(f"Migration finished. copied={copied}, skipped={skipped}, destination={root}")
print("MinIO objects were not deleted. Verify the copied files before removing MinIO.")
