import json
import boto3
from botocore.config import Config
from kb_config import AWS_REGION, KB_ID_FIXED, KB_ID_HIERARCHICAL

_client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION,
                       config=Config(read_timeout=120))

# Long-doc questions — where chunk-content differences show best.
QUERIES = [
    "What is rightsizing in cost optimization?",
    "How should supply be matched to demand to optimize cost?",
    "What are the phases of the Cloud Financial Management framework?",
]

def top_chunk(kb_id, q):
    """Return the single top retrieved chunk's text + length."""
    resp = _client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": q},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 1}},
    )
    results = resp.get("retrievalResults", [])
    if not results:
        return {"text": "(no result)", "chars": 0, "words": 0}
    text = results[0].get("content", {}).get("text", "")
    return {"text": text, "chars": len(text), "words": len(text.split())}

def run():
    out = []
    for q in QUERIES:
        fixed = top_chunk(KB_ID_FIXED, q)
        hier = top_chunk(KB_ID_HIERARCHICAL, q)
        out.append({"query": q, "fixed": fixed, "hierarchical": hier})

        print("\n" + "=" * 90)
        print(f"QUERY: {q}")
        print(f"\n--- FIXED-SIZE  ({fixed['words']} words / {fixed['chars']} chars) ---")
        print(fixed["text"])
        print(f"\n--- HIERARCHICAL  ({hier['words']} words / {hier['chars']} chars) ---")
        print(hier["text"])

    with open("results_chunk_content.json", "w") as f:
        json.dump(out, f, indent=2, default=str)

    print("\n\n===== CHUNK SIZE COMPARISON =====")
    print(f"{'query':<55}{'fixed words':<14}{'hier words'}")
    for r in out:
        q = (r["query"][:52] + "...") if len(r["query"]) > 52 else r["query"]
        print(f"  {q:<55}{r['fixed']['words']:<14}{r['hierarchical']['words']}")
    fw = sum(r["fixed"]["words"] for r in out) / len(out)
    hw = sum(r["hierarchical"]["words"] for r in out) / len(out)
    print(f"\n  Avg chunk size — fixed: {fw:.0f} words | hierarchical: {hw:.0f} words")
    print("Saved results_chunk_content.json")

if __name__ == "__main__":
    run()