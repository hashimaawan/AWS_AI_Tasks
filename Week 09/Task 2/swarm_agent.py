"""
swarm_agent.py — Task 2, Option B: TRUE multi-agent collaboration via a Strands Swarm.

Unlike Option A (agents-as-tools, where a supervisor CALLS sub-agents), a Swarm has NO
central controller. The agents are peers, each auto-equipped with handoff_to_agent and
complete_swarm_task. They collaborate through autonomous, bidirectional handoffs and a
shared context.

Agents:
  • triage   (entry point) — reads the message, hands off to a specialist, or asks to
                             clarify if it genuinely can't tell (decline, don't guess)
  • order    — order status / shipping / product FAQ; can hand off to returns
  • returns  — return eligibility / refunds; can hand off to order

Reuses the Task 1 Gateway, Cognito, Knowledge Base, and Guardrail.

Run interactively:  python swarm_agent.py chat
Import for eval:     import swarm_agent
"""
import os
import boto3
import requests
from strands import Agent, tool
from strands.models import BedrockModel
from strands.multiagent import Swarm
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# ---- Config (same resources as Task 1 / Option A) ----
REGION            = os.environ.get("AWS_REGION", "us-east-1")
MCP_URL           = os.environ.get("MCP_URL", "https://csbot-gateway-qsf83slwcq.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp")
USER_POOL_ID      = os.environ.get("USER_POOL_ID", "us-east-1_zUkl0Gxco")
CLIENT_ID         = os.environ.get("CLIENT_ID", "79tdv9bb7v57tneqvrtabin34j")
COGNITO_DOMAIN    = os.environ.get("COGNITO_DOMAIN", "agentcore-d4992ab7")
KNOWLEDGE_BASE_ID = os.environ.get("KNOWLEDGE_BASE_ID", "3BVCAA2SUV")
GUARDRAIL_ID      = os.environ.get("GUARDRAIL_ID", "dx70nu28renv")
GUARDRAIL_VERSION = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
MODEL_ID          = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")


def get_access_token():
    cog = boto3.client("cognito-idp", region_name=REGION)
    d = cog.describe_user_pool_client(UserPoolId=USER_POOL_ID, ClientId=CLIENT_ID)["UserPoolClient"]
    scope = " ".join(d.get("AllowedOAuthScopes", []))
    print(f">> Auth: requesting token (scope: {scope or 'none'})...")
    url = f"https://{COGNITO_DOMAIN}.auth.{REGION}.amazoncognito.com/oauth2/token"
    r = requests.post(url, data={"grant_type": "client_credentials", "client_id": CLIENT_ID,
                                 "client_secret": d["ClientSecret"], "scope": scope},
                      headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


_kb = boto3.client("bedrock-agent-runtime", region_name=REGION)


@tool
def search_faq(question: str) -> str:
    """Search the AuraBuds Pro product FAQ knowledge base (setup, battery, warranty, etc.)."""
    r = _kb.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={"text": question},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
    )
    chunks = [x["content"]["text"] for x in r.get("retrievalResults", [])]
    return "\n\n".join(chunks) if chunks else "No matching FAQ entry was found."


model = BedrockModel(
    model_id=MODEL_ID, region_name=REGION,
    guardrail_id=GUARDRAIL_ID, guardrail_version=GUARDRAIL_VERSION,
    guardrail_trace="enabled", guardrail_redact_input=True, guardrail_redact_output=True,
)


def _find_tool(tools, needle):
    for t in tools:
        name = getattr(t, "tool_name", getattr(t, "name", ""))
        if needle in name:
            return t
    return None


# ---- Connect to the Gateway; build the peer agents ----
_token = get_access_token()


def _transport():
    return streamablehttp_client(MCP_URL, headers={"Authorization": f"Bearer {_token}"})


mcp_client = MCPClient(_transport)
mcp_client.start()

_all_tools = mcp_client.list_tools_sync()
_order_tool   = _find_tool(_all_tools, "get_order_status")
_returns_tool = _find_tool(_all_tools, "get_return_policy")
print("Gateway tools:", [getattr(t, "tool_name", getattr(t, "name", str(t))) for t in _all_tools])

# NOTE: agent `name` and `description` are what OTHER agents read to decide handoffs,
# so they must clearly state each specialist's scope.
triage_agent = Agent(
    model=model,
    name="triage",
    description="First point of contact. Routes the customer to the order or returns specialist, or asks the customer to clarify when the request is ambiguous.",
    system_prompt=(
        "You are the triage agent for AuraBuds Pro support. Read the customer's message and hand off "
        "to exactly one specialist:\n"
        "- hand off to 'order' for order status, shipping, delivery, or product/how-to questions.\n"
        "- hand off to 'returns' for returns, return eligibility, or refunds.\n"
        "If you cannot confidently tell which specialist the request belongs to, DO NOT hand off. "
        "Instead reply asking the customer to clarify whether it's an order or a returns question. "
        "Never answer order or returns questions yourself."
    ),
    tools=[],
)

order_agent = Agent(
    model=model,
    name="order",
    description="Order specialist: handles order status, shipping, delivery, and product FAQ questions using get_order_status and the FAQ knowledge base.",
    system_prompt=(
        "You are the Order specialist for AuraBuds Pro. Use get_order_status for order questions "
        "(ask for the order ID if missing; never assume one) and search_faq for product questions. "
        "If the customer actually wants a return or refund, hand off to the 'returns' specialist. "
        "Keep replies short and polite."
    ),
    tools=[_order_tool, search_faq],
)

returns_agent = Agent(
    model=model,
    name="returns",
    description="Returns specialist: handles return eligibility and refunds using get_return_policy.",
    system_prompt=(
        "You are the Returns specialist for AuraBuds Pro. Use get_return_policy (order ID optional; "
        "never assume one). If the customer actually wants order status or product help, hand off to "
        "the 'order' specialist. Keep replies short and polite."
    ),
    tools=[_returns_tool],
)

# The Swarm: peers, entry at triage, with safety bounds against runaway handoffs.
swarm = Swarm(
    [triage_agent, order_agent, returns_agent],
    entry_point=triage_agent,
    max_handoffs=6,
    execution_timeout=120.0,
    repetitive_handoff_detection_window=4,
    repetitive_handoff_min_unique_agents=2,
)


def run(message):
    """Run one customer message through the swarm and return the result object."""
    return swarm(message)


def chat_loop():
    print("\nSwarm ready (triage -> order/returns, peer handoffs). Type 'quit' to exit.")
    while True:
        try:
            msg = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if msg.lower() in {"quit", "exit", ""}:
            break
        result = run(msg)
        print("\n--- swarm result ---")
        print(result)
        print("--------------------")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        chat_loop()
    else:
        print("\nSwarm ready. Run 'python swarm_agent.py chat' to talk to it.")
