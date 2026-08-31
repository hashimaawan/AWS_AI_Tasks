# Week 8 — Amazon Bedrock: Core Patterns & RAG

Hands-on Bedrock work for Week 8. **Task 1 (Multi-Model Comparison)** and **Task 2 (RAG with Knowledge Bases)** are both complete and documented below.

---

## Task 1 — Bedrock Multi-Model Comparison

### TL;DR (the verdict)

There is **no single best model — you route by task.**

| Use case | Best pick | Why |
|---|---|---|
| Structured extraction (JSON) | **Nova Lite** | Correct, keeps all fields, ~40× cheaper and fastest; strip markdown fences with a parser |
| Multi-step reasoning | **Claude Haiku 4.5** | Exactly correct *and* fast; Llama tied on accuracy but is unusably slow |
| Tone / customer-facing copy | **Claude Haiku 4.5** | Best senior-register calibration; all models handled the kid version well |
| Cheapest "good enough" default | **Nova Lite** — *with a caveat* | Wins everything **except** reasoning; route reasoning elsewhere |

**Headline finding:** across 3 scenarios per challenge (auto-graded), the cheapest/fastest model (Nova Lite) was reliable on extraction and tone but weakest on multi-step arithmetic. A single-sample test had wrongly suggested "Nova can't reason" — multi-scenario testing corrected that to a milder, truer "less reliable on precise arithmetic." Measuring more than once is what made the finding honest.

### What this does

Using the **Bedrock Converse API**, four models are auto-graded across three challenges on **quality × cost × latency**:

- **Structured output** — extract fields from support emails as JSON; graded in three tiers: structure (valid JSON), objective value (name + required facts present), subjective value (sentiment/urgency vs. our labels).
- **Reasoning** — business-math problems with a known correct answer (incl. a deliberate "trap" where the naive answer is wrong, and a `vendor_switch` case whose answer is "yes" to catch models lazily defaulting to "no").
- **Tone control** — explain a concept to a 10-year-old vs. a senior engineer; graded two ways: readability grade-spread (Level 1) and an LLM-as-judge (Level 2).

### Architecture

```
                    ┌──────────────────────────┐
                    │     run_comparison.py      │
                    │  scenarios × models loop   │
                    │  (fault-tolerant, N-limit) │
                    └────────────┬──────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
       scenarios.py         bedrock_utils.py     grading.py
       (inputs +            converse() wrapper   auto-graders:
        expected answers)   captures cost/       structured / reasoning
                            latency/tokens       / tone (L1 + L2 judge)
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │  Amazon Bedrock (us-east-1)│
                    │  Claude Haiku 4.5 · Nova   │
                    │  Lite · Mistral · Llama3   │
                    └────────────┬──────────────┘
                                 ▼
                    results_multi.json ──► build_report.py / build_html_report.py
```

### Models compared

| Slot | Model | Model ID | Tool use |
|---|---|---|---|
| Anthropic | Claude Haiku 4.5 | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Yes |
| Amazon | Nova Lite | `amazon.nova-lite-v1:0` | Yes |
| Mistral | Mistral Large | `mistral.mistral-large-2402-v1:0` | Yes |
| Meta | Llama 3 70B | `meta.llama3-70b-instruct-v1:0` | No |

> **Design decision — Nova Lite instead of Titan Text.** Titan is legacy and lacks clean Converse tool-use / system-prompt support; Nova Lite is its supported successor.

> **Design decision — kept a no-tool-use model (Llama 3 70B) on purpose.** It surfaces a real constraint: guaranteed structured output via a tool schema is model-dependent.

### Setup notes

- **Model access (2026):** Bedrock's "Model access" console page is retired — serverless models auto-enable on first invoke. Third-party models sit behind a one-time AWS Marketplace subscription. `claude-3-haiku` (Legacy) had a stuck subscription and `claude-3-5-haiku-20241022` was end-of-life; current **Claude Haiku 4.5** invoked cleanly with the `us.` inference-profile prefix (cross-region only — will not run on a bare model ID).
- **Auth:** IAM Identity Center (SSO), not a long-lived IAM user. Short-lived, auto-expiring credentials — the right call in a shared sandbox.

### Results (3 scenarios per challenge, auto-graded)

| Model | Struct (objective) | Reasoning (math) | Tone spread | Tone judge | Cost/run\* | Avg latency |
|---|---|---|---|---|---|---|
| Claude Haiku 4.5 | 3/3 | **3/3** | **9.9** | 5/5 | ~$0.0072 | ~3,745 ms |
| Nova Lite | 3/3 | 2/3 | 7.9 | ~4.8 | **~$0.0003** | **~1,769 ms** |
| Mistral Large | 3/3 | 3/3 (math) | 5.9 | ~4.8 | ~$0.0154 | ~6,300 ms |
| Llama 3 70B | 1/3 | **3/3** | 4.5 | ~4.8 | ~$0.0014 | ~5,652 ms |

\* Placeholder pricing from `models_config.py` — verify against the live Bedrock pricing page.

### Key findings

- **Structured output has three tiers, and only the value checks differentiate.** All models produce valid JSON (structure 100%). The signal is in *objective* content: **Llama repeatedly drops facts** (order numbers), scoring 1/3, while the others are near-perfect. Subjective fields (sentiment/urgency) are contestable — some "failures" were debatable labels, not model errors.
- **Reasoning: the `vendor_switch` trap confirmed the models genuinely reason** — none defaulted to a lazy "no". Two grader gaps were found and fixed (a keyword list too narrow, a shipping-urgency label all four models disagreed with) — a reminder that objective checks are trustworthy and subjective ones need a human/LLM backstop.
- **Tone: Level-1 and Level-2 disagreed on Mistral's API explanation** — readability passed it, but the LLM-judge caught it as shallow-for-a-senior. That divergence is exactly why two evaluation signals beat one.

### Design decisions (why this, not that)

- **Converse API, not `InvokeModel`** — one normalized response shape across four providers; `usage`/`metrics` give cost + latency for free.
- **Auto-grade everything** — every axis is a computed number, not a gut call. Cost-eff and Speed on the radar are *measured*; Structured/Reasoning/Tone are *scored* — the distinction is stated explicitly.
- **Multi-scenario, per-scenario reporting first** — a bare average hides why two "2/3" scores differ. Per-scenario detail is always shown alongside the aggregate.

### Limitations

- Placeholder pricing must be replaced with live figures before quoting cost.
- The reasoning grader detects whether the right *number appears*, so it can't fully separate a small arithmetic slip from a conceptual error on its own (it records `closest` so a human can see how far off).
- The LLM-judge has low discriminative power (clustered at 5/5) and a disclosed self-preference bias (it is also a contestant).

---

## Task 2 — RAG Application with Bedrock Knowledge Bases

### TL;DR (the verdict)

**RAG works, and it's measurably better where it matters — but it isn't magic, and I measured exactly where it wins.**

| Requirement | Result |
|---|---|
| (a) Retrieval accuracy | **4/4** correct document cited on policy questions; A/B probes 9/9 both KBs |
| (b) RAG vs direct LLM | **RAG outperformed on 5/10** (decisive on private facts; honest ties elsewhere) |
| (c) Chunking strategy + why | Document-level **tie (100%/100%)**; chunk-content **3–6.5× richer** with hierarchical |
| Wow — false-answer rate | **0/5 hallucinations** |
| Wow — guardrail | Contextual grounding **intervened on q9**, no over-blocking |

### What this does

A FinOps-domain RAG chatbot over **10 documents** in S3: 6 real AWS whitepapers (Cost Optimization Pillar, Savings Plans, tagging, Budgets, S3 storage) + 4 generated internal policy docs containing **invented facts** (idle-EC2 = CPU <3%, escalation to Director at 120%, CostCenter = `CC-####`, etc.). It answers via the **RetrieveAndGenerate** API and is tested with 10 questions (5 answerable, 5 designed to force "I don't know").

> **Why the invented policy facts matter:** no base LLM can know "CPU below 3%" — so these questions produce airtight *RAG-beats-direct* evidence and clean, gradeable ground truth. The AWS docs (public knowledge) are weaker for that comparison but prove retrieval on messy real prose.

### Architecture

```
   10 docs ──► S3 (s3://w8t2-aw/documents/)
                     │
                     ▼  ingest + Titan Text Embeddings V2
        ┌────────────────────────────┐
        │  Bedrock Knowledge Base     │   KB #1 fixed-size (300/20)   → OpenSearch Serverless
        │  (2 KBs, same corpus,       │   KB #2 hierarchical          → OpenSearch Serverless
        │   only chunking differs)    │
        └────────────┬───────────────┘
                     │ RetrieveAndGenerate (+ guardrail)
                     ▼
        ┌────────────────────────────┐
        │  Guardrail: contextual      │  grounding + relevance @ 0.75
        │  grounding + relevance      │  (hallucination backstop)
        └────────────┬───────────────┘
                     ▼
   rag_chatbot.py · direct_vs_rag.py · rag_chatbot_guarded.py
   chunking_ab.py · chunk_content_compare.py  ──►  5 result JSONs ──► task2_report.html
```

### Pipeline choices (why this, not that)

- **Self-managed "Unstructured Vector Store KB", not the recommended Managed KB.** Managed KB hides hierarchical chunking, and the task requires a chunking comparison — so the managed flow literally can't fulfill the requirement. Self-managed gave full control over indexing. *(For a production deploy where nobody tunes chunking, Managed KB would be the lower-maintenance choice.)*
- **Embeddings: Titan Text Embeddings V2 (1024-dim).** Cheap, native, no extra dependency. Cohere Embed was the alternative but offered no retrieval advantage worth the added dependency.
- **Vector store: OpenSearch Serverless.** Native one-click Bedrock integration, keeps data in-account with no third-party dependency.
  - *vs Pinecone:* excellent and cheap at scale, but a third-party service — external account, API key, data leaving AWS, extra vendor/security review. Avoided.
  - *vs Aurora pgvector:* genuinely cheaper for low-traffic (no OCU minimum floor), but needs a DB instance + schema + connections. Chose OpenSearch for speed of standup; would revisit pgvector for a cost-sensitive production KB.
- **Chunking A/B is two KBs, not a toggle** — chunking strategy is fixed at data-source creation and can't be edited afterward. A real Bedrock constraint.
- **Guardrail scoped to grounding + relevance only** — not the content/PII/denied-topic filters. The task is hallucination prevention, not content moderation.

### Results

**(a) Retrieval accuracy & RAG answers.** All 4 policy-fact questions returned the exact invented fact with a citation to the correct source doc (4/4). q5 (a real-AWS fact) was correctly declined — not reliably retrievable, so the bot didn't guess. q8 (a "GPU/SageMaker idle threshold" trap that *sounds* in-corpus) retrieved a topically-close chunk but refused to fabricate a number.


#### Retrieval accuracy — did the right chunks come back? (requirement a)

Measured two ways:

**Retrieve-API probes (retrieval only, fixed-size KB):**

| Probe | Expected source document | Retrieved? | Rank |
|---|---|---|---|
| idle_ec2 | Idle Resource Cleanup Runbook | Yes | #1 |
| budget_120 | Budget Alert & Escalation Playbook | Yes | #2 |
| costcenter | Resource Tagging Standard | Yes | #1 |
| approval_25k | Cloud Cost Governance Policy | Yes | #1 |
| tagging_mand | Resource Tagging Standard | Yes | #1 |
| cfm_pillars | Cost Optimization Pillar (whitepaper) | Yes | #1 |
| rightsizing | Cost Optimization Pillar (whitepaper) | Yes | #1 |
| showback | Cost Optimization Pillar (whitepaper) | Yes | #1 |
| matched_supply | Cost Optimization Pillar (whitepaper) | Yes | #1 |

Correct document returned on **9/9 probes**, rank 1 on 8 of 9.

**RAG chatbot citations (answerable set):** the 4 policy questions each cited the correct source document with the answer (q1→Cleanup Runbook, q2→Alert Playbook, q3→Tagging Standard, q4→Governance Policy) → **4/4**. q5 returned no citation: the fact IS in the corpus but sits inside a comparison *table*, which chunking/embedding surfaces poorly — the bot correctly declined rather than guessing.

**(b) RAG vs direct LLM** (same Haiku 4.5 model, only difference is documents):

| Category | Result |
|---|---|
| Policy facts q1–q4 | **RAG won 4/4** — direct model correctly refused (can't know private facts) |
| Public fact q5 | tie — direct guessed, RAG missed (honest corpus/retrieval gap) |
| Out-of-scope q6–q9 | tie — both correctly declined |
| Sanity floor q10 ("capital of France") | **RAG won** — direct answered "Paris" (correct, but *outside the source*); RAG correctly declined |

> **The q10 insight:** RAG's job isn't to know everything — it's to answer only from the source and admit when the source is silent. The direct model was factually right but behaviorally wrong for a grounded assistant. That's the whole point of RAG, shown in one question.

**(c) Chunking — fixed-size vs hierarchical:**

- **Document-level: a tie.** Both KBs retrieved the correct document at rank 1 on all 9 probes (100%/100%). For a small, topically-distinct corpus, chunking doesn't change *which document* comes back.
- **Chunk-content: a large difference.** On the long Cost Optimization Pillar whitepaper, hierarchical returned **3–6.5× more context per chunk**:

  | Query | Fixed (words) | Hierarchical (words) | Ratio |
  |---|---|---|---|
  | Rightsizing | 148 | 968 | **6.5×** |
  | Supply/demand matching | 218 | 756 | 3.5× |
  | CFM framework phases | 227 | 1,174 | **5.2×** |

  The fixed-size chunk started mid-sentence, ended mid-explanation, and included stray footnote URLs from a bad split boundary; hierarchical returned the complete, coherent section.

- **Recommendation:** fixed-size is sufficient for short-document corpora (simpler, tied accuracy); switch to hierarchical as documents get longer and context completeness matters.

**Why not semantic or other strategies?** Fixed-size and hierarchical are the two extremes — dumb-by-count vs. structure-aware — so the comparison directly answers "does chunk structure matter for this corpus?". Semantic chunking sits *between* them, so it would likely land between the two results; since fixed and hierarchical already tied at the document level (100%/100%), semantic almost certainly would too — a third line saying the same thing, not new signal. A clean two-way A/B is more interpretable than a muddy three-way one. Semantic earns its place on a *different* corpus — long, mixed-topic docs with frequent topic shifts but no heading structure (transcripts, scraped web content) — which this corpus is not. Semantic was not measured, so no claim is made it is worse; only that it was not the most informative comparison to run. A full sweep (fixed / hierarchical / semantic / none, scored on end-to-end answer quality) is a noted next step.

**Guardrail (contextual grounding + relevance @ 0.75).** False-answer rate: **0/5**. Defense-in-depth in action — the model declined 4/5 out-of-scope questions on its own; the guardrail **actively intervened on q9** (`guardrailAction = INTERVENED`). It did not over-block: all 4 legitimate policy answers passed. The guardrail converts good-but-voluntary model behavior into an *enforced, audited* boundary.

### Cost & teardown (a real FinOps lesson)

- **The cost is the vector store, not the data.** S3 storage and per-query inference are pennies; embedding is a one-time few cents. **OpenSearch Serverless bills for held capacity (~$11–12/day/collection) whether idle or not.** That is ~99% of the bill.
- **Gotcha learned firsthand: deleting a Knowledge Base does not always delete its OpenSearch collection.** Orphaned collections keep billing. Teardown must be verified at the *collection* level, not just the KB level — exactly the kind of idle-resource waste a FinOps program is built to catch.
- Both collections were deleted after extracting results; all findings are preserved in the saved JSON files.

### Demo script

**Technical:** "I built a FinOps RAG bot over 10 docs — 6 real AWS whitepapers plus 4 policy docs with invented facts so I could prove RAG beats a plain LLM and grade retrieval cleanly. Retrieval accuracy was 4/4 on the policy questions with correct citations. Against a direct LLM, RAG won on every private-fact question — the direct model correctly refused because it can't know those facts. My favourite result is q10: asked the capital of France, the direct model said Paris — correct, but outside the documents — while RAG correctly declined, because a grounded bot's job is to stay in-source. Hallucinations were zero, enforced by a contextual-grounding guardrail that actively blocked q9 without over-blocking the real answers. On chunking, document retrieval was a tie at 100%, but hierarchical returned 3–6.5× more complete context per chunk on the long whitepaper — so I'd use fixed-size for short docs and hierarchical as documents grow. Cost lesson: the bill is the idle OpenSearch collection, not the data — and deleting the KB doesn't delete the collection, so teardown has to be verified at the collection level."

**Plain-language:** "I built a chatbot that answers only from a set of company cost-management documents. I gave it questions it *could* answer and questions it *couldn't*, and it correctly said 'I don't know' every time it should have — no making things up. I compared it to a plain AI with no documents: for private company facts, the plain AI had to guess or refuse while mine answered from the source. I also tested two ways of splitting the documents — for this small set both found the right document equally well, but one method gave the AI much fuller context on long documents, which is better for accuracy. And the main cost isn't the documents or the questions — it's the always-on search database, which has to be shut down carefully or it keeps charging."

### Repo structure

```
week8-task2/
├── kb_config.py            # KB IDs, model ARN, guardrail ID, top-K
├── questions.py            # 10-question test set (5 answerable / 5 unanswerable)
├── rag_chatbot.py          # RetrieveAndGenerate core (answers + citations)
├── direct_vs_rag.py        # same Qs to a plain LLM, side by side
├── rag_chatbot_guarded.py  # RAG + contextual-grounding guardrail
├── chunking_ab.py          # fixed vs hierarchical retrieval accuracy
├── chunk_content_compare.py# fixed vs hierarchical chunk-content size
├── build_task2_report.py   # -> task2_report.html
├── results_*.json          # 5 result files
└── task2_report.html
```

### Limitations

- The chunking A/B measures document-level retrieval; a chunk-content-quality metric (beyond word count) would capture more of hierarchical's benefit.
- q5's miss shows RAG is only as good as retrieval — the fact wasn't reliably surfaced from the real AWS doc.
- Guardrail thresholds (0.75) were not exhaustively tuned; a threshold sweep would map the precision/recall tradeoff.
