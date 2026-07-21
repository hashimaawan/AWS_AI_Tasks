"""
AWS Lambda handler — the plumbing that replaces local_runner.py.

Triggered by an S3 'object created' event. For each new PDF it:
  1. downloads the PDF bytes from S3
  2. runs process_pdf() from pipeline.py  (the UNCHANGED shared core)
  3. writes the structured result to DynamoDB
  4. copies the original into sorted/<category>/ in the same bucket

document_id is the sha256 of the file's bytes, so re-processing the SAME
PDF overwrites its row instead of creating a duplicate. This makes the
handler idempotent against S3's at-least-once delivery and manual re-uploads.

Environment variable:
  TABLE_NAME  - DynamoDB table name (default: document-metadata)
"""

import os
import hashlib
import urllib.parse

import boto3                       # provided by the Lambda runtime; do NOT bundle
from pipeline import process_pdf   # our logic, unchanged from local

s3 = boto3.client("s3")
table = boto3.resource("dynamodb").Table(os.environ.get("TABLE_NAME", "document-metadata"))


def lambda_handler(event, context):
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        # S3 URL-encodes the key (spaces -> '+', etc.) - always decode it.
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        # Safety: only handle PDFs under incoming/ (belt-and-braces with the
        # trigger's prefix/suffix filter, to avoid ever looping on our own output).
        if not key.lower().endswith(".pdf") or not key.startswith("incoming/"):
            print(f"Skipping {key}")
            continue

        pdf_bytes = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        result = process_pdf(pdf_bytes)

        # Content-derived id: same bytes -> same id -> overwrite, not duplicate.
        document_id = hashlib.sha256(pdf_bytes).hexdigest()
        filename = key.split("/")[-1]

        table.put_item(Item={
            "document_id": document_id,
            "source_key": key,
            "category": result["category"],
            "fields": result["fields"],          # map of strings
            "char_count": result["char_count"],  # int -> DynamoDB Number
        })

        dest_key = f"sorted/{result['category']}/{filename}"
        s3.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key},
            Key=dest_key,
        )

        print(f"Processed {key} -> {result['category']} | fields={result['fields']}")

    return {"statusCode": 200, "processed": len(event.get("Records", []))}