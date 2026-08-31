import sys
import json
from statistics import mean
from botocore.exceptions import ClientError

from models_config import MODELS
from bedrock_utils import converse
from scenarios import (STRUCTURED_INSTRUCTIONS, STRUCTURED_SCENARIOS,
                       REASONING_SCENARIOS, TONE_SCENARIOS)
from grading import (grade_structured, grade_reasoning,
                     grade_tone_readability, judge_tone)

# Fixed judge for tone Level 2. Disclosed bias: it is also a contestant, so its
# scores on its own tone outputs carry self-preference (flagged in the README).
JUDGE = next(m for m in MODELS if m["key"] == "claude-haiku-4.5")


def do_structured(model, scenarios):
    per = {}
    for s in scenarios:
        r = converse(model, "You are a precise data-extraction service.",
                     f"{STRUCTURED_INSTRUCTIONS}\n\nEMAIL:\n{s['email']}", temperature=0.0)
        r["grade"] = grade_structured(r["text"], s["expected"])
        per[s["id"]] = r
    ids = [s["id"] for s in scenarios]; n = len(ids)
    struct = [per[i]["grade"]["structure_ok"] for i in ids]
    obj = [per[i]["grade"]["objective_ok"] for i in ids]
    subj = [per[i]["grade"]["subjective_ok"] for i in ids]
    per["aggregate"] = {
        "structure_rate": f"{sum(struct)}/{n}", "structure_frac": sum(struct)/n,
        "objective_rate": f"{sum(obj)}/{n}", "objective_frac": sum(obj)/n,
        "subjective_rate": f"{sum(subj)}/{n}", "subjective_frac": sum(subj)/n,
        "avg_cost": mean(per[i]["cost_usd"] for i in ids),
        "avg_latency": mean(per[i]["wall_latency_ms"] for i in ids)}
    return per


def do_reasoning(model, scenarios):
    per = {}
    for s in scenarios:
        r = converse(model, "You are a sharp business analyst. Show your working.",
                     s["problem"], temperature=0.2)
        r["grade"] = grade_reasoning(r["text"], s["expected"])
        per[s["id"]] = r
    ids = [s["id"] for s in scenarios]; n = len(ids)
    passes = [per[i]["grade"]["passed"] for i in ids]
    ans = [per[i]["grade"]["answer_correct"] for i in ids]
    per["aggregate"] = {
        "pass_rate": f"{sum(passes)}/{n}", "pass_frac": sum(passes)/n,
        "answer_correct_rate": f"{sum(ans)}/{n}", "answer_correct_frac": sum(ans)/n,
        "avg_cost": mean(per[i]["cost_usd"] for i in ids),
        "avg_latency": mean(per[i]["wall_latency_ms"] for i in ids)}
    return per


def do_tone(model, scenarios):
    per = {}
    for s in scenarios:
        kid = converse(model, "Explain simply, warmly, no jargon.",
                       f"Explain {s['concept']} to a 10-year-old in 3-4 sentences.", temperature=0.4)
        eng = converse(model, "Be precise and technical; assume deep expertise.",
                       f"Explain {s['concept']} to a senior software engineer, "
                       f"naming the key trade-offs.", temperature=0.4)
        per[s["id"]] = {"kid": kid, "engineer": eng,
                        "readability": grade_tone_readability(kid["text"], eng["text"]),
                        "judge": judge_tone(converse, JUDGE, s["concept"], kid["text"], eng["text"])}
    ids = [s["id"] for s in scenarios]; n = len(ids)
    def jscore(sid, key):
        p = per[sid]["judge"]["parsed"]
        return p.get(key) if isinstance(p, dict) and isinstance(p.get(key), (int, float)) else None
    spreads = [per[i]["readability"]["grade_spread"] for i in ids]
    kid_sc = [v for v in (jscore(i, "kid_score") for i in ids) if v is not None]
    eng_sc = [v for v in (jscore(i, "eng_score") for i in ids) if v is not None]
    per["aggregate"] = {
        "avg_grade_spread": round(mean(spreads), 1),
        "avg_judge_kid": round(mean(kid_sc), 2) if kid_sc else None,
        "avg_judge_eng": round(mean(eng_sc), 2) if eng_sc else None,
        "avg_model_cost": mean(per[i]["kid"]["cost_usd"] + per[i]["engineer"]["cost_usd"] for i in ids),
        "avg_model_latency": mean((per[i]["kid"]["wall_latency_ms"] + per[i]["engineer"]["wall_latency_ms"])/2 for i in ids),
        "judge_eval_cost": sum(per[i]["judge"]["judge_cost_usd"] for i in ids)}
    return per


def run_all(limit=None):
    s_scn = STRUCTURED_SCENARIOS[:limit] if limit else STRUCTURED_SCENARIOS
    r_scn = REASONING_SCENARIOS[:limit] if limit else REASONING_SCENARIOS
    t_scn = TONE_SCENARIOS[:limit] if limit else TONE_SCENARIOS
    print(f"Running {len(s_scn)} structured, {len(r_scn)} reasoning, "
          f"{len(t_scn)} tone scenario(s) per model.\n")

    results = {}
    for m in MODELS:
        key = m["key"]
        print(f"\n=== {key} ({m['provider']}) ===")
        try:
            structured = do_structured(m, s_scn)
            reasoning = do_reasoning(m, r_scn)
            tone = do_tone(m, t_scn)
        except ClientError as e:
            print(f"  SKIPPED — {e.response['Error']['Code']}")
            results[key] = {"status": "unavailable", "error": e.response["Error"]["Code"]}
            continue
        results[key] = {"status": "ok", "structured": structured,
                        "reasoning": reasoning, "tone": tone}

        # ---- PER-SCENARIO detail FIRST (the truth) ----
        print("  Structured (per scenario):")
        for s in s_scn:
            g = structured[s["id"]]["grade"]
            print(f"    - {s['id']:<22} structure={g['structure_ok']} "
                  f"objective={g['objective_ok']} subjective={g['subjective_ok']}")
        print("  Reasoning (per scenario):")
        for s in r_scn:
            g = reasoning[s["id"]]["grade"]
            print(f"    - {s['id']:<22} math={g['answer_correct']} "
                  f"recommendation={g['recommendation_ok']} passed={g['passed']}")
        print("  Tone (per scenario):")
        for s in t_scn:
            rd = tone[s["id"]]["readability"]; jp = tone[s["id"]]["judge"]["parsed"] or {}
            print(f"    - {s['id']:<22} grade_spread={rd['grade_spread']} "
                  f"judge_kid={jp.get('kid_score')} judge_eng={jp.get('eng_score')}")

        # ---- AGGREGATE SECOND (headline, never alone) ----
        sa, ra, ta = structured["aggregate"], reasoning["aggregate"], tone["aggregate"]
        print("  AGGREGATE:")
        print(f"    structured  structure {sa['structure_rate']} | "
              f"objective {sa['objective_rate']} | subjective {sa['subjective_rate']}")
        print(f"    reasoning   pass {ra['pass_rate']} (pure math {ra['answer_correct_rate']})")
        print(f"    tone        spread {ta['avg_grade_spread']} | "
              f"judge k/e {ta['avg_judge_kid']}/{ta['avg_judge_eng']}")

    with open("results_multi.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nSaved results_multi.json")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_all(limit)