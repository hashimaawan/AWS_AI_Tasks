import json
import time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from kb_config import AWS_REGION
from questions import QUESTIONS

# Plain Converse (NO knowledge base) — this is the "direct LLM" baseline.
# Same client family as Task 1 (bedrock-runtime), NOT the agent-runtime KB client.
_client = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    config=Config(read_timeout=120, retries={"max_attempts": 2}),
)

# Same generation model as RAG uses, so the ONLY variable is "docs vs no docs".
DIRECT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# A fair system prompt: tell it to admit ignorance, so we don't stack the deck
# by "tricking" it into hallucinating. We want an honest direct-LLM baseline.
SYSTEM = ("You are a helpful assistant. Answer from your own knowledge. "
          "If you do not know a specific fact, say you don't know rather than guessing.")


def direct_answer(question):
    start = time.perf_counter()
    resp = _client.converse(
        modelId=DIRECT_MODEL_ID,
        system=[{"text": SYSTEM}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"temperature": 0.0, "maxTokens": 512},
    )
    latency_ms = (time.perf_counter() - start) * 1000
    text = resp["output"]["message"]["content"][0]["text"].strip()
    usage = resp["usage"]
    return {"answer": text, "latency_ms": round(latency_ms, 1),
            "input_tokens": usage["inputTokens"], "output_tokens": usage["outputTokens"]}


def classify(answer, item):
    """Bucket the direct answer so the comparison is measurable, not vibes."""
    low = answer.lower()
    refused = any(p in low for p in [
        "i don't know", "i do not know", "don't have", "do not have",
        "cannot find", "can't find", "unable to", "no information",
        "not able to", "i'm not sure", "not aware"])
    if item["answerable"]:
        expect = item.get("expect_contains", [])
        got_fact = all(e.lower() in low for e in expect) if expect else None
        if got_fact:
            return "CORRECT"          # direct LLM knew it (expected only for public facts)
        return "REFUSED" if refused else "WRONG/GUESS"  # didn't know a private fact
    else:
        # For unanswerable Qs, refusing is the CORRECT behavior.
        return "REFUSED (good)" if refused else "HALLUCINATED"


def run():
    # Load the RAG results so we can put them side by side.
    with open("results_rag.json") as f:
        rag = json.load(f)

    rows = []
    for item in QUESTIONS:
        qid = item["id"]
        print(f"\n=== {qid} ===\nQ: {item['q']}")
        try:
            d = direct_answer(item["q"])
        except ClientError as e:
            print(f"  ERROR — {e.response['Error']['Code']}")
            continue
        verdict = classify(d["answer"], item)

        rag_entry = rag.get(qid, {})
        rag_answer = rag_entry.get("answer", "(no RAG answer)")
        rag_fact = rag_entry.get("fact_present")

        rows.append({
            "id": qid, "question": item["q"], "answerable": item["answerable"],
            "expected_source": item.get("source_doc"),
            "direct_answer": d["answer"], "direct_verdict": verdict,
            "direct_latency_ms": d["latency_ms"],
            "rag_answer": rag_answer, "rag_fact_present": rag_fact,
            "rag_cited_docs": rag_entry.get("cited_docs", []),
        })

        print(f"  DIRECT [{verdict}]: {d['answer'][:120]}{'...' if len(d['answer'])>120 else ''}")
        print(f"  RAG   : {str(rag_answer)[:120]}{'...' if len(str(rag_answer))>120 else ''}")

    with open("results_direct_vs_rag.json", "w") as f:
        json.dump(rows, f, indent=2, default=str)
    print("\nSaved results_direct_vs_rag.json")

    # ---- The money summary: where did RAG beat direct? ----
    print("\n===== DIRECT vs RAG =====")
    print(f"{'id':<20}{'direct':<18}{'rag':<12}{'RAG advantage?'}")
    rag_wins = 0
    for r in rows:
        if r["answerable"]:
            rag_ok = r["rag_fact_present"] is True
            direct_ok = r["direct_verdict"] == "CORRECT"
            advantage = "RAG WON" if (rag_ok and not direct_ok) else ("tie" if rag_ok == direct_ok else "direct won")
            rag_state = "fact ✓" if rag_ok else "miss"
        else:
            direct_bad = r["direct_verdict"] == "HALLUCINATED"
            advantage = "RAG WON" if direct_bad else "tie (both declined)"
            rag_state = "declined"
        if advantage == "RAG WON":
            rag_wins += 1
        print(f"  {r['id']:<20}{r['direct_verdict']:<18}{rag_state:<12}{advantage}")
    print(f"\nRAG outperformed direct on {rag_wins} of {len(rows)} questions.")


if __name__ == "__main__":
    run()