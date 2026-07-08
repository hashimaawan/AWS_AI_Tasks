import boto3
from PIL import Image
import io
import os

s3 = boto3.client("s3")
DEST_BUCKET = os.environ["DEST_BUCKET"]
MAX_SIZE = (300, 300)

def lambda_handler(event, context):
    rec = event["Records"][0]["s3"]
    src_bucket = rec["bucket"]["name"]
    key = rec["object"]["key"]

    obj = s3.get_object(Bucket=src_bucket, Key=key)
    img = Image.open(io.BytesIO(obj["Body"].read()))
    img_format = img.format or "PNG"
    img.thumbnail(MAX_SIZE)

    buf = io.BytesIO()
    img.save(buf, format=img_format)
    buf.seek(0)

    s3.put_object(Bucket=DEST_BUCKET, Key=f"resized-{key}", Body=buf)
    return {"status": "done", "key": key, "size": img.size}