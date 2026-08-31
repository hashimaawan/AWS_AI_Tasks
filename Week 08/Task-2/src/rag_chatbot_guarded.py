import json
import time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from kb_config import (AWS_REGION, KB_ID_FIXED, GEN_MODEL_ARN, TOP_K,
                       GUARDRAIL_ID, GUARDRAIL_VERSION)
from questions import QUESTIONS

_client = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION,
    config=Config(read_timeout=120, retries={"max_attempts": 2}),
)

# The exact blocked-message text you set in the console. If the answer equals
# this, the GUARDRAIL blocked it (vs. the model choosing to decline on its own).
BLOCKED_MSG = "I cannot answer this based on the provided documents."


def rag_guarded(question, kb_id=KB_ID_FIXED):
    start = time.perf_counter()
    resp = _client.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb_id,
                "modelArn": GEN_MODEL_ARN,
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": TOP_K}
                },
                # <<< THE ONLY NEW PIECE vs the unguarded version >>>
                "generationConfiguration": {
                    "guardrailConfiguration": {
                        "guardrailId": GUARDRAIL_ID,
                        "guardrailVersion": GUARDRAIL_VERSION,
                    }
                },
            },
        },
    )
    latency_ms = (time.perf_counter() - start) * 1000

    answer = resp["output"]["text"]
    citations = []
    for c in resp.get("citations", []):
        for ref in c.get("retrievedReferences", []):
            citations.append({
                "text": ref.get("content", {}).get("text", ""),
                "source": ref.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
            })

    # Did the guardrail actively block? Two signals:
    #  (a) the answer equals our distinctive blocked message, or
    #  (b) the response carries a guardrailAction = "INTERVENED".
    guardrail_action = resp.get("guardrailAction")  # "INTERVENED" | "NONE" | None
    blocked = (answer.strip() == BLOCKED_MSG) or (guardrail_action == "INTERVENED")

    return {"answer": answer, "citations": citations, "num_citations": len(citations),
            "guardrail_action": guardrail_action, "blocked_by_guardrail": blocked,
            "latency_ms": round(latency_ms, 1)}


def run_all():
    # Load unguarded results to compare side by side.
    with open("results_rag.json") as f:
        unguarded = json.load(f)

    results = {}
    for item in QUESTIONS:
        qid, question = item["id"], item["q"]
        print(f"\n=== {qid} ({'answerable' if item['answerable'] else 'unanswerable'}) ===")
        try:
            r = rag_guarded(question)
        except ClientError as e:
            print(f"  ERROR — {e.response['Error']['Code']}: {e.response['Error']['Message'][:120]}")
            results[qid] = {"status": "error", "error": e.response["Error"]["Code"]}
            continue

        expect = item.get("expect_contains", [])
        fact_present = all(e.lower() in r["answer"].lower() for e in expect) if expect else None

        results[qid] = {
            "status": "ok", "question": question, "answerable": item["answerable"],
            "answer": r["answer"], "fact_present": fact_present,
            "num_citations": r["num_citations"],
            "guardrail_action": r["guardrail_action"],
            "blocked_by_guardrail": r["blocked_by_guardrail"],
            "citations": r["citations"], "latency_ms": r["latency_ms"],
            "unguarded_answer": unguarded.get(qid, {}).get("answer", ""),
        }
        flag = "BLOCKED" if r["blocked_by_guardrail"] else "passed"
        print(f"  guardrail: {flag} (action={r['guardrail_action']})")
        print(f"  A: {r['answer'][:150]}{'...' if len(r['answer'])>150 else ''}")

    with open("results_rag_guarded.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nSaved results_rag_guarded.json")

    # ---- Summary: guarded behaviour + false-answer rate ----
    print("\n===== GUARDED RUN =====")
    print(f"{'id':<20}{'type':<13}{'guardrail':<10}{'fact/cites'}")
    hallucinations = 0
    for qid, r in results.items():
        if r.get("status") != "ok":
            print(f"  {qid:<20}ERROR"); continue
        typ = "answerable" if r["answerable"] else "UNANSWER"
        g = "BLOCKED" if r["blocked_by_guardrail"] else "-"
        extra = f"fact={r['fact_present']}" if r["answerable"] else f"cites={r['num_citations']}"
        # A hallucination = unanswerable, not blocked, and it actually gave an answer
        if (not r["answerable"] and not r["blocked_by_guardrail"]
                and r["answer"].strip() != BLOCKED_MSG
                and "cannot" not in r["answer"].lower()
                and "could not" not in r["answer"].lower()
                and "unable" not in r["answer"].lower()):
            hallucinations += 1
        print(f"  {qid:<20}{typ:<13}{g:<10}{extra}")
    n_unans = sum(1 for i in QUESTIONS if not i["answerable"])
    print(f"\nFalse-answer rate (guarded): {hallucinations}/{n_unans}")


if __name__ == "__main__":
    run_all()