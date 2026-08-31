import json
import re
import textstat


def extract_json(text):
    cleaned = re.sub(r"```(json)?", "", text).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


# ---------- Challenge 1: structured (three tiers) ----------
def grade_structured(text, expected):
    parsed = extract_json(text)
    res = {"valid_json": parsed is not None, "has_all_keys": False,
           "name_ok": False, "facts_ok": False,
           "sentiment_ok": False, "urgency_ok": False,
           "structure_ok": False, "objective_ok": False, "subjective_ok": False,
           "passed": False, "parsed": parsed}
    if not parsed:
        return res
    required = ["customer_name", "issue", "sentiment", "urgency"]
    res["has_all_keys"] = all(k in parsed for k in required)
    res["name_ok"] = expected["name_contains"].lower() in str(parsed.get("customer_name", "")).lower()
    issue = str(parsed.get("issue", "")).lower()
    res["facts_ok"] = all(f.lower() in issue for f in expected.get("issue_must_include", []))
    res["sentiment_ok"] = str(parsed.get("sentiment", "")).lower() == expected["sentiment"]
    res["urgency_ok"] = str(parsed.get("urgency", "")).lower() == expected["urgency"]

    # Tier 1 - STRUCTURE: usable JSON with the right shape (table stakes)
    res["structure_ok"] = res["valid_json"] and res["has_all_keys"]

    # Tier 2 - OBJECTIVE value: deterministic facts (name + required strings). Trustworthy.
    res["objective_ok"] = res["structure_ok"] and res["name_ok"] and res["facts_ok"]

    # Tier 3 - SUBJECTIVE value: judgement fields vs our contestable labels. Low-trust.
    res["subjective_ok"] = res["sentiment_ok"] and res["urgency_ok"]
    
    # Overall (kept for continuity; report the three tiers separately)
    res["passed"] = res["objective_ok"] and res["subjective_ok"]
    return res


# ---------- Challenge 2: reasoning ----------
def _numbers(text):
    out = []
    for r in re.findall(r"[-+]?\d[\d,]*\.?\d*", text):
        try:
            out.append(float(r.replace(",", "")))
        except ValueError:
            pass
    return out


def grade_reasoning(text, expected):
    nums = _numbers(text)
    figs = {}
    for target, tol in expected["figures"]:
        closest = min(nums, key=lambda n: abs(n - target)) if nums else None
        figs[str(target)] = {"hit": closest is not None and abs(closest - target) <= tol,
                             "closest": closest}
    low = text.lower()
    rec_ok = any(k.lower() in low for k in expected["recommendation_keywords"])
    answer_ok = all(v["hit"] for v in figs.values())
    return {"figures": figs, "recommendation_ok": rec_ok,
            "answer_correct": answer_ok, "passed": answer_ok and rec_ok}


# ---------- Challenge 3: tone ----------
JARGON = ["capex", "opex", "virtualiz", "statelessness", "cap theorem", "latency",
          "throughput", "idempotent", "orchestrat", "kubernetes", "container",
          "multi-tenant", "hypervisor", "microservice", "endpoint", "payload",
          "protocol", "abstraction", "neural", "hyperparameter", "inference",
          "overfitting", "gradient", "scalab"]


def _jargon(text):
    low = text.lower()
    return sum(low.count(j) for j in JARGON)


def grade_tone_readability(kid_text, eng_text):
    kid_g = textstat.flesch_kincaid_grade(kid_text)
    eng_g = textstat.flesch_kincaid_grade(eng_text)
    return {"kid_grade": round(kid_g, 1), "eng_grade": round(eng_g, 1),
            "grade_spread": round(eng_g - kid_g, 1),
            "kid_jargon": _jargon(kid_text), "eng_jargon": _jargon(eng_text),
            "passed": (eng_g > kid_g) and (_jargon(kid_text) <= 1)}


def judge_tone(converse_fn, judge_model, concept, kid_text, eng_text):
    prompt = f"""You are evaluating two explanations of "{concept}".
Rate each from 1 to 5 on how well it fits its TARGET audience.
- KID target: a 10-year-old. High = simple words, relatable analogy, no jargon.
- ENGINEER target: a senior software engineer. High = precise, technical,
  real trade-offs, assumes expertise.
Return ONLY JSON, no prose:
{{"kid_score": <1-5>, "eng_score": <1-5>, "reason": "<one short sentence>"}}

KID VERSION:
{kid_text}

ENGINEER VERSION:
{eng_text}"""
    r = converse_fn(judge_model, "You are a strict evaluation judge. Output only JSON.",
                    prompt, temperature=0.0)
    return {"parsed": extract_json(r["text"]), "raw": r["text"],
            "judge_cost_usd": r["cost_usd"], "judge_latency_ms": r["wall_latency_ms"]}