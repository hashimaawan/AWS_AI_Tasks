import json
import numpy as np
import matplotlib.pyplot as plt

with open("results_multi.json") as f:
    data = json.load(f)

models = [k for k, v in data.items() if v.get("status") == "ok"]


def agg(m):
    d = data[m]
    sa, ra, ta = d["structured"]["aggregate"], d["reasoning"]["aggregate"], d["tone"]["aggregate"]
    return {
        "struct_structure": sa["structure_frac"],
        "struct_objective": sa["objective_frac"],
        "struct_subjective": sa["subjective_frac"],
        "reason_math": ra["answer_correct_frac"],
        "tone_judge": ((ta["avg_judge_kid"] or 0) + (ta["avg_judge_eng"] or 0)) / 2,
        "cost": sa["avg_cost"] + ra["avg_cost"] + ta["avg_model_cost"],
        "latency": float(np.mean([sa["avg_latency"], ra["avg_latency"], ta["avg_model_latency"]])),
    }


A = {m: agg(m) for m in models}


def inv(vals):
    lo, hi = min(vals), max(vals)
    return [5 - 4 * (v - lo) / (hi - lo) if hi > lo else 5 for v in vals]


cost_score = dict(zip(models, inv([A[m]["cost"] for m in models])))
speed_score = dict(zip(models, inv([A[m]["latency"] for m in models])))

# ---- Chart 1: cost + latency ----
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
ax1.bar(models, [A[m]["cost"] for m in models]); ax1.set_yscale("log")
ax1.set_title("Avg cost per challenge (USD, log)"); ax1.set_ylabel("USD")
ax1.tick_params(axis="x", rotation=20)
ax2.bar(models, [A[m]["latency"] for m in models])
ax2.set_title("Avg latency (ms)"); ax2.set_ylabel("ms")
ax2.tick_params(axis="x", rotation=20)
fig.tight_layout(); fig.savefig("fig_cost_latency_multi.png", dpi=150)

# ---- Chart 2: radar — trustworthy axes only (objective content + pure math) ----
dims = ["Structured\n(objective)", "Reasoning\n(math)", "Tone\n(judge)", "Cost-eff", "Speed"]
angles = np.linspace(0, 2 * np.pi, len(dims), endpoint=False).tolist()
angles += angles[:1]
fig2, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw=dict(polar=True))
for m in models:
    vals = [A[m]["struct_objective"] * 5, A[m]["reason_math"] * 5, A[m]["tone_judge"],
            cost_score[m], speed_score[m]]
    vals += vals[:1]
    ax.plot(angles, vals, linewidth=2, label=m); ax.fill(angles, vals, alpha=0.08)
ax.set_xticks(angles[:-1]); ax.set_xticklabels(dims); ax.set_ylim(0, 5)
ax.set_title("Model comparison (trustworthy axes: objective content + math)")
ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
fig2.savefig("fig_quality_radar_multi.png", dpi=150, bbox_inches="tight")

# ---- Matrix: three-tier structured + math + tone ----
rows = ["| Model | Struct (structure) | Struct (objective) | Struct (subjective) | "
        "Reasoning (math) | Tone judge k/e | Avg cost | Avg latency |",
        "|---|---|---|---|---|---|---|---|"]
for m in models:
    sa = data[m]["structured"]["aggregate"]; ra = data[m]["reasoning"]["aggregate"]
    ta = data[m]["tone"]["aggregate"]
    rows.append(f"| {m} | {sa['structure_rate']} | {sa['objective_rate']} | {sa['subjective_rate']} | "
                f"{ra['answer_correct_rate']} | {ta['avg_judge_kid']}/{ta['avg_judge_eng']} | "
                f"${A[m]['cost']:.6f} | {A[m]['latency']:.0f} ms |")
open("comparison_matrix_multi.md", "w").write("\n".join(rows))

print("Wrote charts + comparison_matrix_multi.md")
for m in models:
    print(m, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in A[m].items()})