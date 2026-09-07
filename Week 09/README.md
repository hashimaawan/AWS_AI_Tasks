# Week 09 — Amazon Bedrock: Agents, Guardrails & Multi-Agent Systems

Two customer-support agents built on **Amazon Bedrock AgentCore**, for a fictional product
(**AuraBuds Pro** earbuds). Task 1 is a single agent; Task 2 extends it into a multi-agent
system, built two ways (supervisor routing and a true collaborative swarm).

- **Model:** Claude Haiku 4.5 · **Framework:** Strands · **Region:** us-east-1
- **Tools over MCP:** AgentCore Gateway → Lambda · **RAG:** Bedrock Knowledge Base on S3 Vectors
- **Safety:** Bedrock Guardrail (PII masking + denied topics) · **Tracing:** OpenTelemetry

---

## Task 1 — Single Agent (Customer Support Bot)

A single agent that answers **order-status** questions and **product-FAQ** questions, with a
guardrail masking PII and refusing off-limits topics.

**How it works**
- `get_order_status` — a **Lambda** exposed as an **MCP tool** through an **AgentCore Gateway**
  (OAuth via Cognito). This is the production, reusable, auth-protected tool pattern.
- `search_faq` — an **in-code tool** that queries a **Bedrock Knowledge Base** (S3 Vectors) via
  the Retrieve API. (The KB is already a reusable service by its ID; wrapping it added no benefit.)
- A **Bedrock Guardrail** wraps every model call: masks email/phone/name/address/card/SSN and
  refuses financial/medical advice.

**Architecture:** see `Task 1/images/t1-architecture.png`

**Files**
```
Task 1/
├── agent.py             # the agent: token → Gateway MCP → discover tool → + FAQ tool + guardrail
├── run_evals.py         # reproducible 7-case eval (order lookup, miss, FAQ, PII, denied topic, scope)
├── infra/               # gateway setup + IAM policies
│   ├── setup_gateway.py     # builds Cognito auth + Gateway + registers the Lambda target
│   ├── add_target.py        # re-registers the order Lambda target
│   ├── gateway-trust.json   # IAM trust policy (lets the Gateway assume its role)
│   └── gateway-invoke.json  # IAM permission (lets that role invoke the Lambda)
├── lambda/
│   └── get_order_status.py  # order-lookup Lambda (mock orders; Gateway-target format)
├── KB/
│   └── product-faq.md       # the FAQ document ingested into the Knowledge Base
├── images/                  # architecture + screenshots
└── task1-onepager.html      # visual report
```

**Run**
```bash
python agent.py chat        # interactive
python run_evals.py         # 7/7 behaviours
```

**Result:** 7/7 test behaviours pass — order lookup, graceful miss, FAQ retrieval, FAQ nuance,
PII masked (still answers), denied-topic refusal, out-of-scope refusal.

---

## Task 2 — Multi-Agent (Supervisor Routing)

A supervisor routes each message to the right specialist — **Order** or **Returns** — and
**declines to guess** when a request is ambiguous. Built **two ways**:

### Option A — Agents-as-tools (`supervisor.py`)
A supervisor agent **calls** each specialist as a tool. Hierarchical, one-directional,
deterministic, cheap. This is **routing / orchestration**.
**Architecture:** `Task 2/images/t2-architecture-A.png`

### Option B — Swarm, true collaboration (`swarm_agent.py`)
Three **peer** agents (triage, order, returns) with **no central controller**. Each is
auto-equipped with `handoff_to_agent` + `complete_swarm_task`, shares working memory, and can
hand off to any peer — **including specialist ⇄ specialist**. This is **true collaboration**.
**Architecture:** `Task 2/images/t2-architecture.png`
**Collaboration flow:** `Task 2/images/t2-collab-sequence.png` (a 2-part question answered by
three agents across two handoffs).

**The difference, in one line:** in Option A you write functions that *call* the sub-agents
(top-down); in Option B the agents get automatic handoff tools and pass control to *each other*
(peer-to-peer).

**Reused from Task 1:** the Gateway, Cognito, Knowledge Base, Guardrail, and the order tool.
**New in Task 2:** a Returns Lambda (`get_return_policy`), registered as a **second Gateway
target**; two sub-agents; the supervisor (A) and the swarm (B); a routing eval; OTEL tracing.

**Observability:** the agents are instrumented with **OpenTelemetry**; each run emits a trace
(supervisor → specialist → tool → model calls) rendered as a waterfall
(`Task 2/images/t2-trace.png`). *Note: the managed CloudWatch dashboard needs Transaction
Search, which the org SCP blocks at the account level, so traces were captured locally — the
same span data, rendered by `view_trace.py`.*

**Files**
```
Task 2/
├── supervisor.py          # Option A: agents-as-tools (routing)
├── swarm_agent.py         # Option B: Strands Swarm (true collaboration)
├── run_routing_evals.py   # routing scorecard (2 order, 2 returns, 2 ambiguous)
├── view_trace.py          # renders OTEL spans → HTML waterfall
├── infra/
│   ├── add_returns_target.py  # registers the returns Lambda as a 2nd Gateway target
│   └── returns-invoke.json    # IAM permission to invoke the returns Lambda
├── lambda/
│   └── get_return_policy.py   # returns/refund Lambda (order_id optional)
├── images/                    # architectures + collaboration diagram + screenshots
└── task2-onepager.html        # visual report
```

**Run**
```bash
python supervisor.py chat        # Option A (routing)
python swarm_agent.py chat       # Option B (swarm collaboration)
python run_routing_evals.py      # routing scorecard — 6/6
```

**Result:** 6/6 routing — 4 clear cases routed correctly, 2 ambiguous cases declined (asked to
clarify) rather than guessing. Option B additionally demonstrates specialist-to-specialist
handoff on multi-part questions.

---

## Key design decisions

- **AgentCore, not Agents Classic** — Classic is in maintenance mode and closed to new accounts;
  AgentCore is the current path. Concepts map 1:1.
- **S3 Vectors, not OpenSearch Serverless** — no idle floor vs a ~$700/month baseline; far cheaper
  for a low-traffic FAQ.
- **Gateway + Lambda (MCP) for the order tool** — a real, reusable, auth-protected service.
- **FAQ in-code** — the KB is already reusable via its ID; a wrapper added no benefit (trade-off:
  slightly less discoverable than a Gateway-exposed tool).
- **Guardrail PII = Mask, not Block** — masking removes the PII but still answers the question.
- **Claude Haiku 4.5** — routing + short replies; cheaper/faster than Sonnet, which is the fallback.
- **Agents-as-tools vs swarm** — routing (deterministic, cheaper) vs true collaboration (peer
  handoffs, more tokens). Both included to show the trade-off.

## Environment notes (org SCP)
The account's Service Control Policy denies resource creation unless tagged; all Lambdas were
created with `owner` + `environment` tags. Two things it blocked at the account level:
CloudWatch Transaction Search (observability dashboard) and the Gateway's optional auto-logging —
both handled or deferred, with local tracing used instead.
