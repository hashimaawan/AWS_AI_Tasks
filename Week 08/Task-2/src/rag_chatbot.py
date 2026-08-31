import json
import time
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from kb_config import AWS_REGION, KB_ID_FIXED, GEN_MODEL_ARN, TOP_K
from questions import QUESTIONS

# bedrock-agent-runtime is the client for KB operations (Retrieve / RetrieveAndGenerate).
# Note: this is a DIFFERENT client from bedrock-runtime (Converse) used in Task 1.
_client = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION,
    config=Config(read_timeout=120, retries={"max_attempts": 2}),
)


def retrieve_and_generate(question, kb_id=KB_ID_FIXED):
    """One RAG turn: retrieve top-K chunks from the KB + generate a grounded answer."""
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
            },
        },
    )
    latency_ms = (time.perf_counter() - start) * 1000

    answer = resp["output"]["text"]

    # Citations tell us WHICH retrieved chunks the model actually used to build
    # the answer. Each citation -> retrievedReferences -> the chunk text + source file.
    citations = []
    for c in resp.get("citations", []):
        for ref in c.get("retrievedReferences", []):
            citations.append({
                "text": ref.get("content", {}).get("text", ""),
                "source": ref.get("location", {}).get("s3Location", {}).get("uri", "unknown"),
                "score": ref.get("metadata", {}).get("score"),
            })

    return {
        "answer": answer,
        "citations": citations,
        "num_citations": len(citations),
        "latency_ms": round(latency_ms, 1),
        "session_id": resp.get("sessionId"),
    }


def run_all():
    results = {}
    for item in QUESTIONS:
        qid, question = item["id"], item["q"]
        print(f"\n=== {qid} ({'answerable' if item['answerable'] else 'unanswerable'}) ===")
        print(f"Q: {question}")
        try:
            r = retrieve_and_generate(question)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            print(f"  ERROR — {code}: {e.response['Error']['Message'][:120]}")
            results[qid] = {"status": "error", "error": code, "question": question,
                            "answerable": item["answerable"]}
            continue

        # Light auto-check: for answerable Qs, did the expected fact make it into the answer?
        expect = item.get("expect_contains", [])
        fact_present = all(e.lower() in r["answer"].lower() for e in expect) if expect else None
        # Which source docs were cited (short names, from the S3 filename)
        cited_docs = sorted({c["source"].split("/")[-1] for c in r["citations"]})

        results[qid] = {
            "status": "ok",
            "question": question,
            "answerable": item["answerable"],
            "expected_source": item.get("source_doc"),
            "answer": r["answer"],
            "fact_present": fact_present,
            "num_citations": r["num_citations"],
            "cited_docs": cited_docs,
            "citations": r["citations"],
            "latency_ms": r["latency_ms"],
        }

        print(f"A: {r['answer'][:200]}{'...' if len(r['answer']) > 200 else ''}")
        print(f"   citations: {r['num_citations']} from {cited_docs}")
        if expect:
            print(f"   expected fact present: {fact_present}")

    with open("results_rag.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("\nSaved results_rag.json")

    # Quick console summary
    print("\n===== SUMMARY =====")
    for qid, r in results.items():
        if r["status"] != "ok":
            print(f"  {qid:<20} ERROR"); continue
        tag = "answerable" if r["answerable"] else "UNANSWERABLE"
        extra = f"fact={r['fact_present']}" if r["answerable"] else f"cites={r['num_citations']}"
        print(f"  {qid:<20} {tag:<12} {extra}")


if __name__ == "__main__":
    run_all()