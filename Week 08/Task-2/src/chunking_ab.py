import json
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from kb_config import AWS_REGION, KB_ID_FIXED, KB_ID_HIERARCHICAL, TOP_K

_client = boto3.client(
    "bedrock-agent-runtime",
    region_name=AWS_REGION,
    config=Config(read_timeout=120, retries={"max_attempts": 2}),
)

# Retrieval-accuracy probes. Each has the doc we EXPECT to see in the top-K.
# Mix: short policy docs (likely tie) + long Pillar whitepaper (where hierarchical
# has the best chance to differ).
PROBES = [
    # --- short policy docs (baseline; expected to tie) ---
    {"id": "idle_ec2",      "q": "What CPU threshold defines an idle EC2 instance?",
     "expect_doc": "09_idle_resource_cleanup_runbook"},
    {"id": "budget_120",    "q": "Who is notified at 120% of budget?",
     "expect_doc": "10_budget_alert_escalation_playbook"},
    {"id": "costcenter",    "q": "What format must the CostCenter tag follow?",
     "expect_doc": "08_resource_tagging_standard"},
    {"id": "approval_25k",  "q": "Who approves recurring spend over $25,000 per month?",
     "expect_doc": "07_cloud_cost_governance_policy"},
    {"id": "tagging_mand",  "q": "What are the mandatory resource tags?",
     "expect_doc": "08_resource_tagging_standard"},
    # --- long Pillar whitepaper (where hierarchical may win) ---
    {"id": "cfm_pillars",   "q": "What are the phases of the Cloud Financial Management framework?",
     "expect_doc": "01_cost_optimization_pillar"},
    {"id": "rightsizing",   "q": "What is rightsizing in cost optimization?",
     "expect_doc": "01_cost_optimization_pillar"},
    {"id": "showback",      "q": "What is the difference between showback and chargeback?",
     "expect_doc": "01_cost_optimization_pillar"},
    {"id": "matched_supply","q": "How should supply be matched to demand to optimize cost?",
     "expect_doc": "01_cost_optimization_pillar"},
]


def retrieve(kb_id, question):
    resp = _client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": TOP_K}},
    )
    chunks = []
    for r in resp.get("retrievalResults", []):
        uri = r.get("location", {}).get("s3Location", {}).get("uri", "")
        chunks.append({"doc": uri.split("/")[-1], "score": r.get("score"),
                       "text": r.get("content", {}).get("text", "")[:200]})

#         # in score_kb, when you find the correct chunk:
# matched_score = next((c["score"] for c in chunks if p["expect_doc"] in c["doc"]), None)
# rows.append({..., "rank": rank, "match_score": matched_score, "top_docs": docs_returned})
    return chunks


def score_kb(kb_id, label):
    print(f"\n########## {label} ({kb_id}) ##########")
    rows = []
    hits = 0
    for p in PROBES:
        try:
            chunks = retrieve(kb_id, p["q"])
        except ClientError as e:
            print(f"  {p['id']}: ERROR {e.response['Error']['Code']}")
            continue
        docs_returned = [c["doc"] for c in chunks]
        # "Hit" = the expected doc appears anywhere in the top-K retrieved chunks.
        hit = any(p["expect_doc"] in d for d in docs_returned)
        # Rank of first correct chunk (1-based); None if not found.
        rank = next((i + 1 for i, d in enumerate(docs_returned) if p["expect_doc"] in d), None)
        if hit:
            hits += 1
        rows.append({"id": p["id"], "expect": p["expect_doc"], "hit": hit,
                     "rank": rank, "top_docs": docs_returned})
        print(f"  {p['id']:<15} hit={hit}  rank={rank}  top: {docs_returned}")
    acc = hits / len(PROBES)
    print(f"  --> retrieval accuracy: {hits}/{len(PROBES)} = {acc:.0%}")
    return {"label": label, "kb_id": kb_id, "accuracy": acc, "hits": hits,
            "total": len(PROBES), "rows": rows}


def run():
    fixed = score_kb(KB_ID_FIXED, "FIXED-SIZE (300/20)")
    hier = score_kb(KB_ID_HIERARCHICAL, "HIERARCHICAL")

    with open("results_chunking_ab.json", "w") as f:
        json.dump({"fixed": fixed, "hierarchical": hier}, f, indent=2, default=str)

    print("\n\n===== CHUNKING A/B SUMMARY =====")
    print(f"{'probe':<15}{'fixed':<10}{'hierarchical':<14}{'winner'}")
    for pf, ph in zip(fixed["rows"], hier["rows"]):
        f_mark = f"hit@{pf['rank']}" if pf["hit"] else "miss"
        h_mark = f"hit@{ph['rank']}" if ph["hit"] else "miss"
        if pf["hit"] and ph["hit"]:
            winner = "tie" if pf["rank"] == ph["rank"] else ("fixed" if pf["rank"] < ph["rank"] else "hierarchical")
        elif pf["hit"]:
            winner = "fixed"
        elif ph["hit"]:
            winner = "hierarchical"
        else:
            winner = "both miss"
        print(f"  {pf['id']:<15}{f_mark:<10}{h_mark:<14}{winner}")
    print(f"\n  FIXED accuracy:        {fixed['hits']}/{fixed['total']} = {fixed['accuracy']:.0%}")
    print(f"  HIERARCHICAL accuracy: {hier['hits']}/{hier['total']} = {hier['accuracy']:.0%}")
    print("\nSaved results_chunking_ab.json")


if __name__ == "__main__":
    run()