# Shared config for Task 2. One place to change IDs/models.
AWS_REGION = "us-east-1"

# Fixed-size KB (built first). The hierarchical KB ID gets added later for the A/B.
KB_ID_FIXED = "F5ZVEGYXLA"

# Model used to GENERATE the answer from retrieved chunks (RetrieveAndGenerate).
# Must be an inference-profile ID (cross-region) for Claude 4.x — same rule as Task 1.
GEN_MODEL_ARN = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# How many chunks to retrieve per query (KB default is 5).
TOP_K = 5

# Contextual grounding + relevance guardrail (created in console)
GUARDRAIL_ID = "t9onkqq1882f"
GUARDRAIL_VERSION = "DRAFT"

KB_ID_HIERARCHICAL = "TAK2AVO94U"