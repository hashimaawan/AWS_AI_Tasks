AWS_REGION = "us-east-1"

# All four run on-demand in us-east-1 with base IDs (no inference profile).
MODELS = [
    {"key": "claude-haiku-4.5", "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
     "provider": "Anthropic", "supports_tools": True},
    {"key": "nova-lite",      "model_id": "amazon.nova-lite-v1:0",
     "provider": "Amazon",    "supports_tools": True},
    {"key": "mistral-large",  "model_id": "mistral.mistral-large-2402-v1:0",
     "provider": "Mistral",   "supports_tools": True},
    {"key": "llama3-70b",     "model_id": "meta.llama3-70b-instruct-v1:0",
     "provider": "Meta",      "supports_tools": False},  # no Converse tool use
]

# USD per 1,000 tokens as (input, output). VERIFIED on the live Bedrock pricing
PRICING = {
    "claude-haiku-4.5": (0.001, 0.005),
    "nova-lite":      (0.00006, 0.00024),
    "mistral-large":  (0.00400, 0.01200),
    "llama3-70b":     (0.00099, 0.00099),
}