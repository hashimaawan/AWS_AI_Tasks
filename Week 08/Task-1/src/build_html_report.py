import json, html, base64, os
from statistics import mean

RESULTS, OUT = "results_multi.json", "report.html"
PNGS = ["fig_cost_latency_multi.png", "fig_quality_radar_multi.png"]

with open(RESULTS) as f:
    data = json.load(f)
models = [k for k, v in data.items() if v.get("status") == "ok"]

def esc(x): return html.escape(str(x))
def badge(ok):
    if ok is None: return '<span class="b b-na">n/a</span>'
    return '<span class="b b-ok">PASS</span>' if ok else '<span class="b b-no">FAIL</span>'
def bar(val, mx, unit=""):
    pct = 0 if mx == 0 else min(100, val / mx * 100)
    return f'<div class="bar"><div class="fill" style="width:{pct:.1f}%"></div><span>{val:.4g}{unit}</span></div>'

def sids(m, challenge):
    return [k for k in data[m][challenge] if k != "aggregate"]

def model_calls(m):
    d, out = data[m], []
    for sid in sids(m, "structured"):
        c = d["structured"][sid]; out.append((c["input_tokens"], c["output_tokens"], c["cost_usd"]))
    for sid in sids(m, "reasoning"):
        c = d["reasoning"][sid]; out.append((c["input_tokens"], c["output_tokens"], c["cost_usd"]))
    for sid in sids(m, "tone"):
        c = d["tone"][sid]
        for part in ("kid", "engineer"):
            p = c[part]; out.append((p["input_tokens"], p["output_tokens"], p["cost_usd"]))
    return out

def totals(m):
    calls = model_calls(m)
    ti = sum(c[0] for c in calls); to = sum(c[1] for c in calls); tc = sum(c[2] for c in calls)
    jc = data[m]["tone"]["aggregate"].get("judge_eval_cost", 0)
    return ti, to, tc, jc

T = {m: totals(m) for m in models}
max_tok = max((T[m][0] + T[m][1]) for m in models)
max_cost = max(T[m][2] for m in models)

css = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1a2733;line-height:1.5}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
header{background:linear-gradient(135deg,#1b3a5b,#2c6a9e);color:#fff;padding:28px 24px;border-radius:12px;margin-bottom:24px}
header h1{margin:0 0 6px;font-size:24px} header p{margin:0;opacity:.85;font-size:14px}
h2{font-size:19px;margin:32px 0 12px;border-bottom:2px solid #e2e8ee;padding-bottom:6px}
h3{font-size:15px;margin:20px 0 8px;color:#2c6a9e}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);font-size:13px}
th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #eef2f6}
th{background:#eef3f8;font-weight:600} tr:last-child td{border-bottom:0}
.b{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}
.b-ok{background:#d7f0dd;color:#1a7a37} .b-no{background:#fbdcdc;color:#b02a2a} .b-na{background:#e6e8ea;color:#667}
.bar{position:relative;background:#eef2f6;border-radius:4px;height:20px;min-width:120px}
.bar .fill{background:#2c6a9e;height:100%;border-radius:4px}
.bar span{position:absolute;left:8px;top:2px;font-size:11px;color:#1a2733}
details{background:#fff;border:1px solid #e2e8ee;border-radius:6px;margin:6px 0;padding:6px 10px}
summary{cursor:pointer;font-size:13px;font-weight:600;color:#2c6a9e}
pre{white-space:pre-wrap;background:#f7f9fb;padding:10px;border-radius:6px;font-size:12px;overflow-x:auto;margin:8px 0 0}
.meta{font-size:12px;color:#667;margin:4px 0}
img{max-width:100%;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);margin:8px 0}
.card{background:#fff;border-radius:8px;padding:14px 16px;margin:10px 0;box-shadow:0 1px 3px rgba(0,0,0,.08)}
"""

H = [f"<!doctype html><meta charset='utf-8'><title>Bedrock Model Comparison</title><style>{css}</style>"]
H.append("<div class='wrap'>")
n_s = len(sids(models[0], "structured")); n_r = len(sids(models[0], "reasoning")); n_t = len(sids(models[0], "tone"))
H.append(f"<header><h1>Bedrock Multi-Model Comparison — Task 1</h1>"
         f"<p>{len(models)} models · {n_s} structured · {n_r} reasoning · {n_t} tone scenarios · "
         f"auto-graded (structure / objective / subjective + LLM-judge)</p></header>")

# ---- Executive summary ----
H.append("<h2>Executive summary</h2><table>")
H.append("<tr><th>Model</th><th>Struct: structure</th><th>Struct: objective</th><th>Struct: subjective</th>"
         "<th>Reasoning (math)</th><th>Tone judge k/e</th><th>Avg cost</th><th>Avg latency</th></tr>")
for m in models:
    sa = data[m]["structured"]["aggregate"]; ra = data[m]["reasoning"]["aggregate"]; ta = data[m]["tone"]["aggregate"]
    avg_cost = sa["avg_cost"] + ra["avg_cost"] + ta["avg_model_cost"]
    avg_lat = mean([sa["avg_latency"], ra["avg_latency"], ta["avg_model_latency"]])
    H.append(f"<tr><td><b>{esc(m)}</b></td><td>{sa['structure_rate']}</td><td>{sa['objective_rate']}</td>"
             f"<td>{sa['subjective_rate']}</td><td>{ra['answer_correct_rate']}</td>"
             f"<td>{ta['avg_judge_kid']}/{ta['avg_judge_eng']}</td>"
             f"<td>${avg_cost:.6f}</td><td>{avg_lat:.0f} ms</td></tr>")
H.append("</table>")
H.append("<p class='meta'>Structure = valid JSON + keys (table stakes). Objective = deterministic facts "
         "(name, order numbers) — trustworthy. Subjective = sentiment/urgency vs. our labels — contestable.</p>")

# ---- Token & cost breakdown ----
H.append("<h2>Token &amp; cost breakdown</h2><table>")
H.append("<tr><th>Model</th><th>Input tok</th><th>Output tok</th><th>Total tokens</th>"
         "<th>Model cost</th><th>Judge-eval cost</th></tr>")
for m in models:
    ti, to, tc, jc = T[m]
    H.append(f"<tr><td><b>{esc(m)}</b></td><td>{ti}</td><td>{to}</td>"
             f"<td>{bar(ti+to, max_tok)}</td><td>{bar(tc, max_cost, '$')}</td><td>${jc:.6f}</td></tr>")
H.append("</table>")
H.append("<p class='meta'>Judge-eval cost = the extra LLM-as-judge passes. Evaluation is not free — "
         "a real production consideration.</p>")

# ---- Charts ----
H.append("<h2>Charts</h2>")
for png in PNGS:
    if os.path.exists(png):
        b64 = base64.b64encode(open(png, "rb").read()).decode()
        H.append(f"<img src='data:image/png;base64,{b64}' alt='{png}'>")
    else:
        H.append(f"<p class='meta'>[{png} not found — run build_report.py first]</p>")

# ---- Structured drill-down (three tiers + all sub-checks) ----
H.append("<h2>Structured output — per scenario</h2>")
for sid in sids(models[0], "structured"):
    H.append(f"<div class='card'><h3>{esc(sid)}</h3><table>")
    H.append("<tr><th>Model</th><th>Structure</th><th>Objective</th><th>Subjective</th>"
             "<th>valid/keys</th><th>name/facts</th><th>sent/urg</th>"
             "<th>In/Out tok</th><th>Latency</th><th>Cost</th><th>Output</th></tr>")
    for m in models:
        c = data[m]["structured"][sid]; g = c["grade"]
        det = f"<details><summary>view</summary><pre>{esc(c['text'])}</pre></details>"
        H.append(f"<tr><td>{esc(m)}</td><td>{badge(g['structure_ok'])}</td><td>{badge(g['objective_ok'])}</td>"
                 f"<td>{badge(g['subjective_ok'])}</td>"
                 f"<td>{badge(g['valid_json'])}/{badge(g['has_all_keys'])}</td>"
                 f"<td>{badge(g['name_ok'])}/{badge(g['facts_ok'])}</td>"
                 f"<td>{badge(g['sentiment_ok'])}/{badge(g['urgency_ok'])}</td>"
                 f"<td>{c['input_tokens']}/{c['output_tokens']}</td><td>{c['wall_latency_ms']:.0f} ms</td>"
                 f"<td>${c['cost_usd']:.6f}</td><td>{det}</td></tr>")
    H.append("</table></div>")

# ---- Reasoning drill-down ----
H.append("<h2>Reasoning — per scenario</h2>")
for sid in sids(models[0], "reasoning"):
    H.append(f"<div class='card'><h3>{esc(sid)}</h3><table>")
    H.append("<tr><th>Model</th><th>Math</th><th>Recommendation</th><th>Passed</th>"
             "<th>In/Out tok</th><th>Latency</th><th>Cost</th><th>Working</th></tr>")
    for m in models:
        c = data[m]["reasoning"][sid]; g = c["grade"]
        det = f"<details><summary>view</summary><pre>{esc(c['text'])}</pre></details>"
        H.append(f"<tr><td>{esc(m)}</td><td>{badge(g['answer_correct'])}</td><td>{badge(g['recommendation_ok'])}</td>"
                 f"<td>{badge(g['passed'])}</td><td>{c['input_tokens']}/{c['output_tokens']}</td>"
                 f"<td>{c['wall_latency_ms']:.0f} ms</td><td>${c['cost_usd']:.6f}</td><td>{det}</td></tr>")
    H.append("</table></div>")

# ---- Tone drill-down ----
H.append("<h2>Tone — per scenario (both signals)</h2>")
for sid in sids(models[0], "tone"):
    H.append(f"<div class='card'><h3>{esc(sid)}</h3><table>")
    H.append("<tr><th>Model</th><th>Grade spread (L1)</th><th>Kid/Eng jargon</th>"
             "<th>Judge k/e (L2)</th><th>In/Out tok (kid+eng)</th><th>Outputs</th></tr>")
    for m in models:
        c = data[m]["tone"][sid]; r = c["readability"]; jp = c["judge"]["parsed"] or {}
        tin = c["kid"]["input_tokens"] + c["engineer"]["input_tokens"]
        tout = c["kid"]["output_tokens"] + c["engineer"]["output_tokens"]
        det = (f"<details><summary>view kid + engineer</summary>"
               f"<pre><b>KID:</b>\n{esc(c['kid']['text'])}\n\n<b>ENGINEER:</b>\n{esc(c['engineer']['text'])}</pre></details>")
        H.append(f"<tr><td>{esc(m)}</td><td>{r['grade_spread']}</td><td>{r['kid_jargon']}/{r['eng_jargon']}</td>"
                 f"<td>{jp.get('kid_score')}/{jp.get('eng_score')}</td><td>{tin}/{tout}</td><td>{det}</td></tr>")
    H.append("</table></div>")

H.append("</div>")
open(OUT, "w", encoding="utf-8").write("".join(H))
print(f"Wrote {OUT} — open it in a browser.")