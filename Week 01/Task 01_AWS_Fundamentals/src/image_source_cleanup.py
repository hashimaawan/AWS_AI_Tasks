import boto3
import os

s3 = boto3.resource("s3")
BUCKET = os.environ["SOURCE_BUCKET"]

def lambda_handler(event, context):
    bucket = s3.Bucket(BUCKET)
    count = sum(1 for _ in bucket.objects.all())
    bucket.objects.all().delete()
    return {"status": "emptied", "bucket": BUCKET, "objects_deleted": count}