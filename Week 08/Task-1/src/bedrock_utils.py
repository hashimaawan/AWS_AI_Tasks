import time
import boto3
from botocore.config import Config
from models_config import AWS_REGION, PRICING

# One shared client; longer read timeout so slower models don't false-fail.
_client = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    config=Config(read_timeout=120, retries={"max_attempts": 2}),
)

def converse(model, system_text, user_text,
             temperature=0.2, max_tokens=1024, tool_config=None):
    """One Converse call -> text plus captured metrics (latency, tokens, cost)."""
    kwargs = {
        "modelId": model["model_id"],
        "messages": [{"role": "user", "content": [{"text": user_text}]}],
        "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
    }
    if system_text:
        kwargs["system"] = [{"text": system_text}]   # top-level system prompt
    if tool_config:
        kwargs["toolConfig"] = tool_config

    start = time.perf_counter()
    resp = _client.converse(**kwargs)
    wall_ms = (time.perf_counter() - start) * 1000

    blocks = resp["output"]["message"]["content"]
    text = "".join(b.get("text", "") for b in blocks).strip()

    usage = resp["usage"]
    in_tok, out_tok = usage["inputTokens"], usage["outputTokens"]
    p_in, p_out = PRICING[model["key"]]
    cost = (in_tok / 1000) * p_in + (out_tok / 1000) * p_out

    return {
        "text": text,
        "raw_content": blocks,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost_usd": cost,
        "wall_latency_ms": round(wall_ms, 1),
        "server_latency_ms": resp.get("metrics", {}).get("latencyMs"),
        "stop_reason": resp.get("stopReason"),
    }