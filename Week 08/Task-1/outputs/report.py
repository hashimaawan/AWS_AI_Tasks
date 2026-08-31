import json
import numpy as np
import matplotlib.pyplot as plt

with open("results.json") as f:
    data = json.load(f)

models = [k for k, v in data.items() if v.get("status") == "ok"]

def calls(m):
    d = data[m]
    return [d["structured"], d["reasoning"], d["tone"]["kid"], d["tone"]["engineer"]]

totals = {}
for m in models:
    cs = calls(m)
    totals[m] = {
        "cost": sum(c["cost_usd"] for c in cs),
        "latency": sum(c["wall_latency_ms"] for c in cs) / len(cs),
        "tokens": sum(c["input_tokens"] + c["output_tokens"] for c in cs),
        "json_valid": data[m]["structured"]["valid_json"],
    }

# Objective scores (derived from the run), scaled 1..5. Lower cost/latency = better.
def inverse_scores(values):
    lo, hi = min(values), max(values)
    return [5 - 4 * (v - lo) / (hi - lo) if hi > lo else 5 for v in values]

costs = [totals[m]["cost"] for m in models]
lats  = [totals[m]["latency"] for m in models]
cost_score  = dict(zip(models, inverse_scores(costs)))
speed_score = dict(zip(models, inverse_scores(lats)))

# Subjective scores (my read of the transcripts — adjust to your own judgement).
QUALITY = {
    "claude-haiku-4.5": {"Structured": 4, "Reasoning": 5, "Tone": 5},
    "nova-lite":        {"Structured": 4, "Reasoning": 2, "Tone": 4},
    "mistral-large":    {"Structured": 5, "Reasoning": 4, "Tone": 4},
    "llama3-70b":       {"Structured": 2, "Reasoning": 5, "Tone": 3},
}

# ---- Chart 1: cost + latency ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
ax1.bar(models, costs); ax1.set_yscale("log")
ax1.set_title("Total cost per full run (USD, log scale)"); ax1.set_ylabel("USD")
ax1.tick_params(axis="x", rotation=20)
ax2.bar(models, lats)
ax2.set_title("Average latency per call (ms)"); ax2.set_ylabel("ms")
ax2.tick_params(axis="x", rotation=20)
fig.tight_layout(); fig.savefig("fig_cost_latency.png", dpi=150)

# ---- Chart 2: quality radar ----
dims = ["Structured", "Reasoning", "Tone", "Cost-eff", "Speed"]
angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
angles += angles[:1]
fig2, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
for m in models:
    vals = [QUALITY[m]["Structured"], QUALITY[m]["Reasoning"], QUALITY[m]["Tone"],
            cost_score[m], speed_score[m]]
    vals += vals[:1]
    ax.plot(angles, vals, linewidth=2, label=m)
    ax.fill(angles, vals, alpha=0.08)
ax.set_xticks(angles[:-1]); ax.set_xticklabels(dims); ax.set_ylim(0, 5)
ax.set_title("Model comparison across five dimensions")
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
fig2.savefig("fig_quality_radar.png", dpi=150, bbox_inches="tight")

# ---- Comparison matrix (markdown) ----
rows = ["| Model | JSON valid | Total cost (USD) | Avg latency (ms) | Total tokens |",
        "|---|---|---|---|---|"]
for m in models:
    t = totals[m]
    rows.append(f"| {m} | {t['json_valid']} | ${t['cost']:.6f} | {t['latency']:.0f} | {t['tokens']} |")
open("comparison_matrix.md", "w").write("\n".join(rows))

print("Wrote fig_cost_latency.png, fig_quality_radar.png, comparison_matrix.md")
for m in models:
    print(m, {k: round(v, 4) if isinstance(v, float) else v for k, v in totals[m].items()})