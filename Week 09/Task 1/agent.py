"""
agent.py — AuraBot: a Strands customer-support agent on Amazon Bedrock AgentCore.

Tools:
  • get_order_status  -> Lambda, exposed as an MCP tool via the AgentCore Gateway
  • search_faq        -> queries a Bedrock Knowledge Base (S3 Vectors)
Guardrail:
  • Bedrock Guardrail (PII masking + denied topics) wraps every model call

Run interactively:   python agent.py chat
Import for eval:      import agent   (chat loop stays off)

IDs are read from environment variables, falling back to the known values
so it works out of the box in this account.
"""
import os
import boto3
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# ---- Configuration (env var first, known value as fallback) ----
REGION            = os.environ.get("AWS_REGION", "us-east-1")
MCP_URL           = os.environ.get("MCP_URL", "https://csbot-gateway-qsf83slwcq.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
USER_POOL_ID      = os.environ.get("USER_POOL_ID", "us-east-1_zUkl0Gxco")
CLIENT_ID         = os.environ.get("CLIENT_ID", "79tdv9bb7v57tneqvrtabin34j")
COGNITO_DOMAIN    = os.environ.get("COGNITO_DOMAIN", "agentcore-d4992ab7")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "3BVCAA2SUV")
GUARDRAIL_ID      = os.environ.get("GUARDRAIL_ID", "dx70nu28renv")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
MODEL_ID          = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


# ---- 1. OAuth token for the Gateway (client-credentials flow) ----
def get_access_token():
    cog = boto3.client("cognito-idp", region_name=REGION)
    d = cog.describe_user_pool_client(UserPoolId=USER_POOL_ID, ClientId=CLIENT_ID)["UserPoolClient"]
    secret = d["ClientSecret"]
    scope = " ".join(d.get("AllowedOAuthScopes", []))
    print(f">> Auth: requesting token (scope: {scope or 'none'})...")
    url = f"https://{COGNITO_DOMAIN}.auth.{REGION}.amazoncognito.com/oauth2/token"
    r = requests.post(
        url,
        data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
              "client_secret": secret, "scope": scope},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


# ---- 2. FAQ tool -> Bedrock Knowledge Base ----
_kb = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_faq(question: str) -> str:
    """Search the AuraBuds Pro product FAQ knowledge base.

    Use for setup, pairing, factory reset, battery, water resistance, warranty.

    Args:
        question: The customer's product or how-to question.
    """
    r = _kb.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    chunks = [x["content"]["text"] for x in r.get("retrievalResults", [])]
    return "\n\n".join(chunks) if chunks else "No matching FAQ entry was found."


# ---- 3. Model + guardrail ----
model = BedrockModel(
    model_id=MODEL_ID,
    region_name=REGION,
    guardrail_id=GUARDRAIL_ID,
    guardrail_version=GUARDRAIL_VERSION,
    guardrail_trace="enabled",
    guardrail_redact_input=True,
    guardrail_redact_output=True,
)

SYSTEM_PROMPT = """You are AuraBot, a friendly and concise customer-support assistant for the AuraBuds Pro wireless earbuds.

- For order status, shipping, or delivery questions, use the order-status tool. If the customer hasn't given an order ID, politely ask for it first.
- For product questions (setup, pairing, reset, battery, water resistance, warranty), use the search_faq tool.
- Only help with (a) order status and (b) AuraBuds Pro product questions. Otherwise politely say you can only help with those two areas.
- Never invent order details or product facts. If a tool returns nothing useful, say you don't have that information.
- Keep replies short, clear, and polite."""


# ---- 4. Connect to the Gateway over MCP and build the agent ----
_token = get_access_token()


def _transport():
    return streamablehttp_client(MCP_URL, headers={"Authorization": f"Bearer {_token}"})


# The MCP client must stay open while the agent is used, so we enter its
# context here at import time and keep it open for the life of the process.
mcp_client = MCPClient(_transport)
mcp_client.start()

_gateway_tools = mcp_client.list_tools_sync()
_names = [getattr(t, "tool_name", getattr(t, "name", str(t))) for t in _gateway_tools]
print("Tools discovered from the Gateway:", _names)

# This is the object eval scripts and the chat loop both use.
agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[*_gateway_tools, search_faq],
)


# ---- 5. Interactive chat loop — only runs when launched with "chat" ----
def chat_loop():
    print("\nAuraBot ready. Ask about an order or the product. Type 'quit' to exit.")
    while True:
        try:
            msg = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit", ""}:
            break
        print("\nAuraBot: ", end="", flush=True)
        agent(msg)
        print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        chat_loop()
    else:
        print("\nAgent is ready. Run 'python agent.py chat' to talk to it, "
              "or 'python run_evals.py' to run the evaluation.")
