"""
seed_logs.py  --  RUN THIS IN AWS CLOUDSHELL (region: eu-north-1)

Creates a CloudWatch log group and writes sample INFO/ERROR log events
spread across the last 3 days, so the Glue job in Stage 3 has something
real to retrieve and the Athena "query by date" step is meaningful.

Why CloudShell: it already has boto3 installed and your credentials, so
there is nothing to set up. Just paste and run.

NOTE: one INFO template deliberately contains the word "ERROR" in its body
("INFO Retrying after previous ERROR ...") to exercise the tricky case where a
message holds BOTH keywords. The job classifies by PARSING the level at the
front of the line, so this is correctly tagged INFO -- proving the classifier
is not fooled by a keyword in the body.
"""
import boto3, random
from datetime import datetime, timezone, timedelta

REGION    = "eu-north-1"
LOG_GROUP = "/agrilink/app"

logs = boto3.client("logs", region_name=REGION)

# Create the log group once (ignore if it already exists)
try:
    logs.create_log_group(logGroupName=LOG_GROUP)
    print(f"Created log group {LOG_GROUP}")
except logs.exceptions.ResourceAlreadyExistsException:
    print(f"Log group {LOG_GROUP} already exists, reusing it")

INFO_MSGS = [
    "INFO Order accepted for {tx}",
    "INFO Transport matched for {tx} via pooled_van",
    "INFO Payment escrow held for {tx}",
    "INFO Delivery confirmed for {tx}",
    "INFO Retrying after previous ERROR for {tx}",   # <-- body contains "ERROR"
]
ERROR_MSGS = [
    "ERROR Payment gateway timeout for {tx}",
    "ERROR No transport bid received for {tx}",
    "ERROR Escrow release failed for {tx}",
    "ERROR Invalid crop price for {tx}",
]

now = datetime.now(timezone.utc)
run_id = now.strftime("%H%M%S")
total = 0

# One PutLogEvents call PER DAY. CloudWatch rejects a single batch whose events
# span more than 24 hours, so we must not mix days in one call.
for day_offset in (2, 1, 0):
    day = now - timedelta(days=day_offset)
    stream = f"seed-{day.strftime('%Y%m%d')}-{run_id}"
    logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=stream)

    events = []
    for _ in range(12):                       # 12 events per day
        tx = f"TXN{random.randint(1, 60):04d}"
        is_error = random.random() < 0.35      # ~35% errors
        template = random.choice(ERROR_MSGS if is_error else INFO_MSGS)
        ts = day.replace(hour=random.randint(0, 23),
                         minute=random.randint(0, 59),
                         second=random.randint(0, 59), microsecond=0)
        events.append({"timestamp": int(ts.timestamp() * 1000),
                       "message": template.format(tx=tx)})

    events.sort(key=lambda e: e["timestamp"])  # PutLogEvents requires ascending order
    logs.put_log_events(logGroupName=LOG_GROUP, logStreamName=stream, logEvents=events)
    total += len(events)
    print(f"  wrote {len(events)} events for {day.strftime('%Y-%m-%d')} to stream {stream}")

print(f"\nDone. Seeded {total} events across 3 days into {LOG_GROUP}.")