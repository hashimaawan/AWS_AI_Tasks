# 10-question test set.
# answerable=True  -> the answer IS in the docs (mostly the policy docs, so RAG
#                     beats a direct LLM that can't know invented facts).
# answerable=False -> NOT in the docs; a good RAG bot must say "I don't know".
# For answerable ones, "expect_contains" lets us auto-check retrieval got the fact.

QUESTIONS = [
    # ---- 5 ANSWERABLE (ground truth from our docs) ----
    {"id": "q1_idle_ec2", "answerable": True,
     "q": "What CPU utilization threshold defines an idle EC2 instance in the cleanup policy?",
     "expect_contains": ["3%"], "source_doc": "09_idle_resource_cleanup_runbook"},

    {"id": "q2_budget_120", "answerable": True,
     "q": "Who gets notified when an account crosses 120% of its budget?",
     "expect_contains": ["Director"], "source_doc": "10_budget_alert_escalation_playbook"},

    {"id": "q3_costcenter_format", "answerable": True,
     "q": "What is the required format for the CostCenter tag value?",
     "expect_contains": ["CC-"], "source_doc": "08_resource_tagging_standard"},

    {"id": "q4_approval_25k", "answerable": True,
     "q": "Who must approve new recurring spend of $25,000 per month or more?",
     "expect_contains": ["VP", "Finance"], "source_doc": "07_cloud_cost_governance_policy"},

    {"id": "q5_ri_discount", "answerable": True,
     "q": "What is the maximum discount a Standard Reserved Instance can offer versus On-Demand?",
     "expect_contains": ["72"], "source_doc": "02_savings_plans_guide (real AWS doc)"},

    # ---- 5 UNANSWERABLE (should say "I don't know") ----
    {"id": "q6_leave_policy", "answerable": False,
     "q": "What is the annual leave policy for employees?"},

    {"id": "q7_ceo_name", "answerable": False,
     "q": "Who is the CEO of the company?"},

    {"id": "q8_gpu_threshold", "answerable": False,
     "q": "What GPU utilization threshold defines an idle SageMaker training job in the cleanup policy?"},

    {"id": "q9_healthcare", "answerable": False,
     "q": "What is our policy on healthcare reimbursement for remote workers?"},

    {"id": "q10_france", "answerable": False,
     "q": "What is the capital of France?"},
]