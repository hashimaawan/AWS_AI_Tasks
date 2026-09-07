"""
view_trace.py — turn saved OpenTelemetry spans into a CloudWatch-style HTML waterfall.

Usage:
    export CSBOT_TRACE_FILE=trace.jsonl
    python supervisor.py chat        # ask ONE question, then quit
    unset CSBOT_TRACE_FILE
    python view_trace.py trace.jsonl trace.html            # dark (default)
    python view_trace.py --light trace.jsonl trace-light.html   # light/report theme
"""
import json
import os
import sys

_THEME = os.environ.get("CSBOT_TRACE_THEME", "dark")


def parse_spans(path):
    text = open(path).read()
    dec = json.JSONDecoder()
    spans, i, n = [], 0, len(text)
    while i < n:
        while i < n and text[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
            spans.append(obj)
            i = end
        except json.JSONDecodeError:
            i += 1
    return spans


def ts(s):
    from datetime import datetime
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def classify(sp):
    name = sp.get("name", "")
    attr = sp.get("attributes", {})
    tools = attr.get("gen_ai.agent.tools", "")
    tok = attr.get("gen_ai.usage.total_tokens", "")
    if name.startswith("invoke_agent"):
        if "ask_order_agent" in tools and "ask_returns_agent" in tools:
            return ("SUPERVISOR", "#7c5cff", f"agent · {tok} tok")
        if "return" in tools.lower():
            return ("Returns sub-agent", "#2f9e6f", f"agent · {tok} tok")
        if "order" in tools.lower():
            return ("Order sub-agent", "#2f6bd8", f"agent · {tok} tok")
        return ("Sub-agent", "#2f9e6f", f"agent · {tok} tok")
    if name == "chat":
        return ("model call (Haiku)", "#1fa9c8", f"{tok} tok")
    if name.startswith("execute_tool"):
        tn = attr.get("gen_ai.tool.name", name.replace("execute_tool ", ""))
        if tn.startswith("ask_"):
            who = "Returns" if "return" in tn else "Order"
            return (f"route \u2192 {who}", "#e8871e", "routing decision")
        return (f"tool: {tn}", "#d64b5d", "Gateway \u2192 Lambda")
    if name.startswith("execute_event_loop_cycle"):
        return ("loop cycle", "#5a6a82", "")
    return (name, "#5a6a82", "")


DARK = """
  body{background:#0f1420;color:#e8edf6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:28px 30px 50px;}
  h1{font-size:20px;margin:0 0 4px;}
  .sub{color:#9aa7bd;font-size:13px;margin-bottom:20px;}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:18px;font-size:12px;color:#9aa7bd;}
  .legend span b{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle;}
  .row{display:flex;align-items:center;height:30px;border-bottom:1px solid #1c2434;}
  .lbl{width:320px;font-size:12.5px;color:#dfe7f5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle;}
  .meta{color:#7c8aa3;font-size:11px;margin-left:8px;}
  .track{position:relative;flex:1;height:20px;background:#141b29;border-radius:4px;overflow:hidden;}
  .bar{position:absolute;top:3px;height:14px;border-radius:3px;min-width:2px;opacity:.9;}
  .ms{position:absolute;right:4px;top:-1px;font-size:10px;color:#0f1420;font-weight:700;}
  .axis{color:#7c8aa3;font-size:11px;text-align:right;margin-top:6px;}
"""

LIGHT = """
  body{background:#ffffff;color:#1a2233;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:28px 30px 50px;}
  h1{font-size:20px;margin:0 0 4px;color:#111827;}
  .sub{color:#5b6b8c;font-size:13px;margin-bottom:20px;}
  .legend{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:18px;font-size:12px;color:#5b6b8c;}
  .legend span b{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle;}
  .row{display:flex;align-items:center;height:30px;border-bottom:1px solid #eef1f6;}
  .lbl{width:320px;font-size:12.5px;color:#26324a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle;}
  .meta{color:#8794a8;font-size:11px;margin-left:8px;}
  .track{position:relative;flex:1;height:20px;background:#f3f5f9;border-radius:4px;overflow:hidden;border:1px solid #eef1f6;}
  .bar{position:absolute;top:3px;height:14px;border-radius:3px;min-width:2px;opacity:.92;}
  .ms{position:absolute;right:4px;top:-1px;font-size:10px;color:#ffffff;font-weight:700;}
  .axis{color:#8794a8;font-size:11px;text-align:right;margin-top:6px;}
"""


def build_html(spans):
    rows = []
    for sp in spans:
        try:
            st, en = ts(sp["start_time"]), ts(sp["end_time"])
        except Exception:
            continue
        rows.append({"id": sp["context"]["span_id"], "parent": sp.get("parent_id"),
                     "start": st, "end": en, "dur": en - st, "sp": sp})
    if not rows:
        return "<html><body>No spans found.</body></html>"

    root_start = min(r["start"] for r in rows)
    total = max(r["end"] for r in rows) - root_start or 1.0
    by_id = {r["id"]: r for r in rows}

    def depth(r):
        d, p, seen = 0, r["parent"], set()
        while p in by_id and p not in seen:
            seen.add(p); d += 1; p = by_id[p]["parent"]
        return d
    for r in rows:
        r["depth"] = depth(r)
    rows.sort(key=lambda r: (r["start"], r["depth"]))

    bars = []
    for r in rows:
        label, color, meta = classify(r["sp"])
        left = (r["start"] - root_start) / total * 100
        width = max(r["dur"] / total * 100, 0.6)
        ms = int(r["dur"] * 1000)
        pad = 14 + r["depth"] * 22
        bars.append(f'<div class="row"><div class="lbl" style="padding-left:{pad}px">'
                    f'<span class="dot" style="background:{color}"></span>{label}'
                    f'<span class="meta">{meta}</span></div>'
                    f'<div class="track"><div class="bar" style="left:{left:.2f}%;'
                    f'width:{width:.2f}%;background:{color}"><span class="ms">{ms} ms</span>'
                    f'</div></div></div>')

    total_ms = int(total * 1000)
    css = LIGHT if _THEME == "light" else DARK
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>AuraBot — Trace Waterfall</title><style>{css}</style></head><body>
  <h1>AuraBot — Multi-Agent Trace (local OpenTelemetry)</h1>
  <div class="sub">One customer message routed by the supervisor. Total wall time: {total_ms} ms · same span data CloudWatch Transaction Search would render.</div>
  <div class="legend">
    <span><b style="background:#7c5cff"></b>Supervisor</span>
    <span><b style="background:#2f9e6f"></b>Sub-agent</span>
    <span><b style="background:#e8871e"></b>Routing decision</span>
    <span><b style="background:#d64b5d"></b>Tool (Gateway&#8594;Lambda)</span>
    <span><b style="background:#1fa9c8"></b>Model call</span>
    <span><b style="background:#5a6a82"></b>Internal</span>
  </div>
  {''.join(bars)}
  <div class="axis">0 ms &#8212;&#8212;&#8212;&#8212;&#8212;&#8212;&#8212;&#8212; {total_ms} ms</div>
</body></html>'''


if __name__ == "__main__":
    args = list(sys.argv[1:])
    if "--light" in args:
        _THEME = "light"; args.remove("--light")
    if "--dark" in args:
        _THEME = "dark"; args.remove("--dark")
    src = args[0] if len(args) > 0 else "trace.jsonl"
    out = args[1] if len(args) > 1 else "trace.html"
    spans = parse_spans(src)
    open(out, "w").write(build_html(spans))
    print(f"Parsed {len(spans)} spans ({_THEME} theme) -> {out}")
