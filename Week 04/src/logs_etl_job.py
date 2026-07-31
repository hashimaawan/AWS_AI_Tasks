"""
logs_etl_job.py  --  AWS GLUE PYTHON SHELL JOB (Python 3.9)

WHAT IT DOES
  1. Retrieves log events from a CloudWatch log group (via the Logs API).
  2. Classifies each event as ERROR or INFO.
  3. Writes them to S3 partitioned by tag and date:
        s3://<bucket>/logs/processed/tag=error/dt=2025-07-27/events.json
        s3://<bucket>/logs/processed/tag=info/dt=2025-07-27/events.json
     (newline-delimited JSON -- one event per line)

  A crawler then catalogs this output and Athena queries it by date.

Python Shell jobs come with boto3 pre-installed, so there are no
dependencies to add.
"""
import boto3, json
from datetime import datetime, timezone, timedelta
from collections import defaultdict

REGION    = "eu-north-1"
LOG_GROUP = "/agrilink/app"
BUCKET    = "datalake-ha"  
# =====================================================

OUTPUT_PREFIX = "logs/processed"
LOOKBACK_DAYS = 7

logs = boto3.client("logs", region_name=REGION)
s3   = boto3.client("s3",   region_name=REGION)

start_ms = int((datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp() * 1000)

# ---- 1. Retrieve all events in the window (filter_log_events is paginated) ----
events, kwargs = [], {"logGroupName": LOG_GROUP, "startTime": start_ms}
while True:
    resp = logs.filter_log_events(**kwargs)
    events.extend(resp.get("events", []))
    token = resp.get("nextToken")
    if not token:
        break
    kwargs["nextToken"] = token
print(f"Retrieved {len(events)} raw events from {LOG_GROUP}")

# ---- 2. Classify each event by tag (error/info) and by date ----
grouped = defaultdict(list)          # key = (tag, dt) -> list of records
for ev in events:
    msg = ev.get("message", "")
    if "ERROR" in msg:
        tag = "error"
    elif "INFO" in msg:
        tag = "info"
    else:
        continue                    
    ts_ms = ev["timestamp"]
    when  = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    dt    = when.strftime("%Y-%m-%d")
    grouped[(tag, dt)].append({
        "timestamp":  ts_ms,
        "iso_time":   when.isoformat(),
        "level":      tag.upper(),
        "message":    msg.strip(),
        "log_stream": ev.get("logStreamName", ""),
    })

# ---- 3. Write one newline-JSON file per (tag, date) partition ----
written = 0
for (tag, dt), records in grouped.items():
    body = "\n".join(json.dumps(r) for r in records) + "\n"
    key  = f"{OUTPUT_PREFIX}/tag={tag}/dt={dt}/events.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=body.encode("utf-8"))
    written += 1
    print(f"wrote s3://{BUCKET}/{key}  ({len(records)} records)")

print(f"Done. {written} partition files written under s3://{BUCKET}/{OUTPUT_PREFIX}/")
