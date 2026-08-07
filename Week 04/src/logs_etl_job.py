"""
logs_etl_job.py  --  AWS GLUE PYTHON SHELL JOB (Python 3.9)

WHAT IT DOES
  1. Retrieves log events from a CloudWatch log group (via the Logs API).
  2. Classifies each event as ERROR or INFO by PARSING the log line's format.
  3. Writes them to S3 partitioned by tag and date:
        s3://<bucket>/logs/processed/tag=error/dt=2025-07-27/events.json
        s3://<bucket>/logs/processed/tag=info/dt=2025-07-27/events.json
     (newline-delimited JSON -- one event per line)

  A crawler then catalogs this output and Athena queries it by date.

Python Shell jobs come with boto3 pre-installed, so there are no
dependencies to add.
"""
import boto3, json, re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# ============ EDIT THESE THREE, THEN SAVE ============
REGION    = "eu-north-1"
LOG_GROUP = "/agrilink/app"
BUCKET    = "datalake-ha"   # no "s3://", no trailing "/"
# =====================================================

OUTPUT_PREFIX = "logs/processed"
LOOKBACK_DAYS = 7

# ---- Level parser -----------------------------------------------------------
# Instead of "does the word appear somewhere" (fragile) we PARSE the level from
# the position the log format puts it. Anchored at ^, so a keyword that appears
# later in the message body can never be captured as the level.
#
# It tolerates an optional leading timestamp and an optional [thread] token, so
# all of these classify correctly:
#     "ERROR Payment gateway timeout ..."                  -> ERROR
#     "INFO Retrying after previous ERROR for TXN0042"      -> INFO   (body ERROR ignored)
#     "2026-07-27T01:30:00Z ERROR Payment failed"          -> ERROR  (timestamp skipped)
#     "2026-07-27 12:00:00 [worker-3] INFO Order accepted" -> INFO   (ts + thread skipped)
#     "WARN Suppressed 3 ERROR events"                     -> WARN   (-> skipped, not error/info)
#
# Real-world note: this parses OUR known text layout. The gold standard is still
# structured logs (a real `level` field, read directly). For a different text
# format you would adjust this one pattern -- the rest of the pipeline is unchanged.
LEVEL_RE = re.compile(
    r"^\s*"
    r"(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\S*\s+)?"   # optional ISO-ish timestamp
    r"(?:\[[^\]]*\]\s+)?"                                   # optional [thread]/[component]
    r"(ERROR|WARN|INFO|DEBUG|TRACE|FATAL)\b",               # the level  (captured group 1)
    re.IGNORECASE,
)

def parse_level(message: str) -> str:
    """Return the log level (upper-case) parsed from the line, or '' if none."""
    m = LEVEL_RE.match(message or "")
    return m.group(1).upper() if m else ""

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


# 2026-07-27T01:30:00Z  [worker-3]  ERROR  Payment failed after retry
# └──── timestamp ────┘  └─thread─┘  └─┬─┘  └──────── body ────────┘
#       (skip)            (skip)     LEVEL   (ignored — even if it says "error")
#                                     ▲
#                         the parser reads THIS position


# ---- 2. Classify each event by tag (error/info) and by date ----
grouped = defaultdict(list)          # key = (tag, dt) -> list of records
for ev in events:
    msg   = ev.get("message", "")
    level = parse_level(msg)         # parsed from the line's format, not "contains"
    if level == "ERROR":
        tag = "error"
    elif level == "INFO":
        tag = "info"
    else:
        continue                     # WARN/DEBUG/unknown/no-match -> task wants only error+info
    ts_ms = ev["timestamp"]
    when  = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    dt    = when.strftime("%Y-%m-%d")
    grouped[(tag, dt)].append({
        "timestamp":  ts_ms,
        "iso_time":   when.isoformat(),
        "level":      level,
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